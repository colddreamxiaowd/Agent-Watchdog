"""Operational backup/health check. No automatic restore or Codex control.
Private SQLite backups contain session metadata: never commit or upload them.
"""
import argparse
import json
import os
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

from app_hook_v29 import event_path,local_dir
from app_watch_v30 import db_path


def status(db=None, log=None):
    path=Path(db or db_path())
    logfile=Path(log or event_path())
    result={"db_exists":path.is_file(),"log_exists":logfile.is_file(),
            "codex_app_e2e":"NOT_VERIFIED","autonomous_recovery":False,
            "warning":"Event coverage and actual Codex App activity require human onsite review"}
    if path.is_file():
        con=sqlite3.connect(str(path),timeout=8)
        try:
            result["integrity"]=con.execute("PRAGMA integrity_check").fetchone()[0]
            result["alerts_total"]=con.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            result["calls_total"]=con.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            result["last_cursor"]=con.execute("SELECT value FROM meta WHERE name='cursor'").fetchone()
        except sqlite3.Error as err:
            result["db_error_type"]=type(err).__name__
        finally:
            con.close()
    return result


def backup(db=None,directory=None):
    source=Path(db or db_path())
    if not source.is_file():
        raise FileNotFoundError("No watcher DB to back up")
    destdir=Path(directory or local_dir()/"backups").resolve()
    # By default all backup data is kept in an app-private location;
    # explicit path overrides should be reviewed by the human operator.
    destdir.mkdir(parents=True,exist_ok=True)
    suffix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target=destdir/f"watch_state-{suffix}.sqlite3"
    if target.exists():
        raise FileExistsError("Backup already exists; refusing overwrite")
    src=sqlite3.connect(str(source),timeout=8)
    dst=sqlite3.connect(str(target),timeout=8)
    try:
        src.backup(dst)
        integrity=dst.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok":
            raise sqlite3.DatabaseError("Backup integrity check failed")
        return {"status":"BACKED_UP_PRIVATE_SQLITE","path":str(target),
                "integrity":integrity,
                "restore":"NOT_AUTOMATED_USER_APPROVAL_REQUIRED"}
    finally:
        src.close()
        dst.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("status","backup"))
    p.add_argument("--db")
    p.add_argument("--log")
    p.add_argument("--directory")
    a=p.parse_args()
    print(json.dumps(status(a.db,a.log) if a.action=="status" else backup(a.db,a.directory),
                     ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
