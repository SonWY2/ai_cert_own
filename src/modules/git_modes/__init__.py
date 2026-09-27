"""Immutable Git revision selection and conservative Python impact planning."""

from pathlib import Path

from modules.static_scan.orchestrator import git, graph


def _commit(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode("ascii").strip()


def _paths(db) -> set[str]:
    return {row[0] for row in db.execute("SELECT path FROM nodes WHERE kind='file'")}


def _dependents(db, changed: set[str]) -> set[str]:
    """Follow only resolved incoming graph edges, including definitions within files."""
    seeds = set()
    for path in sorted(changed):
        seeds.update(row[0] for row in db.execute("SELECT id FROM nodes WHERE path=?", (path,)))
    visited = set(seeds)
    frontier = seeds
    while frontier:
        incoming = set()
        for node in frontier:
            incoming.update(row[0] for row in db.execute(
                "SELECT source FROM edges WHERE target=? AND state='resolved'", (node,)))
        frontier = incoming - visited
        visited.update(frontier)
    paths = set()
    for node in visited:
        paths.add(db.execute("SELECT path FROM nodes WHERE id=?", (node,)).fetchone()[0])
    return paths


def _diff(repo: Path, base: str, target: str) -> tuple[set[str], set[str]]:
    records = git(repo, "diff", "--name-status", "-z", "--find-renames", base, target, "--").split(b"\0")
    changed: set[str] = set()
    deleted: set[str] = set()
    index = 0
    while index < len(records) and records[index]:
        status = records[index].decode("ascii")
        index += 1
        count = 2 if status.startswith(("R", "C")) else 1
        names = [records[index + offset].decode("utf-8", "surrogateescape") for offset in range(count)]
        index += count
        for name in names:
            if name.endswith(".py"):
                changed.add(name)
        if status.startswith(("D", "R")) and names[0].endswith(".py"):
            deleted.add(names[0])
    return changed, deleted


def plan_main(repo: Path, main_ref: str, previous_accepted_sha: str | None = None) -> dict:
    """Plan a scheduled full scan, skipping only an already accepted identical commit."""
    target = _commit(repo, main_ref)
    previous = _commit(repo, previous_accepted_sha) if previous_accepted_sha is not None else None
    if previous_accepted_sha is not None and previous_accepted_sha != previous:
        raise ValueError("Previous accepted revision must be a full immutable commit SHA")
    if previous == target:
        return dict(mode="main", base_sha=previous, target_sha=target, skipped=True,
                    scope="none", observed_target_paths=[], omitted_unknown_paths=[],
                    coverage="same_sha_skipped")
    result, db = graph(repo, target)
    try:
        paths = sorted(_paths(db))
    finally:
        db.close()
    return dict(mode="main", base_sha=previous, target_sha=result["commit"], skipped=False,
                scope="full", observed_target_paths=paths, omitted_unknown_paths=[],
                coverage="tracked_python_full; unresolved_graph_references_and_non_python_outside_scope")


def plan_candidate(repo: Path, main_ref: str, candidate_ref: str, scope: str = "impact") -> dict:
    """Plan a candidate against its merge base without reading the working tree."""
    if scope not in ("impact", "full"):
        raise ValueError("scope must be 'impact' or 'full'")
    main = _commit(repo, main_ref)
    target = _commit(repo, candidate_ref)
    base = git(repo, "merge-base", main, target).decode("ascii").strip()
    if not base:
        raise ValueError("No merge base between main and candidate")
    target_result, target_db = graph(repo, target)
    try:
        target_paths = _paths(target_db)
        if scope == "full":
            return dict(mode="candidate", base_sha=base, target_sha=target_result["commit"],
                        scope=scope, observed_target_paths=sorted(target_paths),
                        omitted_unknown_paths=[], coverage="tracked_python_full; unresolved_graph_references_and_non_python_outside_scope")
        changed, deleted = _diff(repo, base, target)
        try:
            _, base_db = graph(repo, base)
        except ValueError as error:
            if str(error) != "No tracked Python source at this commit":
                raise
            base_db = None
        try:
            base_paths = _paths(base_db) if base_db is not None else set()
            relevant = changed & (base_paths | target_paths)
            base_affected = _dependents(base_db, relevant & base_paths) if base_db is not None else set()
            affected = relevant | base_affected | _dependents(target_db, relevant & target_paths)
            observed = affected & target_paths
            omitted = (target_paths - observed) | (deleted - target_paths) | (changed - base_paths - target_paths)
            return dict(mode="candidate", base_sha=base, target_sha=target_result["commit"],
                        scope=scope, observed_target_paths=sorted(observed), omitted_unknown_paths=sorted(omitted),
                        coverage="partial_resolved_reverse_graph_both_revisions; deleted_paths_have_no_target_blob; unresolved_references_and_non_python_outside_scope")
        finally:
            if base_db is not None:
                base_db.close()
    finally:
        target_db.close()
