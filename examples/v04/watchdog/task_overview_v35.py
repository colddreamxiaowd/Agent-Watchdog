"""Evidence-limited per-task overview. Never runs tests or attributes Git writes.
Human-approved session binding + contract + Git snapshot + saved test statuses.
"""
import json
from pathlib import Path

import evidence
import scope_guard
import session_binding_v34 as binding
import task_contract



# Conservative guard: a foreground observer should not hash multi-GB worktrees
# every polling cycle and interfere with a running coding agent.
MAX_FILES = 5000
MAX_SINGLE_FILE = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


def resource_preflight(repo):
    names = [x for x in evidence.git(repo,"ls-files","--cached","--others",
                                      "--exclude-standard","-z").split(b"\0") if x]
    if len(names) > MAX_FILES:
        return "TOO_MANY_GIT_VISIBLE_FILES"
    total = 0
    import os
    for raw in names:
        p = repo / os.fsdecode(raw)
        if p.is_symlink() or not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            return "FILE_STAT_UNAVAILABLE"
        if size > MAX_SINGLE_FILE:
            return "SINGLE_FILE_TOO_LARGE"
        total += size
        if total > MAX_TOTAL_BYTES:
            return "TOTAL_GIT_VISIBLE_FILES_TOO_LARGE"
    return None

def event_summary(events, entry):
    subset = []
    seen = set()
    for x in events:
        if x.get("source") != entry["source"] or x.get("session_id") != entry["session_id"]:
            continue
        key = x.get("event_id")
        if not isinstance(key, str) or not key or key in seen:
            continue
        seen.add(key)
        subset.append(x)
    finished = {}
    started = set()
    for x in subset:
        call = (x.get("turn_id"), x.get("tool_use_id"))
        if not (isinstance(call[1], str) and call[1] and
                isinstance(x.get("turn_id"), str) and x.get("linkable") is True):
            continue
        if x.get("phase") == "STARTED":
            started.add(call)
        if x.get("phase") == "FINISHED":
            value = x.get("outcome")
            if value in ("SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"):
                # Conflicting terminal projections cannot become success.
                if call in finished and finished[call] != value:
                    finished[call] = "CONFLICT"
                else:
                    finished[call] = value
    categories = {k: sum(v == k for v in finished.values())
                  for k in ("SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN", "CONFLICT")}
    return {"observed_events": len(subset), "started_calls": len(started),
            "finished_calls": len(finished), "outcomes": categories,
            "missing_terminal_calls": sum(c not in finished for c in started),
            "scope": "Session association only; no semantic task progress or source authentication"}


def single(entry, events, show_goal=False):
    alias = entry.get("alias", "invalid")
    result = {"session_alias": alias, "binding": "HUMAN_REVIEWED_UNAUTHENTICATED",
              "repo_path_echoed": False, "source_identity": "UNVERIFIED",
              "author_attribution": "UNKNOWN"}
    repo = evidence.root_for(entry["repo"])
    contract, approved, _, _ = task_contract.load(repo)
    current = task_contract.contract_hash(contract)
    if not approved or entry.get("contract_sha256") != current:
        return {**result, "state": "CONTRACT_CHANGED_OR_UNAPPROVED",
                "actions": ["REAPPROVE_AND_REBIND_MANUALLY"], "observations": event_summary(events, entry)}
    base = evidence.read_json(evidence.state_dir(repo) / "baseline.json")
    if (not isinstance(base, dict) or
        entry.get("baseline_snapshot") != base.get("snapshot_id")):
        return {**result, "state": "BASELINE_CHANGED",
                "actions": ["REVIEW_BASELINE_RESET_MANUALLY"], "observations": event_summary(events, entry)}
    resource_issue = resource_preflight(repo)
    if resource_issue:
        return {**result, "state": "RESOURCE_BOUND_REVIEW",
                "reason": resource_issue,
                "actions": ["REDUCE_SCAN_SCOPE_OR_USE_SMALL_TEST_REPOSITORY"],
                "observations": event_summary(events, entry)}
    checks = task_contract.acceptance_status(repo)
    scope = scope_guard.check(repo)
    findings = scope.get("findings", [])
    accept = checks["acceptance"]
    actions = []
    if findings:
        actions.append("REVIEW_GIT_SCOPE_NO_AUTHOR_ATTRIBUTION")
    if not checks.get("baseline_available"):
        actions.append("BASELINE_MISSING")
    if any(x in ("FAILED", "INCONCLUSIVE") for x in accept.values()):
        actions.append("REVIEW_FAILED_OR_INCONCLUSIVE_TEST")
    if any(x in ("NOT_TESTED", "STALE") for x in accept.values()):
        actions.append("RUN_APPROVED_TEST_MANUALLY")
    if checks.get("stage") == "VERIFIED_COMPLETE":
        actions.append("INDEPENDENT_CHECKS_PASSED_REVIEW_SEMANTIC_GOAL")
    if not actions:
        actions.append("CONTINUE_OBSERVING_NOT_PROVEN_COMPLETE")
    out = {**result, "state": "REVIEW_AVAILABLE",
           "contract_checks_stage": checks["stage"], "approved": approved,
           "scope_code": scope["status"],
           "scope_findings": [{k: f[k] for k in ("path", "code", "kind") if k in f} for f in findings],
           "acceptance": accept, "observations": event_summary(events, entry),
           "actions": actions,
           "note": "Git snapshot changes are not attributable to the Codex session; PASS is only specified checks"}
    if show_goal:
        out["goal"] = contract["goal"]
    return out


def overview(log=None, registry=None, show_goal=False):
    data = binding.read_registry(registry)
    events = binding.recent_events(log)
    reports = []
    for entry in data["bindings"]:
        try:
            reports.append(single(entry, events, show_goal))
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as err:
            reports.append({"session_alias": entry.get("alias", "invalid"),
                            "state": "UNAVAILABLE", "error_kind": type(err).__name__,
                            "actions": ["REVIEW_LOCAL_REGISTRY_AND_REPOSITORY"],
                            "source_identity": "UNVERIFIED"})
    return {"status": "READ_ONLY_TASK_OVERVIEW", "tasks": reports,
            "task_count": len(reports),
            "limits": "Only recent <=8MB redacted events; explicit binding not cryptographic; never starts tests"}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--log")
    p.add_argument("--registry")
    p.add_argument("--show-goal", action="store_true", help="Display private approved goal on local terminal")
    x = p.parse_args()
    print(json.dumps(overview(x.log, x.registry, x.show_goal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
