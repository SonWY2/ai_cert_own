"""Read tracked Python blobs at an immutable Git commit without executing them."""

import argparse
import ast
import hashlib
import io
import json
import subprocess
import symtable
import sys
import tokenize
from pathlib import Path

if __package__:
    from .cache import FactsCache
    from .code_graph import SOURCE_BYTE_BUDGET, build_graph, context
else:
    from cache import FactsCache
    from code_graph import SOURCE_BYTE_BUDGET, build_graph, context


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def symbols(tree: ast.AST) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []

    class Collector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.record(node, "class")

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.record(node, "function")

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.record(node, "async_function")

        def record(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
            self.scope.append(node.name)
            found.append({"name": ".".join(self.scope), "kind": kind, "line": node.lineno,
                          "end_line": node.end_lineno})
            self.generic_visit(node)
            self.scope.pop()

    Collector().visit(tree)
    return found


def file_facts(path: str, content: bytes, oid: str) -> dict[str, object]:
    record: dict[str, object] = {
        "path": path,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "blob_oid": oid,
    }
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(content).readline)
        text = content.decode(encoding)
        tree = ast.parse(text, filename=path)
        table = symtable.symtable(text, path, "exec")
    except (UnicodeDecodeError, SyntaxError, LookupError) as error:
        record["parse_error"] = str(error)
    else:
        record["symbols"] = symbols(tree)
        record["symbol_table_names"] = sorted(table.get_identifiers())
        imports: set[str] = set()
        flags = dict.fromkeys(("await", "task_creation", "try", "context_manager",
                               "raise", "return", "decorator"), False)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
            if isinstance(node, ast.Await):
                flags["await"] = True
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                flags["task_creation"] |= node.func.attr in ("create_task", "ensure_future")
            elif isinstance(node, (ast.Try, ast.TryStar)):
                flags["try"] = True
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                flags["context_manager"] = True
            elif isinstance(node, ast.Raise):
                flags["raise"] = True
            elif isinstance(node, ast.Return):
                flags["return"] = True
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                flags["decorator"] |= bool(node.decorator_list)
        record["imports"] = sorted(imports)
        record["flags"] = flags
    return record


def scan(repo: Path, revision: str, *, cache: FactsCache | None = None) -> dict[str, object]:
    disabled_reason = cache.disabled_reason if cache is not None else None
    if cache is not None:
        cache.events.clear()
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").decode().strip()
    entries = git(repo, "ls-tree", "-rz", "--full-tree", commit)
    source_root = (git(repo, "rev-parse", "--absolute-git-dir").decode().strip()
                   if cache is not None and disabled_reason is None else None)
    files: list[dict[str, object]] = []

    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split(b" ")
        if mode not in (b"100644", b"100755") or kind != b"blob" or not name.endswith(b".py"):
            continue

        try:
            path = name.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Tracked Python path must be UTF-8") from error
        content = git(repo, "cat-file", "blob", oid.decode("ascii"))
        oid_text = oid.decode("ascii")
        if cache is None or disabled_reason is not None:
            record = file_facts(path, content, oid_text)
            if cache is not None:
                cache.events.append({"path": path, "origin": "disabled",
                                     "source_sha256": record["source_sha256"],
                                     "cache_key": None, "invalidation_reason": disabled_reason,
                                     "artifact_sha256": None})
        else:
            record = cache.facts(path, content, source_root, lambda: file_facts(path, content, oid_text))
            record = {**record, "blob_oid": oid_text}
        files.append(record)

    if not files:
        raise ValueError("No tracked Python source at this commit")
    return {"commit": commit, "python_parser": sys.version.split()[0], "files": files}




def graph(repo: Path, revision: str, *, cache: FactsCache | None = None):
    """Return the frozen scan and its typed, in-memory SQLite graph."""
    result = scan(repo, revision, cache=cache)
    return result, build_graph(result, lambda oid: git(repo, "cat-file", "blob", oid))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("revision", help="Git commit or ref to freeze before reading")
    parser.add_argument("--node", help="Retrieve context around a graph node ID")
    parser.add_argument("--hops", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--source-byte-budget", type=int, help="Maximum UTF-8 source slice bytes in graph context")
    args = parser.parse_args()
    try:
        if args.source_byte_budget is not None and not args.node:
            raise ValueError("--source-byte-budget requires --node")
        if args.node:
            result, database = graph(args.repository, args.revision)
            result = {"commit": result["commit"], "context": context(database, args.node, args.hops, args.limit,
                       source_byte_budget=args.source_byte_budget if args.source_byte_budget is not None else SOURCE_BYTE_BUDGET)}
        else:
            result = scan(args.repository, args.revision)
    except (subprocess.CalledProcessError, ValueError) as error:
        parser.exit(2, f"scan rejected: {error}\n")
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
