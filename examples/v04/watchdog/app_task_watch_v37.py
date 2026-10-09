"""Integrated local Codex App companion: events + approved-task transitions.
No auto-run tests, no auto trust/kill/retry, no background registration.
"""
import argparse
import json
import sqlite3
import time

import app_watch_v30
import session_binding_v34
import task_overview_v35
import task_pulse_v36

TASK_MESSAGES = {
    "CONTRACT_REAPPROVAL_REVIEW": "Task contract changed. Review approval and binding.",
    "BASELINE_RESET_REVIEW": "Task Git baseline changed. Review binding.",
    "PROTECTED_FILE_REVIEW": "Protected file differs. Review local task evidence.",
    "OUTSIDE_SCOPE_REVIEW": "Git files outside approved scope. Please review.",
    "ACCEPTANCE_REVIEW": "Saved test evidence failed or is stale. Review.",
    "CHECKS_PASSED_HUMAN_REVIEW": "Approved checks passed. Verify the original goal."
}
# The existing fixed-string notifier can reuse these, without any private
# strings from the session, file names or task goal.
app_watch_v30.MESSAGES.update(TASK_MESSAGES)


def cycle(log=None, registry=None, watch_db=None, pulse_db=None, notify=False):
    general = app_watch_v30.poll(log=log, db=watch_db)
    fresh = general.pop("new_alert_ids", [])
    if fresh and notify:
        app_watch_v30.show_alerts(watch_db, True, fresh)
    snapshot = task_overview_v35.overview(log, registry)
    task_changes = task_pulse_v36.evaluate(snapshot, pulse_db)
    if notify:
        for item in task_changes["new_notices"]:
            app_watch_v30.notify_windows(item["code"])
    return {"status": "READ_ONLY_CODEX_APP_TASK_WATCH",
            "unverified_app_hook": True, "event_observation": general,
            "task_evidence": task_changes,
            "task_states": [{"session_alias": t.get("session_alias"), "state": t.get("state"),
                             "contract_checks_stage": t.get("contract_checks_stage"),
                             "actions": t.get("actions", [])} for t in snapshot["tasks"]],
            "limits": "No automatic acceptance runs, no process control, no task semantic certainty"}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="action", required=True)
    x = sub.add_parser("sessions"); x.add_argument("--log")
    x = sub.add_parser("bind")
    x.add_argument("--repo",required=True); x.add_argument("--alias",required=True)
    x.add_argument("--log"); x.add_argument("--registry")
    x.add_argument("--approve-binding",action="store_true")
    x = sub.add_parser("overview"); x.add_argument("--log"); x.add_argument("--registry")
    x.add_argument("--show-goal",action="store_true")
    x = sub.add_parser("watch")
    x.add_argument("--log"); x.add_argument("--registry")
    x.add_argument("--watch-db"); x.add_argument("--pulse-db")
    x.add_argument("--notify", action="store_true")
    x.add_argument("--once",action="store_true")
    x.add_argument("--interval",type=int,default=30)
    a=p.parse_args()
    if a.action == "sessions":
        rows=[{k:v for k,v in x.items() if not k.startswith("_")} for x in session_binding_v34.sessions(a.log)]
        print(json.dumps({"sessions":rows,"origin":"HOOK_UNVERIFIED"},ensure_ascii=False,indent=2))
        return
    if a.action == "bind":
        print(json.dumps(session_binding_v34.bind(a.repo,a.alias,a.log,a.registry,a.approve_binding),
                         ensure_ascii=False,indent=2))
        return
    if a.action == "overview":
        print(json.dumps(task_overview_v35.overview(a.log,a.registry,a.show_goal),
                         ensure_ascii=False,indent=2))
        return
    if a.interval < 1:
        p.error("interval must be positive")
    first=True
    while True:
        try:
            report=cycle(a.log,a.registry,a.watch_db,a.pulse_db,a.notify)
            changed=report["event_observation"].get("events_new",0) or \
                    report["event_observation"].get("alerts_new",0) or \
                    report["task_evidence"]["new_notices"]
            if first or changed:
                print(json.dumps(report,ensure_ascii=False),flush=True)
            first=False
        except (OSError,sqlite3.Error,ValueError,RuntimeError) as exc:
            print(json.dumps({"status":"WATCH_ERROR","error_kind":type(exc).__name__}),flush=True)
        if a.once:
            break
        try:
            time.sleep(a.interval)
        except KeyboardInterrupt:
            break


if __name__=="__main__":
    main()
