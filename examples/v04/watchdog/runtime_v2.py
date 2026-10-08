"""Round 23: absence is uncertainty. Conservative state machine for sanitized events."""
import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from execution_v2 import read_projected


def moment(s):
    if not isinstance(s, str):
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except ValueError:
        return None


def diagnose(rows, now=None, stall_seconds=300, quiet_seconds=300, repeat_limit=3, failure_window_seconds=600):
    if stall_seconds < 1 or quiet_seconds < 1 or repeat_limit < 2 or failure_window_seconds < 1:
        raise ValueError("thresholds must be positive")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    calls = defaultdict(list)
    recent, invalid_time = [], 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        t = moment(row.get("received_at"))
        if t is None or t > now:
            invalid_time += 1
            continue
        recent.append((t, row))
        if (row.get("linkable") is True and row.get("session_id")
                and row.get("tool_use_id") and row.get("source")):
            key = (row["source"], row["session_id"], row.get("turn_id"),
                   row["tool_use_id"])
            calls[key].append((t, row))
    recent.sort(key=lambda x: x[0])
    incidents, closed_failures, active = [], [], []
    for key, observations in calls.items():
        observations.sort(key=lambda x: x[0])
        # Replay of the same normalized event is not a second failure.
        unique = {r.get("event_id") or (r.get("event"), r.get("received_at")): (t, r)
                  for t, r in observations}
        sorted_rows = sorted(unique.values(), key=lambda x: x[0])
        started = [v for v in sorted_rows if v[1].get("phase") == "STARTED"]
        finished = [v for v in sorted_rows if v[1].get("phase") == "FINISHED"]
        if len({(r.get("outcome"), r.get("exit_code")) for _, r in finished}) > 1:
            incidents.append({"kind": "CONFLICTING_TERMINAL", "call": key[3],
                              "source": key[0], "session": key[1], "certainty": "REVIEW"})
            continue
        if finished:
            ended_at, terminal = finished[-1]
            if terminal.get("outcome") == "FAILED" and (now - ended_at).total_seconds() <= failure_window_seconds:
                closed_failures.append((key, terminal))
            if started:
                started_at = started[0][0]
                duration = (ended_at - started_at).total_seconds()
                if duration >= stall_seconds:
                    incidents.append({"kind": "SLOW_COMPLETED_CALL_REVIEW", "call": key[3],
                                      "source": key[0], "session": key[1],
                                      "duration_seconds": int(duration),
                                      "certainty": "DURATION_ONLY_NOT_A_FAILURE"})
            if not started:
                incidents.append({"kind": "ORPHAN_TERMINAL", "call": key[3],
                                  "source": key[0], "session": key[1], "certainty": "REVIEW"})
        elif started:
            last_time = sorted_rows[-1][0]
            age = (now - last_time).total_seconds()
            active.append((key, age))
            if age >= stall_seconds:
                incidents.append({"kind": "SUSPECTED_STALL", "call": key[3],
                                  "source": key[0], "session": key[1],
                                  "seconds_since_observation": int(age),
                                  "certainty": "SUSPECTED_NOT_CONFIRMED"})
    for key, row in closed_failures:
        incidents.append({"kind": "FAILED", "call": key[3], "source": key[0],
                          "session": key[1], "basis": row.get("result_basis"),
                          "certainty": "EXPLICIT_REPORTED_RESULT"})
    groups = defaultdict(set)
    for key, row in closed_failures:
        # Same tool category is NOT evidence of identical commands or a loop.
        groups[(key[0], key[1], row.get("tool"))].add(key[3])
    for (source, session, tool), ids in groups.items():
        if len(ids) >= repeat_limit:
            incidents.append({"kind": "FAILURE_CLUSTER_REVIEW", "session": session,
                              "source": source, "tool_category": tool,
                              "distinct_failed_calls": len(ids),
                              "certainty": "NOT_PROOF_OF_RETRY_OR_LOOP"})
    quiet = not recent or (now - recent[-1][0]).total_seconds() >= quiet_seconds
    if quiet:
        incidents.append({"kind": "NO_OBSERVATION", "certainty": "UNKNOWN_ACTIVITY",
                          "detail": "No recent evidence; machine sleep/unsupported tools possible"})
    suspected = any(x["kind"] == "SUSPECTED_STALL" for x in incidents)
    # Do not leave an old failure as the permanent status of a healthy new run.
    return {"state": ("SUSPECTED_STALL" if suspected else
                      "NO_OBSERVATION" if quiet else
                      "FAILED" if closed_failures else "OBSERVING"),
            "events_read": len(recent), "invalid_or_future_time": invalid_time,
            "open_calls": len(active), "incidents": incidents,
            "limits": "No automatic kill/retry; missing hooks and sleep cannot confirm deadlock."}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--events", required=True)
    p.add_argument("--stall-seconds", type=int, default=300)
    p.add_argument("--quiet-seconds", type=int, default=300)
    args = p.parse_args()
    print(json.dumps(diagnose(read_projected(args.events), stall_seconds=args.stall_seconds,
                              quiet_seconds=args.quiet_seconds), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
