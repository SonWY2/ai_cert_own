"""Select caller hypotheses without treating a partial Git graph as complete.

The caller must calculate the plan with plan_main/plan_candidate against Git and
supply the output of verify_source_run. This pure boundary checks consistency,
not the authenticity of a caller-supplied plan or the truth of a hypothesis.
"""

import re
from pathlib import Path

from modules.git_modes import plan_candidate, plan_main

_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _path(value):
    if (not isinstance(value, str) or not value or value.startswith("/") or
            "\x00" in value or
            any(part in ("", ".", "..") for part in value.split("/"))):
        raise ValueError("Invalid source path")
    return value


def _paths(value, field):
    if not isinstance(value, list) or any(not isinstance(path, str) for path in value):
        raise ValueError(f"Invalid {field}")
    paths = [_path(path) for path in value]
    if paths != sorted(set(paths)):
        raise ValueError(f"{field} must be sorted and unique")
    return set(paths)


def select_candidates(verified_source_run, calculated_git_plan, caller_candidates):
    """Return observed hypotheses and UNKNOWN omitted paths; never resolve absence.

    A full scope means all tracked Python target files were selected, not that
    unresolved graph references or non-Python sources were checked.
    """
    if not isinstance(verified_source_run, dict) or not isinstance(calculated_git_plan, dict):
        raise ValueError("Verified source run and calculated plan must be objects")
    run = verified_source_run.get("run")
    evidence = verified_source_run.get("evidence")
    if not isinstance(run, dict) or not isinstance(evidence, list):
        raise ValueError("Invalid verified source inventory")
    target = run.get("commit")
    if (not isinstance(target, str) or not _OID.fullmatch(target) or
            calculated_git_plan.get("target_sha") != target):
        raise ValueError("Source run target SHA does not match Git plan")
    inventory = []
    for record in evidence:
        if not isinstance(record, dict) or record.get("commit") != target:
            raise ValueError("Invalid source evidence")
        inventory.append(_path(record.get("path")))
    target_paths = set(inventory)
    if not target_paths or len(target_paths) != len(inventory):
        raise ValueError("Invalid or duplicate source inventory paths")

    plan = calculated_git_plan
    mode, scope, skipped = plan.get("mode"), plan.get("scope"), plan.get("skipped", False)
    if mode not in ("main", "candidate") or type(skipped) is not bool:
        raise ValueError("Invalid Git plan mode or skipped flag")
    if mode == "main" and ("skipped" not in plan or
                           scope != ("none" if skipped else "full")):
        raise ValueError("Invalid main plan scope")
    if mode == "candidate" and ("skipped" in plan or scope not in ("impact", "full")):
        raise ValueError("Invalid candidate plan scope")
    observed = _paths(plan.get("observed_target_paths"), "observed target paths")
    omitted = _paths(plan.get("omitted_unknown_paths"), "omitted unknown paths")
    if observed - target_paths or observed & omitted:
        raise ValueError("Observed paths must be distinct tracked target sources")
    if skipped:
        if observed or omitted or plan.get("base_sha") != target:
            raise ValueError("Skipped plan must have identical SHA and empty scope")
    elif scope == "full":
        if observed != target_paths or omitted:
            raise ValueError("Full plan must cover exactly the target inventory")
    elif not target_paths - observed <= omitted:
        raise ValueError("Impact plan must report every unobserved target path")

    if not isinstance(caller_candidates, (list, tuple)):
        raise ValueError("Candidates must be a sequence")
    selected = []
    unknown = set(omitted)
    for candidate in caller_candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("location"), dict):
            raise ValueError("Candidate requires a location")
        location = candidate["location"]
        path = _path(location.get("path"))
        line = location.get("line")
        end_line = location.get("end_line", line)
        if (type(line) is not int or line < 1 or type(end_line) is not int or
                end_line < line):
            raise ValueError("Candidate requires a valid positive line range")
        if path in observed:
            selected.append(candidate)
        elif path in target_paths or path in omitted:
            unknown.add(path)
        else:
            raise ValueError("Candidate path is outside target inventory and plan omissions")
    return {"observed_candidates": selected, "omitted_unknown_paths": sorted(unknown),
            "coverage": plan.get("coverage")}


def plan_for_review(verified_source_run, main_ref=None, candidate_ref=None, scope=None,
                    previous_sha=None):
    """Calculate a Git-backed plan only when the caller selects a scan mode."""
    if main_ref is None:
        if candidate_ref is not None or scope is not None:
            raise ValueError("Candidate and scope require a main reference")
        return None
    repository = Path(verified_source_run["run"]["repository"])
    if candidate_ref is None:
        if scope is not None:
            raise ValueError("Main scan is always full")
        return plan_main(repository, main_ref, previous_sha)
    return plan_candidate(repository, main_ref, candidate_ref, scope=scope or "impact")
