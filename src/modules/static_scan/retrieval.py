"""Deterministic retrieval from an already-built, frozen code graph."""

import re
import sqlite3
from collections.abc import Iterable
from .code_graph import SOURCE_BYTE_BUDGET, _render_context
from .counterexamples import counterexamples


def retrieve(
    db: sqlite3.Connection,
    *,
    frame: tuple[str, int] | None = None,
    symbol: str | None = None,
    changed_files: Iterable[str] = (),
    query: str | None = None,
    limit: int = 50,
    source_byte_budget: int = SOURCE_BYTE_BUDGET,
) -> dict:
    """Find exact symbols or lexical matches in changed files, then resolved neighbors.

    A symbol matches a node's full qualified name or ID. Lexical matching is
    case-sensitive substring matching against stored source text, restricted to
    changed files. Unknown edges are returned as provenance but never traversed.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if isinstance(source_byte_budget, bool) or not isinstance(source_byte_budget, int) or source_byte_budget <= 0:
        raise ValueError("source_byte_budget must be a positive integer")
    paths = tuple(sorted(set(changed_files)))
    if frame is None and not symbol and not (paths and query):
        raise ValueError("provide a frame, symbol or both changed_files and query")
    if query and not paths:
        raise ValueError("query requires changed_files")
    if paths and not query:
        raise ValueError("changed_files requires query")

    seeds: set[str] = set()
    frame_context = None
    if frame is not None:
        if (not isinstance(frame, tuple) or len(frame) != 2
                or not isinstance(frame[0], str) or not frame[0]
                or frame[0].startswith("/") or "\\" in frame[0]
                or any(part in ("", ".", "..") for part in frame[0].split("/"))
                or not frame[0].endswith(".py")
                or isinstance(frame[1], bool) or not isinstance(frame[1], int) or frame[1] < 1):
            raise ValueError("frame must be a repo-relative Python path and positive line")
        path, line = frame
        source = db.execute("SELECT text FROM source_text WHERE path=?", (path,)).fetchone()
        if source is None or line > len(re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", source[0])):
            raise ValueError("frame must identify a line in parsed frozen source")
        candidates = list(db.execute(
            "SELECT id,line,end_line FROM nodes WHERE path=? AND kind IN ('class','function')",
            (path,),
        ))
        enclosing = [(identity, start, end) for identity, start, end in candidates
                     if start <= line <= end]
        identity = min(enclosing, key=lambda item: (item[2] - item[1], item[0]))[0] if enclosing else f"module:{path}"
        provenance = db.execute("SELECT source_sha256 FROM nodes WHERE id=?", (identity,)).fetchone()
        if provenance is None:
            raise ValueError("frame has no parsed module")
        seeds.add(identity)
        frame_context = {"path": path, "line": line, "node_id": identity, "source_sha256": provenance[0]}
    exact: set[str] = set()
    if symbol:
        exact.update(row[0] for row in db.execute(
            "SELECT id FROM nodes WHERE id=? OR (name=? AND kind IN ('module','class','function'))",
            (symbol, symbol),
        ))
        seeds.update(exact)
    if query:
        for path in paths:
            row = db.execute("SELECT text FROM source_text WHERE path=?", (path,)).fetchone()
            if row is None:
                continue
            matching_lines = {number for number, line in enumerate(
                re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", row[0]), 1)
                              if query in line}
            if not matching_lines:
                continue
            definitions = list(db.execute(
                "SELECT id,line,end_line FROM nodes WHERE path=? AND kind IN ('class','function')",
                (path,),
            ))
            for number in matching_lines:
                enclosing = [(identity, start, end) for identity, start, end in definitions
                             if start <= number <= end]
                if enclosing:
                    # Prefer the innermost definition rather than its enclosing class.
                    seeds.add(min(enclosing, key=lambda item: (item[2] - item[1], item[0]))[0])
                else:
                    seeds.add(f"module:{path}")

    distances = dict.fromkeys(seeds, 0)
    frontier = seeds
    for depth in (1, 2):
        next_nodes: set[str] = set()
        for current in sorted(frontier):
            for source, target in db.execute(
                "SELECT source,target FROM edges WHERE state='resolved' AND (source=? OR target=?) "
                "ORDER BY kind,source,target,reference", (current, current),
            ):
                neighbor = target if source == current else source
                if neighbor not in distances:
                    next_nodes.add(neighbor)
        for identity in next_nodes:
            distances[identity] = depth
        frontier = next_nodes

    selected = sorted(distances, key=lambda identity: (distances[identity], identity != (frame_context or {}).get("node_id"), identity not in exact, identity))[:limit]
    nodes, budget_truncated, source_bytes = _render_context(db, selected, distances, source_byte_budget)
    chosen = {node["id"] for node in nodes}
    edges = [dict(source=source, target=target, kind=kind, state=state, reference=reference)
             for source, target, kind, state, reference in db.execute(
                 "SELECT source,target,kind,state,reference FROM edges ORDER BY source,kind,reference,target"
             ) if source in chosen and (state == "unknown" or target in chosen)]
    result = {"nodes": nodes, "edges": edges, "truncated": len(distances) > limit or budget_truncated,
              "source_bytes": source_bytes}
    result["static_counterexamples"] = counterexamples(db, nodes, edges)
    if frame_context is not None:
        result["frame"] = frame_context
    return result
