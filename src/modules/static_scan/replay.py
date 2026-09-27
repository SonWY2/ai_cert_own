"""Opt-in clean-full replay of immutable static parser facts only.

This does not compare graph-derived Findings, reports, cost, or elapsed time.
"""

from pathlib import Path

from .cache import FactsCache
from .orchestrator import git, scan


def replay(repo: Path, revision: str, cache: FactsCache) -> tuple[dict, dict]:
    """Compare cached and clean scans at one frozen commit; return clean on mismatch.

    Metadata contains status, commit, cached per-file events and disabled_reason.
    The cache directory must be outside the target repository so the persistent
    disable marker cannot modify the source repository.
    """
    root = (Path(git(repo, "rev-parse", "--absolute-git-dir").decode().strip()).resolve()
            if git(repo, "rev-parse", "--is-bare-repository").strip() == b"true"
            else Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve())
    directory = cache.directory.resolve()
    if directory == root or root in directory.parents:
        raise ValueError("Replay cache directory must be outside the repository")
    commit = git(repo, "rev-parse", "--verify", "--end-of-options",
                 f"{revision}^{{commit}}").decode().strip()
    cached = scan(repo, commit, cache=cache)
    events = list(cache.events)
    clean = scan(repo, commit)
    if cache.disabled_reason is not None:
        return clean, {"status": "disabled", "commit": commit,
                       "cache_events": events, "disabled_reason": cache.disabled_reason}
    # The scan result contains precisely the canonical commit, parser, ordered
    # paths, source hashes, blob OIDs and parser facts; no timing/cost fields.
    if cached != clean:
        cache.disable()
        return clean, {"status": "mismatch", "commit": commit,
                       "cache_events": events, "disabled_reason": cache.disabled_reason}
    return cached, {"status": "match", "commit": commit,
                    "cache_events": events, "disabled_reason": None}
