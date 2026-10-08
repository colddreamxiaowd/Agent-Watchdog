"""Chapter 25: bounded failure-sequence review without raw commands/prompts.
No inference that same tool type means same command or an ineffective loop.
"""
import argparse
import json
from collections import defaultdict
from execution_v2 import read_projected

RESULTS = {"FAILED", "SUCCEEDED", "CANCELLED", "UNKNOWN"}


def terminal_calls(rows):
    groups = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict) or row.get("linkable") is not True:
            continue
        if not all(isinstance(row.get(k), str) and row[k] for k in
                   ("source", "session_id", "tool_use_id")):
            continue
        if row.get("phase") != "FINISHED":
            continue
        key = (row["source"], row["session_id"], row.get("turn_id"), row["tool_use_id"])
        groups[key].append(row)
    output, conflicts = [], []
    for key, members in groups.items():
        terminal = {row.get("outcome") if row.get("outcome") in RESULTS else "UNKNOWN"
                    for row in members}
        # Even exact duplicate records must not create multiple failures.
        if len(terminal) > 1:
            conflicts.append({"source":key[0], "session_id":key[1],
                              "tool_use_id":key[3], "kind":"CONFLICTING_TERMINAL"})
            continue
        tools = {row.get("tool") for row in members}
        if len(tools) != 1:
            conflicts.append({"source":key[0], "session_id":key[1],
                              "tool_use_id":key[3], "kind":"CONFLICTING_TOOL_TYPE"})
            continue
        output.append({"source":key[0], "session_id":key[1], "turn_id":key[2],
                       "tool_use_id":key[3], "tool":next(iter(tools)),
                       "outcome":next(iter(terminal))})
    return output, conflicts


def diagnose(rows, intent_groups=None, min_failures=3):
    if type(min_failures) is not int or min_failures < 2:
        raise ValueError("min_failures must be >=2")
    calls, conflicts = terminal_calls(rows)
    buckets = defaultdict(list)
    for r in calls:
        buckets[(r["source"], r["session_id"], r["tool"])].append(r)
    signals = []
    for (source, session, tool), bunch in buckets.items():
        failures = [x for x in bunch if x["outcome"] == "FAILED"]
        if len(failures) >= min_failures:
            signals.append({"code":"FAILURE_CLUSTER_REVIEW", "source":source,
                            "session_id":session, "tool_category":tool,
                            "distinct_failed_calls":len(failures),
                            "confidence":"NOT_CALIBRATED",
                            "interpretation":"NOT_SAME_COMMAND_OR_NO_PROGRESS_PROOF"})
    # Optional manually reviewed same-intent grouping. It is an assertion, not
    # derived from the private command body nor an authenticated provenance.
    if intent_groups is not None:
        if not isinstance(intent_groups, dict) or intent_groups.get("schema_version") != 1:
            raise ValueError("manual groups need schema_version=1")
        known = {(c["source"], c["session_id"], c["turn_id"], c["tool_use_id"]):c
                 for c in calls}
        seen = set()
        for g in intent_groups.get("groups", []):
            if not isinstance(g, dict) or not isinstance(g.get("id"), str):
                raise ValueError("bad group")
            refs = g.get("calls")
            if not isinstance(refs, list) or len(refs) < 2:
                raise ValueError("group needs >=2 exact operation references")
            selected = []
            for ref in refs:
                if not isinstance(ref, dict):
                    raise ValueError("bad reference")
                key = (ref.get("source"), ref.get("session_id"), ref.get("turn_id"),
                       ref.get("tool_use_id"))
                if key not in known or key in seen:
                    raise ValueError("missing, conflicting, or duplicate operation reference")
                seen.add(key)
                selected.append(known[key])
            if len({(x["source"], x["session_id"]) for x in selected}) != 1:
                raise ValueError("cannot group different sessions/sources")
            failures = sum(x["outcome"] == "FAILED" for x in selected)
            successes = sum(x["outcome"] == "SUCCEEDED" for x in selected)
            signals.append({"code":"MANUAL_SAME_INTENT_REVIEW",
                            "group_id":g["id"], "source":selected[0]["source"],
                            "session_id":selected[0]["session_id"],
                            "failed_calls":failures, "succeeded_calls":successes,
                            "review_outcome":"POSSIBLE_RECOVERY" if successes else "REVIEW_ONLY",
                            "confidence":"HUMAN_GROUPING_UNAUTHENTICATED",
                            "interpretation":"NO_LOOP_OR_TASK_COMPLETION_CERTIFICATION"})
    return {"source":"sanitized_metadata_only", "calls":len(calls),
            "unknown_outcomes":sum(x["outcome"]=="UNKNOWN" for x in calls),
            "conflicts":conflicts, "signals":signals,
            "limits":"Same tool category is not same command; manual group does not prove futility."}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--events", required=True)
    p.add_argument("--manual-groups", help="Optional private reviewed JSON; no commands")
    p.add_argument("--min-failures", type=int, default=3)
    a=p.parse_args()
    groups=json.loads(open(a.manual_groups,encoding="utf-8").read()) if a.manual_groups else None
    print(json.dumps(diagnose(read_projected(a.events),groups,a.min_failures),indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
