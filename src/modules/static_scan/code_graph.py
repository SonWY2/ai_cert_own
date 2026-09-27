"""Conservative, immutable-blob-backed Python code graph."""

import ast
import hashlib
import io
import sqlite3
import re
import tokenize
from typing import Callable


SOURCE_BYTE_BUDGET = 24_000


SCHEMA = """
CREATE TABLE nodes(id TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL,
                  name TEXT NOT NULL, line INTEGER NOT NULL, end_line INTEGER NOT NULL,
                  source_sha256 TEXT NOT NULL, blob_oid TEXT NOT NULL);
CREATE TABLE source_text(path TEXT PRIMARY KEY, text TEXT NOT NULL);
CREATE TABLE edges(source TEXT NOT NULL REFERENCES nodes(id), target TEXT NOT NULL,
                   kind TEXT NOT NULL CHECK(kind IN ('defines','imports','calls','inherits')),
                   state TEXT NOT NULL CHECK(state IN ('resolved','unknown')),
                   reference TEXT NOT NULL,
                   UNIQUE(source,target,kind,state,reference));
CREATE INDEX edges_target ON edges(target,kind,source);
"""


def module_name(path: str) -> str:
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def build_graph(scan_result: dict, blob_reader: Callable[[str], bytes]) -> sqlite3.Connection:
    """Build an in-memory graph; blob_reader accepts only OIDs from the frozen scan."""
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    trees: dict[str, ast.Module] = {}
    modules: dict[str, str | None] = {}
    top: dict[str, dict[str, list[str]]] = {}
    function_nodes: dict[str, list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]] = {}
    records = sorted(scan_result["files"], key=lambda item: item["path"])
    for record in records:
        path = record["path"]
        raw = blob_reader(record["blob_oid"])
        if hashlib.sha256(raw).hexdigest() != record["source_sha256"]:
            raise ValueError(f"Git blob hash mismatch: {path}")
        module = module_name(path)
        node_id = f"file:{path}"
        physical_lines = len(re.findall(rb"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", raw))
        db.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                   (node_id, "file", path, path, 1, max(1, physical_lines),
                    record["source_sha256"], record["blob_oid"]))
        if "parse_error" in record:
            continue
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        text = raw.decode(encoding)
        tree = ast.parse(text, filename=path)
        trees[path] = tree
        db.execute("INSERT INTO source_text VALUES (?,?)", (path, text))
        module_id = f"module:{path}"
        db.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                   (module_id, "module", path, module, 1, max(1, physical_lines),
                    record["source_sha256"], record["blob_oid"]))
        db.execute("INSERT INTO edges VALUES (?,?,?,?,?)",
                   (node_id, module_id, "defines", "resolved", module))
        modules[module] = module_id if module not in modules else None
        top[path] = {}
        conditional_names: set[str] = set()
        function_nodes[path] = []

        def visit_definitions(body: list[ast.stmt], parent: str, prefix: str,
                              unconditional: bool = False) -> None:
            for statement in body:
                if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    kind = "class" if isinstance(statement, ast.ClassDef) else "function"
                    qualified = f"{prefix}.{statement.name}" if prefix else statement.name
                    identity = f"{kind}:{path}:{qualified}:{statement.lineno}"
                    start = min(decorator.lineno for decorator in statement.decorator_list) if statement.decorator_list else statement.lineno
                    db.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                               (identity, kind, path, qualified, start, statement.end_lineno,
                                record["source_sha256"], record["blob_oid"]))
                    db.execute("INSERT INTO edges VALUES (?,?,?,?,?)",
                               (parent, identity, "defines", "resolved", qualified))
                    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        function_nodes[path].append((statement, identity))
                    if not prefix:
                        if unconditional:
                            top[path].setdefault(statement.name, []).append(identity)
                        else:
                            conditional_names.add(statement.name)
                    visit_definitions(statement.body, identity, qualified)
                elif isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While,
                                            ast.With, ast.AsyncWith, ast.Try, ast.TryStar, ast.Match)):
                    for field in ("body", "orelse", "finalbody"):
                        visit_definitions(getattr(statement, field, []), parent, prefix)
                    if isinstance(statement, (ast.Try, ast.TryStar)):
                        for handler in statement.handlers:
                            visit_definitions(handler.body, parent, prefix)
                    elif isinstance(statement, ast.Match):
                        for case in statement.cases:
                            visit_definitions(case.body, parent, prefix)

        visit_definitions(tree.body, module_id, "", unconditional=True)
        for name in conditional_names:
            top[path].pop(name, None)

    def edge(source: str, reference: str, kind: str, target: str | None = None) -> None:
        db.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?)",
                   (source, target or "", kind, "resolved" if target else "unknown", reference))

    for path, tree in trees.items():
        # Top-level rebinding makes lexical names ambiguous across the module.
        rebound = set()
        for statement in tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if statement.decorator_list:
                    rebound.add(statement.name)
                for node in ast.walk(statement):
                    if isinstance(node, ast.Global):
                        rebound.update(node.names)
                continue
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                    rebound.add(node.id)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                        rebound.update(top[path])
                    else:
                        rebound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        for name in rebound:
            top[path].pop(name, None)

    for path, tree in trees.items():
        module_id = f"module:{path}"
        package = module_name(path).split(".")
        if not path.endswith("/__init__.py"):
            package.pop()
        for statement in tree.body:
            if isinstance(statement, ast.Import):
                names = [alias.name for alias in statement.names]
            elif isinstance(statement, ast.ImportFrom):
                base = package[:max(0, len(package) - statement.level + 1)] if statement.level else []
                prefix = ".".join(base + ([statement.module] if statement.module else []))
                names = [prefix] + [f"{prefix}.{alias.name}" for alias in statement.names]
            else:
                continue
            for name in names:
                target = modules.get(name)
                if target is None and isinstance(statement, ast.ImportFrom) and name != prefix:
                    imported = modules.get(prefix)
                    if imported:
                        candidates = top[imported.removeprefix("module:")].get(
                            name.rpartition(".")[2], [])
                        if len(candidates) == 1 and candidates[0].startswith("class:"):
                            target = candidates[0]
                if name != module_name(path):
                    edge(module_id, name, "imports", target)
                parts = name.split(".")
                for depth in range(1, len(parts)):
                    parent_name = ".".join(parts[:depth])
                    parent = modules.get(parent_name)
                    if parent and parent != module_id:
                        edge(module_id, parent_name, "imports", parent)

        def record_calls(statement, source, resolve):
            local = set()
            if resolve:
                local.update(arg.arg for arg in statement.args.posonlyargs)
                local.update(arg.arg for arg in statement.args.args + statement.args.kwonlyargs)
                if statement.args.vararg:
                    local.add(statement.args.vararg.arg)
                if statement.args.kwarg:
                    local.add(statement.args.kwarg.arg)
                for node in ast.walk(statement):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                        local.add(node.id)
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        local.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, (ast.Global, ast.Nonlocal)):
                        local.update(node.names)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not statement:
                        local.add(node.name)

            class DirectCalls(ast.NodeVisitor):
                def visit_FunctionDef(self, node):
                    if node is statement:
                        for child in node.body:
                            self.visit(child)

                visit_AsyncFunctionDef = visit_FunctionDef

                def visit_ClassDef(self, node):
                    pass

                def visit_ListComp(self, node):
                    pass

                visit_SetComp = visit_ListComp
                visit_DictComp = visit_ListComp
                visit_GeneratorExp = visit_ListComp

                def visit_Lambda(self, node):
                    pass

                def visit_Call(self, node):
                    reference = ast.unparse(node.func)
                    target = None
                    if resolve and isinstance(node.func, ast.Name):
                        name = node.func.id
                        if name not in local and len(bindings.get(name, [])) == 1:
                            candidate = bindings[name][0]
                            if candidate.startswith("function:") and candidate != source:
                                target = candidate
                    edge(source, reference, "calls", target)
                    self.generic_visit(node)

            DirectCalls().visit(statement)

        # Name resolution is limited to unambiguous top-level definitions. Any local
        # binding, global rebinding, import or nested definition makes a call unknown.
        bindings = top[path]
        resolved_functions = set()
        for statement in tree.body:
            if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            candidates = bindings.get(statement.name, [])
            if len(candidates) != 1:
                continue
            source = candidates[0]
            if isinstance(statement, ast.ClassDef):
                for base in statement.bases:
                    if isinstance(base, ast.Name):
                        targets = bindings.get(base.id, [])
                        target = targets[0] if len(targets) == 1 and targets[0].startswith("class:") else None
                        edge(source, base.id, "inherits", target if target != source else None)
                    else:
                        edge(source, ast.unparse(base), "inherits")
                continue
            record_calls(statement, source, True)
            resolved_functions.add(source)
        for statement, source in function_nodes[path]:
            if source not in resolved_functions:
                record_calls(statement, source, False)
    db.commit()
    return db


