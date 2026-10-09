"""Transition-only task evidence notifications; no retroactive toast on first scan.
Never executes tests, writes agent workspace, or sends task text to PowerShell.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

import app_hook_v29
import task_overview_v35


def db_path():
    return app_hook_v29.local_dir() / "task_pulse.sqlite3"


def connect(db=None):
    p = Path(db or db_path())
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("CREATE TABLE IF NOT EXISTS current (alias TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0)")
    if "revision" not in [x[1] for x in con.execute("PRAGMA table_info(current)").fetchall()]:
        con.execute("ALTER TABLE current ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
    con.execute("CREATE TABLE IF NOT EXISTS notices (id TEXT PRIMARY KEY, alias TEXT NOT NULL, code TEXT NOT NULL)")
    return con


def triggers(task):
    codes = []
    status = task.get("state")
    if status == "CONTRACT_CHANGED_OR_UNAPPROVED":
        codes.append("CONTRACT_REAPPROVAL_REVIEW")
    if status == "BASELINE_CHANGED":
        codes.append("BASELINE_RESET_REVIEW")
    for x in task.get("scope_findings", []):
        if x.get("code") == "PROTECTED_CHANGE":
            codes.append("PROTECTED_FILE_REVIEW")
        if x.get("code") == "OUTSIDE_DECLARED_PATH_SCOPE":
            codes.append("OUTSIDE_SCOPE_REVIEW")
    if any(v in ("STALE", "FAILED", "INCONCLUSIVE") for v in task.get("acceptance", {}).values()):
        codes.append("ACCEPTANCE_REVIEW")
    if task.get("contract_checks_stage") == "VERIFIED_COMPLETE":
        codes.append("CHECKS_PASSED_HUMAN_REVIEW")
    return sorted(set(codes))


def signature(task):
    # Include changed file list and check statuses in fingerprint to recognize a
    # new meaningful issue; never put paths or goal strings in the notice database.
    meaningful = {k: task.get(k) for k in
                  ("state", "contract_checks_stage", "scope_findings", "acceptance")}
    raw = json.dumps(meaningful, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf8")).hexdigest()


def evaluate(snapshot, db=None):
    """Return new changes only after initial baseline; original snapshot remains readable."""
    con = connect(db)
    new = []
    initialized = []
    try:
        with con:
            for task in snapshot.get("tasks", []):
                alias = task.get("session_alias")
                if not isinstance(alias, str) or not alias:
                    continue
                curr = signature(task)
                previous = con.execute("SELECT fingerprint,revision FROM current WHERE alias=?", (alias,)).fetchone()
                revision = 0 if previous is None else previous[1]
                if previous is None:
                    initialized.append(alias)
                elif previous[0] != curr:
                    revision += 1
                    for code in triggers(task):
                        # Recurrence A->B->A is another meaningful transition.
                        alert_id = hashlib.sha256((alias+"\0"+str(revision)+"\0"+code).encode()).hexdigest()
                        if con.execute("INSERT OR IGNORE INTO notices(id,alias,code) VALUES(?,?,?)",
                                       (alert_id,alias,code)).rowcount:
                            new.append({"session_alias": alias, "code": code,
                                        "meaning": "Review local task evidence; event author not established"})
                con.execute("INSERT INTO current(alias,fingerprint,revision) VALUES(?,?,?) ON CONFLICT(alias) DO UPDATE SET fingerprint=excluded.fingerprint,revision=excluded.revision",
                            (alias, curr, revision))
    finally:
        con.close()
    return {"status": "TASK_TRANSITION_REVIEW",
            "initialized_no_historical_notifications": initialized,
            "new_notices": new,
            "tasks_scanned": snapshot.get("task_count",0),
            "limits": "No first-scan historical toast; only Git/acceptance transitions, not Codex attribution"}


def poll(log=None, registry=None, db=None):
    return evaluate(task_overview_v35.overview(log, registry), db)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--log")
    p.add_argument("--registry")
    p.add_argument("--db")
    a = p.parse_args()
    print(json.dumps(poll(a.log,a.registry,a.db),ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
