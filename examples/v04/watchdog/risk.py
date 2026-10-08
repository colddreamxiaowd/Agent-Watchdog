"""V0.7 deterministic signals, facts first; never treats inactivity as stuck."""
from collections import Counter


def evaluate(report, task=None, recent_events=None):
    alerts = []
    if report.get("protected"):
        alerts.append({"severity": "high", "code": "PROTECTED_CHANGE", "kind": "fact",
                       "evidence": report["protected"], "action": "Inspect changed protected files"})
    if report.get("test_status") in {"FAILED", "STALE", "INCONCLUSIVE"}:
        alerts.append({"severity": "medium", "code": "TEST_" + report["test_status"], "kind": "fact",
                       "evidence": report["test_status"], "action": "Review or rerun approved tests"})
    if task:
        for ident, status in task.get("acceptance", {}).items():
            if status != "PASSED":
                alerts.append({"severity": "medium", "code": "UNVERIFIED_" + ident, "kind": "fact",
                               "evidence": status, "action": "Verify acceptance " + ident})
    last = (recent_events or [])[-6:]
    if len(last) == 6 and all(x.get("tool") for x in last) and len({x.get("tool") for x in last}) == 1:
        alerts.append({"severity": "low", "code": "REPEATED_TOOL_CATEGORY", "kind": "heuristic",
                       "evidence": {"count": 6, "tool": last[0].get("tool")},
                       "action": "Review context; six same-named tools do not prove a loop"})
    return alerts
