"""Source-only AST review units from an approved, immutable graph context.

These are syntactic observations, not execution paths, findings, or evidence of
model coverage. No graph call edge is used to infer invocation order or count.
"""

import ast
import hashlib
import json
import re
import sqlite3


_STATEMENTS = {
    ast.If: "branch", ast.For: "loop", ast.AsyncFor: "loop",
    ast.While: "loop", ast.Return: "return", ast.Raise: "raise",
    ast.Await: "await", ast.With: "with", ast.AsyncWith: "with",
    ast.Try: "try", ast.TryStar: "try", ast.Call: "call",
    ast.Break: "break", ast.Continue: "continue",
}
if hasattr(ast, "Match"):
    _STATEMENTS[ast.Match] = "branch"

_UNKNOWN = ["path_reachability", "guard_dominance", "aliases_and_external_state",
            "external_call_contracts"]


def _id(path: str, sha: str, symbol: str, kind: str, node: ast.AST) -> str:
    coordinates = (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)
    return hashlib.sha256(json.dumps((path, sha, symbol, kind, *coordinates),
                                     separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _coords(node: ast.AST) -> dict:
    return {"line": node.lineno, "col": node.col_offset,
            "end_line": node.end_lineno, "end_col": node.end_col_offset}


def _verified_span(lines: list[str], covered: set[int], node: ast.AST) -> bool:
    if not (1 <= node.lineno <= node.end_lineno <= len(lines)):
        return False
    if any(number not in covered for number in range(node.lineno, node.end_lineno + 1)):
        return False
    first, last = lines[node.lineno - 1].encode("utf-8"), lines[node.end_lineno - 1].encode("utf-8")
    # AST columns are UTF-8 byte offsets, not Unicode character offsets.
    if not (0 <= node.col_offset < len(first) and 0 < node.end_col_offset <= len(last)):
        return False
    for number, data in ((node.lineno, first), (node.end_lineno, last)):
        column = node.col_offset if number == node.lineno else node.end_col_offset
        try:
            data[:column].decode("utf-8")
        except UnicodeDecodeError:
            return False
    return True


def _syntax(text: str, lines: list[str], covered: set[int], node: ast.AST) -> str | None:
    if not _verified_span(lines, covered, node):
        return None
    return ast.get_source_segment(text, node)


def _direct_nodes(function: ast.FunctionDef | ast.AsyncFunctionDef):
    """Walk this function body only; deferred nested function/class bodies are separate."""
    def walk(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        yield node
        for child in ast.iter_child_nodes(node):
            yield from walk(child)

    for statement in function.body:
        yield from walk(statement)


def _definitions(tree: ast.Module):
    """Yield lexical function scopes, including those introduced conditionally."""
    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = f"{prefix}.{child.name}" if prefix else child.name
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield qualified, child
                yield from visit(child, qualified)
            elif not isinstance(child, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                yield from visit(child, prefix)

    yield from visit(tree, "")


def _condition(node: ast.AST) -> ast.AST | None:
    if isinstance(node, (ast.If, ast.While)):
        return node.test
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return node.iter
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return node.items[0].context_expr if node.items else None
    if isinstance(node, ast.Match):
        return node.subject
    return None


def _card(text: str, lines: list[str], covered: set[int], node: ast.AST,
          direct: list[ast.AST]) -> dict:
    test = _condition(node)
    condition = _syntax(text, lines, covered, test) if test is not None else None
    names = {item.id for item in ast.walk(test) if isinstance(item, ast.Name)} if test else set()
    relations = []
    contained = {id(item) for item in ast.walk(node)}
    for item in direct:
        if item is node or isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        kind = None
        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            if len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id in names:
                kind = "increment" if isinstance(item, ast.AugAssign) else "assignment"
        elif isinstance(item, (ast.If, ast.Break, ast.Continue, ast.Return, ast.Raise)):
            if id(item) in contained:
                kind = "nested_guard" if isinstance(item, ast.If) else "nested_" + type(item).__name__.lower()
        if kind is None:
            continue
        expression = _condition(item) if kind == "nested_guard" else item
        source = _syntax(text, lines, covered, expression) if expression is not None else None
        if source is None or not _verified_span(lines, covered, item):
            continue
        relations.append({"kind": kind, **_coords(item), "syntax": source})
    return {"condition": condition, "relations": relations,
            "unknown": list(_UNKNOWN) + ["condition_value_and_progress",
                                         "assignment_path_and_shadowing",
                                         "nested_control_target"]}


def _finally_location(node: ast.Try | ast.TryStar, lines: list[str]) -> dict | None:
    """The AST has no Finally node; locate its header without reading target files."""
    if not node.finalbody:
        return None
    found = None
    for number in range(node.lineno + 1, node.finalbody[0].lineno + 1):
        match = re.match(r"([ \t]*)finally\s*:", lines[number - 1])
        if match and len(match.group(1).encode("utf-8")) == node.col_offset:
            found = {"line": number, "col": node.col_offset, "end_line": number,
                     "end_col": node.col_offset + len("finally:"), "syntax": "finally:"}
    return found


def _packed_size(result: dict) -> int:
    """Measure the exact compact transmitted JSON, including its own byte count."""
    result["source_bytes"] = 0
    while True:
        size = len(json.dumps(result, ensure_ascii=False, separators=(",", ":"),
                              allow_nan=False).encode("utf-8"))
        if size == result["source_bytes"]:
            return size
        result["source_bytes"] = size


def extract_review_units(db: sqlite3.Connection, context: dict, *, level: str,
                         selected_symbol: str | None = None, max_bytes: int = 8192) -> dict:
    """Extract deterministic AST observations; transmit only verified source slices.

    The caller supplies a context authenticated from the frozen Git source.
    Altered slices or identities are rejected before transmission.
    ``source_bytes`` counts the entire compact UTF-8 JSON result. Unlisted
    inventory due to the metadata budget is explicitly unknown, never reviewed.
    """
    if level not in ("outline", "cards"):
        raise ValueError("level must be outline or cards")
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    if not isinstance(context, dict) or not isinstance(context.get("nodes"), list):
        raise ValueError("context must contain approved graph nodes")
    selected = context["nodes"]
    rows: dict[str, tuple[str, str, list[str], set[int]]] = {}
    scopes: dict[str, list[tuple[str, str, int, int, str]]] = {}
    for entry in selected:
        if not isinstance(entry, dict):
            raise ValueError("invalid context node")
        identity = entry.get("id")
        row = db.execute("SELECT kind,path,name,line,end_line,source_sha256 FROM nodes WHERE id=?",
                         (identity,)).fetchone()
        if row is None:
            raise ValueError("unknown context node")
        kind, path, name, start, end, sha = row
        if any(entry.get(field) != value for field, value in
               (("kind", kind), ("path", path), ("name", name), ("line", start),
                ("end_line", end), ("source_sha256", sha)) if field in entry):
            raise ValueError("context node provenance mismatch")
        source_row = db.execute("SELECT text FROM source_text WHERE path=?", (path,)).fetchone()
        if source_row is None or not isinstance(entry.get("source_slice"), str):
            raise ValueError("context source not available")
        text = source_row[0]
        lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", text)
        slice_start = entry.get("slice_start_line", start)
        slice_end = entry.get("slice_end_line", end)
        if (type(slice_start) is not int or type(slice_end) is not int or
                not start <= slice_start <= slice_end <= end or
                "".join(lines[slice_start - 1:slice_end]) != entry["source_slice"]):
            raise ValueError("context source slice differs from immutable graph")
        if path not in rows:
            rows[path] = (sha, text, lines, set())
        elif rows[path][0] != sha:
            raise ValueError("mixed source revisions")
        rows[path][3].update(range(slice_start, slice_end + 1))
        scopes.setdefault(path, []).append((kind, name, start, end, identity))

    pending = []
    for path, (sha, text, lines, covered) in rows.items():
        tree = ast.parse(text, filename=path)
        selected_scopes = scopes[path]
        module_selected = any(kind in ("file", "module") for kind, _, _, _, _ in selected_scopes)
        for symbol, function in _definitions(tree):
            identity = f"function:{path}:{symbol}:{function.lineno}"
            enclosing = [(kind, scope_id) for kind, name, start, end, scope_id in selected_scopes
                         if start <= function.lineno <= end and
                         (identity == scope_id or symbol.startswith(name + "."))]
            if not module_selected and not enclosing:
                continue
            explicitly_supplied = module_selected or any(
                kind == "class" or scope_id == identity for kind, scope_id in enclosing)
            direct = list(_direct_nodes(function))
            for node in direct:
                kind = _STATEMENTS.get(type(node))
                if kind is None:
                    continue
                unit_id = _id(path, sha, symbol, kind, node)
                syntax_node = _condition(node) or node
                syntax = ("try:" if isinstance(node, (ast.Try, ast.TryStar)) and
                          _verified_span(lines, covered, node) else
                          _syntax(text, lines, covered, syntax_node))
                visible = _verified_span(lines, covered, node) and syntax is not None
                reason = ("nested_definition" if not explicitly_supplied else
                          "outside_transmitted_source_slice" if not visible else None)
                item = {"id": unit_id, "symbol": symbol, "path": path, "kind": kind,
                        **_coords(node), "syntax": syntax} if reason is None else None
                if item is not None and isinstance(node, (ast.Try, ast.TryStar)):
                    item["finally"] = _finally_location(node, lines)
                pending.append((path, symbol, identity, node, unit_id, item, reason))
                if level == "cards" and isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                    card_id = _id(path, sha, symbol, "loop_card", node)
                    card = ({"id": card_id, "symbol": symbol, "path": path,
                             "kind": "loop_card", **_coords(node),
                             **_card(text, lines, covered, node, direct)}
                            if reason is None else None)
                    pending.append((path, symbol, identity, node, card_id, card, reason))

    def priority(record):
        path, symbol, identity, node, unit_id, _, _ = record
        preferred = selected_symbol is not None and selected_symbol in (symbol, identity)
        return (not preferred, path, symbol, node.lineno, node.col_offset,
                node.end_lineno, node.end_col_offset, unit_id)

    result = {"level": level, "extracted_ids": [], "delivered": [],
              "omitted": [], "unlisted_count": len(pending), "source_bytes": 0}
    if _packed_size(result) > max_bytes:
        raise ValueError("max_bytes cannot fit the review-unit inventory envelope")
    ordered = sorted(pending, key=priority)
    skipped = 0
    for index, (_, _, _, _, unit_id, item, reason) in enumerate(ordered):
        # Reserve space for the largest possible remaining overflow count.
        remaining = len(ordered) - index - 1
        result["extracted_ids"].append(unit_id)
        result["unlisted_count"] = skipped + remaining
        if reason is None:
            result["delivered"].append(item)
            if _packed_size(result) <= max_bytes:
                continue
            result["delivered"].pop()
            reason = "budget"
        result["omitted"].append({"id": unit_id, "reason": reason})
        if _packed_size(result) <= max_bytes:
            continue
        result["omitted"].pop()
        result["extracted_ids"].pop()
        skipped += 1
        result["unlisted_count"] = skipped + remaining
    _packed_size(result)
    return result
