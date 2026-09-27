"""Freeze the exact source contexts declared in a RunManifest."""

import hashlib
import json
from pathlib import Path

from modules.git_modes import plan_candidate
from modules.static_scan.orchestrator import graph
from modules.static_scan.retrieval import retrieve
from modules.static_scan.review_units import extract_review_units


def context_hash(context):
    """Digest canonical UTF-8 JSON shared by the manifest and candidate audit."""
    raw = json.dumps(context, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def prepare_analysis(verified, *, mode="five", symbol=None, scope=None,
                     main_ref=None, candidate_ref=None, review="raw"):
    """Return (analysis, ordered contexts, candidate plan) from authenticated Git.

    ``verified`` is the result of verify_git_source. No target module is imported
    or executed. The graph database is closed before returning, including errors.
    """
    from modules.diagnosis.model import BOUNDARY_PERSPECTIVES, GENERIC_PERSPECTIVES, PERSPECTIVES

    if mode not in ("five", "boundary", "generic", "single", "plain"):
        raise ValueError("Unsupported analysis mode")
    if review not in ("raw", "outline", "cards"):
        raise ValueError("Unsupported review unit policy")
    if review != "raw" and mode in ("single", "plain"):
        raise ValueError("Single baselines do not receive graph review units")
    if (symbol is None) == (scope is None):
        raise ValueError("Select exactly one of symbol or scope")
    if symbol is not None and (
            not isinstance(symbol, str) or not symbol.strip() or "\x00" in symbol):
        raise ValueError("Selected symbol must be a nonempty string")
    if scope is not None and scope not in ("full", "impact"):
        raise ValueError("Unsupported analysis scope")
    if mode == "single" and scope == "impact":
        raise ValueError("Single-call baseline requires symbol or full scope")
    if mode == "plain" and symbol is None:
        raise ValueError("Plain baseline requires a symbol")
    if (main_ref is None) != (candidate_ref is None):
        raise ValueError("main_ref and candidate_ref must be supplied together")
    if symbol is not None and main_ref is not None:
        raise ValueError("Candidate references require scope")
    if scope == "impact" and main_ref is None:
        raise ValueError("Impact scope requires candidate references")

    run = verified["run"]
    repository = Path(run["repository"])
    plan = (plan_candidate(repository, main_ref, candidate_ref, scope)
            if main_ref is not None else None)
    if plan and plan["target_sha"] != run["commit"]:
        raise ValueError("Candidate revision differs from authenticated Git source")
    scanned, db = graph(repository, run["commit"])
    try:
        if scanned["python_parser"] != run["python_parser"]:
            raise ValueError("Graph Python parser differs from authenticated source scan")
        source_sha = {item["path"]: item["source_sha256"] for item in verified["evidence"]}
        if scanned["commit"] != run["commit"] or {
                item["path"]: item["source_sha256"] for item in scanned["files"]} != source_sha:
            raise ValueError("Graph source differs from authenticated Git source")
        selected_paths = plan["observed_target_paths"] if plan else sorted(source_sha)
        contexts = {}
        if symbol is not None:
            selected = retrieve(db, symbol=symbol)
            if mode == "plain":
                target = next((node for node in selected["nodes"] if node["distance"] == 0), None)
                if target is None:
                    raise ValueError("Selected graph symbol is not available in frozen Git source")
                row = db.execute(
                    "SELECT nodes.id,nodes.path,nodes.line,nodes.end_line,nodes.source_sha256,source_text.text "
                    "FROM nodes JOIN source_text USING(path) "
                    "WHERE nodes.kind='module' AND nodes.path=?", (target["path"],)
                ).fetchone()
                if row is None:
                    raise ValueError("Plain baseline needs complete frozen Python source")
                identity, path, start, end, source_hash, text = row
                selected = {"nodes": [{"id": identity, "path": path, "line": start,
                                       "end_line": end, "source_sha256": source_hash,
                                       "source_slice": text}],
                            "edges": [], "truncated": False,
                            "source_bytes": len(text.encode("utf-8")), "target_symbol": symbol}
            if not selected["nodes"]:
                raise ValueError("Selected graph symbol is not available in frozen Git source")
            if mode != "plain" and not any(node["distance"] == 0 for node in selected["nodes"]):
                raise ValueError("Selected graph symbol does not fit the source byte budget")
            if any(node["path"] not in source_sha or
                   node["source_sha256"] != source_sha[node["path"]] for node in selected["nodes"]):
                raise ValueError("Graph source differs from authenticated Git source")
            if review != "raw":
                selected["review_units"] = extract_review_units(
                    db, selected, level=review, selected_symbol=symbol)
            contexts["symbol:" + symbol] = selected
        elif mode == "single":
            rows = db.execute(
                "SELECT nodes.id,nodes.path,nodes.line,nodes.end_line,nodes.source_sha256,source_text.text "
                "FROM nodes JOIN source_text USING(path) WHERE nodes.kind='module' ORDER BY nodes.path"
            ).fetchall()
            if [row[1] for row in rows] != selected_paths:
                raise ValueError("Full baseline needs every parsed frozen Python module")
            contexts["full"] = {
                "nodes": [{"id": identity, "path": path, "line": start, "end_line": end,
                           "source_sha256": source_hash, "source_slice": text}
                          for identity, path, start, end, source_hash, text in rows],
                "edges": [], "truncated": False,
                "source_bytes": sum(len(row[5].encode("utf-8")) for row in rows)}
        else:
            for path in selected_paths:
                scope_id = "module:" + path
                contexts[scope_id] = None
                if db.execute("SELECT 1 FROM nodes WHERE id=?", (scope_id,)).fetchone() is None:
                    continue
                selected = retrieve(db, symbol=scope_id)
                primary = next((node for node in selected["nodes"] if node["id"] == scope_id), None)
                if primary is None or not primary.get("source_slice"):
                    continue
                complete = [node for node in selected["nodes"] if node.get("source_slice")]
                if len(complete) != len(selected["nodes"]):
                    retained = {node["id"] for node in complete}
                    selected = {**selected, "nodes": complete, "truncated": True,
                                "edges": [edge for edge in selected["edges"] if
                                          edge["source"] in retained and (
                                              edge["state"] == "unknown" or edge["target"] in retained)]}
                if review != "raw":
                    selected["review_units"] = extract_review_units(db, selected, level=review)
                contexts[scope_id] = selected
    finally:
        db.close()
    roles = (BOUNDARY_PERSPECTIVES if mode == "boundary" else
             GENERIC_PERSPECTIVES if mode == "generic" else
             ("all",) if mode in ("single", "plain") else PERSPECTIVES)
    analysis = {"mode": mode, "roles": list(roles), "scope": "symbol" if symbol is not None else scope,
                "symbol": symbol, "base_sha": plan["base_sha"] if plan else None,
                "context_policy": ("git-ast-context-v1" if review == "raw" else
                                   f"git-ast-{review}-v1"),
                "contexts": [{"scope_id": scope_id,
                              "sha256": context_hash(context) if context is not None else None}
                             for scope_id, context in contexts.items()]}
    return analysis, contexts, plan