def _render_context(
    db: sqlite3.Connection, selected: list[str], distances: dict[str, int],
    source_byte_budget: int,
) -> tuple[list[dict], bool, int]:
    """Emit complete source slices greedily within a UTF-8 byte budget."""
    nodes = []
    sources: dict[str, list[str]] = {}
    emitted_source_bytes = 0
    budget_truncated = False
    for identity in selected:
        kind, path, name, line, end_line, digest, blob = db.execute(
            "SELECT kind,path,name,line,end_line,source_sha256,blob_oid FROM nodes WHERE id=?", (identity,)
        ).fetchone()
        if path not in sources:
            row = db.execute("SELECT text FROM source_text WHERE path=?", (path,)).fetchone()
            sources[path] = re.findall(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$", row[0]) if row else []
        snippet = "".join(sources[path][line - 1:end_line])
        size = len(snippet.encode("utf-8"))
        if size > source_byte_budget - emitted_source_bytes:
            budget_truncated = True
            continue
        emitted_source_bytes += size
        nodes.append(dict(id=identity, kind=kind, path=path, name=name, line=line,
                          end_line=end_line, source_sha256=digest, blob_oid=blob,
                          source_slice=snippet, distance=distances[identity]))
    return nodes, budget_truncated, emitted_source_bytes


def context(db: sqlite3.Connection, node_id: str, hops: int = 1, limit: int = 50,
            *, source_byte_budget: int = SOURCE_BYTE_BUDGET) -> dict:
    """Return deterministic, bounded bidirectional 0/1/2-hop context with a source byte budget."""
    if hops not in (0, 1, 2) or limit < 1 or limit > 500:
        raise ValueError("hops must be 0, 1 or 2; limit must be between 1 and 500")
    if type(source_byte_budget) is not int or source_byte_budget < 1:
        raise ValueError("source_byte_budget must be a positive integer")
    if db.execute("SELECT 1 FROM nodes WHERE id=?", (node_id,)).fetchone() is None:
        raise ValueError(f"Unknown graph node: {node_id}")
    distances = {node_id: 0}
    frontier = {node_id}
    for depth in range(1, hops + 1):
        next_nodes = set()
        for current in sorted(frontier):
            for source, target in db.execute(
                "SELECT source,target FROM edges WHERE (source=? OR target=?) AND state='resolved' ORDER BY kind,source,target",
                (current, current),
            ):
                other = target if source == current else source
                if other not in distances:
                    next_nodes.add(other)
        for other in next_nodes:
            distances[other] = depth
        frontier = next_nodes
    selected = sorted(distances, key=lambda item: (distances[item], item))[:limit]
    nodes, budget_truncated, source_bytes = _render_context(db, selected, distances, source_byte_budget)
    chosen = {node["id"] for node in nodes}
    edges = [dict(source=source, target=target, kind=kind, state=state, reference=reference)
             for source, target, kind, state, reference in db.execute(
                 "SELECT source,target,kind,state,reference FROM edges ORDER BY source,kind,reference,target"
             ) if source in chosen and (not target or target in chosen)]
    return {"nodes": nodes, "edges": edges,
            "truncated": len(distances) > limit or budget_truncated, "source_bytes": source_bytes}
