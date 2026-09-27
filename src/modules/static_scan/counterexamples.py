"""Bounded boundary probes from frozen Python AST and resolved local calls.

These are counterexamples to check, not confirmed defects or proof that zero
or an empty collection is valid input. Only straight-line expressions and
early terminating guards count.
"""

import ast
import sqlite3


_OPERATORS = (ast.Div, ast.FloorDiv, ast.Mod)
_KINDS = ("zero_denominator", "empty_index")


def _parameters(fn):
    return [arg.arg for arg in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]


def _unchanged(fn, name):
    return not any(isinstance(node, ast.Name) and node.id == name and
                   isinstance(node.ctx, (ast.Store, ast.Del))
                   for statement in fn.body for node in ast.walk(statement))


def _boundary_exits(statement, name, kind):
    if not isinstance(statement, ast.If) or not statement.body or not isinstance(
            statement.body[-1], (ast.Return, ast.Raise)):
        return False
    test = statement.test
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return isinstance(test.operand, ast.Name) and test.operand.id == name
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    right = test.comparators[0]
    if kind == "empty_index":
        return (isinstance(test.ops[0], ast.Eq) and isinstance(right, ast.List)
                and not right.elts and isinstance(test.left, ast.Name)
                and test.left.id == name)
    return (isinstance(test.ops[0], (ast.Eq, ast.LtE, ast.GtE))
            and isinstance(test.left, ast.Name) and test.left.id == name
            and isinstance(right, ast.Constant) and type(right.value) in (int, float)
            and right.value == 0)


def _expression(statement):
    if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return statement.value
    if isinstance(statement, (ast.Return, ast.Expr)):
        return statement.value
    return None


def _probes(node):
    # Conditional and deferred expressions need path reasoning we do not claim.
    if isinstance(node, (ast.IfExp, ast.BoolOp, ast.Lambda, ast.ListComp,
                         ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return
    if isinstance(node, ast.BinOp) and isinstance(node.op, _OPERATORS):
        if isinstance(node.right, ast.Name):
            yield "zero_denominator", node.right.id, node.lineno
    elif (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
          and isinstance(node.slice, ast.Constant) and type(node.slice.value) is int):
        yield "empty_index", node.value.id, node.lineno
    for child in ast.iter_child_nodes(node):
        yield from _probes(child)


def _sinks(fn):
    stable = {name for name in _parameters(fn) if _unchanged(fn, name)}
    guarded = {kind: set() for kind in _KINDS}
    for statement in fn.body:
        for kind in _KINDS:
            guarded[kind].update(name for name in stable
                                 if _boundary_exits(statement, name, kind))
        expression = _expression(statement)
        if expression is None:
            continue
        for kind, name, line in _probes(expression):
            if name in stable and name not in guarded[kind]:
                yield kind, name, line


def _argument(call, fn, name):
    positional = [arg.arg for arg in fn.args.posonlyargs + fn.args.args]
    if name in positional:
        index = positional.index(name)
        if index < len(call.args):
            return call.args[index]
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def counterexamples(db: sqlite3.Connection, nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Return at most eight source-located probes; never import or run target code."""
    if not nodes:
        return []
    selected = {node["id"]: node for node in nodes}
    roots = [node for node in nodes if node["kind"] == "function" and
             (node["distance"] == 0 or node["distance"] == 1 and
              any(root["kind"] == "module" and root["distance"] == 0 and
                  root["path"] == node["path"] for root in nodes))]
    if not roots:
        return []

    definitions = {}
    for path in sorted({node["path"] for node in nodes}):
        row = db.execute("SELECT text FROM source_text WHERE path=?", (path,)).fetchone()
        if row is None:
            continue
        tree = ast.parse(row[0], filename=path)
        for fn in tree.body:
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions[(path, fn.name, fn.end_lineno)] = fn

    def definition(node):
        if node["kind"] != "function" or "." in node["name"]:
            return None
        return definitions.get((node["path"], node["name"], node["end_line"]))

    calls = {}
    for edge in edges:
        if (edge["kind"] == "calls" and edge["state"] == "resolved"
                and edge["source"] in selected and edge["target"] in selected):
            calls.setdefault(edge["source"], []).append(selected[edge["target"]])

    results = []
    seen = set()
    for entry in roots:
        fn = definition(entry)
        if fn is None:
            continue
        for kind, name, line in _sinks(fn):
            key = (entry["id"], entry["id"], kind, name)
            if key not in seen:
                results.append({"kind": kind, "status": "static_hypothesis",
                                "path": entry["path"], "entry_symbol": entry["name"],
                                "entry_line": fn.lineno, "parameter": name,
                                "input_value": 0 if kind == "zero_denominator" else [],
                                "call_line": None, "sink_symbol": entry["name"], "sink_line": line})
                seen.add(key)
        for statement in fn.body:
            expression = _expression(statement)
            if not isinstance(expression, ast.Call) or not isinstance(expression.func, ast.Name):
                continue
            for callee in calls.get(entry["id"], ()):
                helper = definition(callee)
                if (helper is None or helper.name != expression.func.id or
                        callee["path"] != entry["path"]):
                    continue
                for kind, parameter, line in _sinks(helper):
                    argument = _argument(expression, helper, parameter)
                    literal = ((kind == "zero_denominator" and isinstance(argument, ast.Constant)
                                and type(argument.value) in (int, float) and argument.value == 0)
                               or (kind == "empty_index" and isinstance(argument, ast.List)
                                   and not argument.elts))
                    name = argument.id if isinstance(argument, ast.Name) else None
                    if not literal and (name not in _parameters(fn) or
                                        not _unchanged(fn, name) or
                                        any(_boundary_exits(prior, name, kind) for prior in fn.body
                                            if prior.lineno < statement.lineno)):
                        continue
                    key = (entry["id"], callee["id"], kind, name)
                    if key not in seen:
                        results.append({"kind": kind, "status": "static_hypothesis",
                                        "path": entry["path"], "entry_symbol": entry["name"],
                                        "entry_line": fn.lineno, "parameter": name,
                                        "input_value": 0 if kind == "zero_denominator" else [],
                                        "call_line": expression.lineno,
                                        "sink_symbol": callee["name"], "sink_line": line})
                        seen.add(key)
        if len(results) >= 8:
            break
    return results[:8]
