"""Opt-in read-only Codex App companion: durable JSONL cursor, alerts, Windows balloon.
No raw commands are read/saved. No claims about Codex process health or deadlock.
An initial watcher follows *new* events by default, not old log history.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app_hook_v29 import event_path, local_dir
from execution_v2 import FIELDS

CHUNK = 2 * 1024 * 1024
MAX_LINE = 1024 * 1024


def now_seconds():
    return int(datetime.now(timezone.utc).timestamp())


def db_path():
    return local_dir() / "watch_state.sqlite3"


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS calls (
       id TEXT PRIMARY KEY, source TEXT, session TEXT, tool TEXT,
       started INTEGER, finished INTEGER, outcome TEXT, stall_alerted INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS alerts (
       id TEXT PRIMARY KEY, code TEXT NOT NULL, created INTEGER NOT NULL,
       message TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cooldown (id TEXT PRIMARY KEY, next_at INTEGER NOT NULL);
    """)
    return con


def get_meta(con, name):
    row = con.execute("SELECT value FROM meta WHERE name=?", (name,)).fetchone()
    return row[0] if row else None


def set_meta(con, name, value):
    con.execute("INSERT INTO meta(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                (name, str(value)))


def file_prefix(path):
    with Path(path).open("rb") as f:
        return hashlib.sha256(f.read(256)).hexdigest()


def new_lines(path, offset):
    with Path(path).open("rb") as f:
        f.seek(offset)
        raw = f.read(CHUNK)
    end = raw.rfind(b"\n")
    if end < 0:
        if len(raw) >= CHUNK:
            # Stuck on an enormous/unfinished line; do not silently discard it.
            return [], offset, "OVERSIZED_OR_INCOMPLETE_LINE"
        return [], offset, None
    return raw[:end+1].splitlines(), offset+end+1, None


def timestamp(row):
    value = row.get("received_at")
    if not isinstance(value, str):
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(d.timestamp()) if d.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


def safe_id(value):
    return isinstance(value, str) and bool(value) and len(value) <= 150


def store_alert(con, unique, code, seconds, message):
    return bool(con.execute("INSERT OR IGNORE INTO alerts(id,code,created,message) VALUES(?,?,?,?)",
                            (unique, code, seconds, message)).rowcount)


def ingest(con, row, sec, failure_count, cooldown_seconds):
    if not isinstance(row, dict) or not safe_id(row.get("source")) or not safe_id(row.get("event")):
        return 0
    ident = row.get("event_id")
    if not safe_id(ident):
        # Missing stable ID: keep the observation only as part of a unique raw projection;
        # it is never sufficient to identify a call.
        ident = hashlib.sha256(json.dumps({k:row.get(k) for k in FIELDS},sort_keys=True,
                                       ensure_ascii=False,default=str).encode()).hexdigest()
    if not con.execute("INSERT OR IGNORE INTO seen(id) VALUES(?)", (ident,)).rowcount:
        return 0
    if (row.get("linkable") is not True or
        not all(safe_id(row.get(k)) for k in ("session_id","tool_use_id")) or
        row.get("phase") not in ("STARTED","FINISHED")):
        return 0
    key = hashlib.sha256(json.dumps([row.get(x) for x in
                  ("source","session_id","turn_id","tool_use_id")],ensure_ascii=False).encode()).hexdigest()
    tool = row.get("tool") if safe_id(row.get("tool")) else "UNKNOWN_TOOL"
    if row["phase"] == "STARTED":
        con.execute("""INSERT OR IGNORE INTO calls(id,source,session,tool,started) VALUES(?,?,?,?,?)""",
                    (key,row["source"],row["session_id"],tool,sec))
        return 0
    outcome = row.get("outcome") if row.get("outcome") in ("FAILED","SUCCEEDED","CANCELLED","UNKNOWN") else "UNKNOWN"
    con.execute("""INSERT INTO calls(id,source,session,tool,finished,outcome) VALUES(?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                   finished=excluded.finished, outcome=excluded.outcome""",
                (key,row["source"],row["session_id"],tool,sec,outcome))
    if outcome != "FAILED":
        return 0
    n = con.execute("""SELECT COUNT(*) FROM calls WHERE source=? AND session=? AND tool=?
                       AND outcome='FAILED' AND finished BETWEEN ? AND ?""",
                    (row["source"],row["session_id"],tool,sec-600,sec)).fetchone()[0]
    if n < failure_count:
        return 0
    group = hashlib.sha256(json.dumps([row["source"],row["session_id"],tool]).encode()).hexdigest()
    next_at = con.execute("SELECT next_at FROM cooldown WHERE id=?", (group,)).fetchone()
    if next_at and next_at[0] > sec:
        return 0
    con.execute("INSERT INTO cooldown(id,next_at) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET next_at=excluded.next_at",
                (group,sec+cooldown_seconds))
    return int(store_alert(con,f"cluster:{group}:{sec}","FAILURE_CLUSTER_REVIEW",sec,
                           "Multiple explicitly failed calls of the same tool category; review only."))


def check_stalls(con, sec, stall_seconds):
    added = 0
    # Started and never finished; no proof of a hang (sleep/unsupported hook may explain).
    for key,started in con.execute("""SELECT id,started FROM calls WHERE started IS NOT NULL
          AND finished IS NULL AND stall_alerted=0 AND started<=?""",(sec-stall_seconds,)).fetchall():
        if store_alert(con,"stall:"+key,"SUSPECTED_STALL",sec,
                       "Started call without observed terminal event; NOT a confirmed hang."):
            added += 1
        con.execute("UPDATE calls SET stall_alerted=1 WHERE id=?",(key,))
    return added


def poll(log=None, db=None, sec=None, include_existing=False, stall_seconds=300,
         failure_count=3, cooldown_seconds=900):
    if (type(stall_seconds) is not int or stall_seconds < 5 or
        type(failure_count) is not int or failure_count < 2 or
        type(cooldown_seconds) is not int or cooldown_seconds < 1):
        raise ValueError("invalid safety thresholds")
    path=Path(log or event_path())
    pathdb=Path(db or db_path())
    sec=now_seconds() if sec is None else sec
    con=connect(pathdb)
    try:
        with con:
            previous = get_meta(con,"cursor")
            if not path.is_file():
                return {"status":"NO_LOG_NOT_CODEX_OFFLINE","events_new":0,"alerts_new":0}
            stat=path.stat()
            generation=str((stat.st_dev,stat.st_ino))
            prefix=file_prefix(path)
            size=stat.st_size
            prev_gen=get_meta(con,"generation")
            prev_prefix=get_meta(con,"prefix")
            offset=int(previous) if previous is not None else 0
            reset=(previous is not None and
                    (generation!=prev_gen or prefix!=prev_prefix or size<offset))
            if reset:
                offset=0
            if previous is None and not include_existing:
                # Start from the last complete line. Never consume a half line.
                with path.open("rb") as f:
                    f.seek(max(0,size-MAX_LINE))
                    window=f.read()
                last=window.rfind(b"\n")
                offset=(max(0,size-MAX_LINE)+last+1) if last>=0 else 0
                if offset==0 and size>MAX_LINE:
                    return {"status":"UNSAFE_UNTERMINATED_LOG","events_new":0,"alerts_new":0}
            lines,new_offset,warning=new_lines(path,offset)
            count,alerts=0,0
            for line in lines:
                if len(line)>MAX_LINE:
                    continue
                try:
                    row=json.loads(line)
                except (ValueError,UnicodeDecodeError):
                    continue
                if isinstance(row,dict) and row.get("source") and row.get("event"):
                    stamp=timestamp(row)
                    if stamp is not None and 0<=sec-stamp<=86400:
                        count+=1
                        alerts+=ingest(con,row,stamp,failure_count,cooldown_seconds)
            alerts+=check_stalls(con,sec,stall_seconds)
            set_meta(con,"cursor",new_offset)
            set_meta(con,"generation",generation)
            set_meta(con,"prefix",prefix)
            return {"status":"OBSERVING_NOT_A_HEALTH_PROOF",
                    "events_new":count, "alerts_new":alerts,
                    "cursor_reset":reset,"log_warning":warning}
    finally:
        con.close()


MESSAGES={
"FAILURE_CLUSTER_REVIEW":"Several failed calls. Review Codex App manually.",
"SUSPECTED_STALL":"Call has no observed finish. Check Codex App; hang NOT proven."
}


def notify_windows(code):
    """Only fixed strings are passed to PowerShell; no user/task strings."""
    if os.name!="nt" or code not in MESSAGES:
        return False
    # Windows PowerShell Desktop; notifications may be suppressed by OS policies.
    script=("Add-Type -AssemblyName System.Windows.Forms;"
            "$n=New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon=[System.Drawing.SystemIcons]::Information;"
            "$n.Visible=$true;$n.BalloonTipTitle='Agent Watchdog review';"
            "$n.BalloonTipText='"+MESSAGES[code]+"';"
            "$n.ShowBalloonTip(4000);Start-Sleep -Seconds 4;$n.Dispose()")
    try:
        p=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",script],
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         timeout=8,check=False)
        return p.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


def show_alerts(db=None, notify=False):
    con=connect(db or db_path())
    try:
        alerts=con.execute("SELECT code,created,message FROM alerts ORDER BY created DESC LIMIT 20").fetchall()
        if notify:
            # Only notify for newly created, never re-notify on restart.
            ids=con.execute("SELECT id,code FROM alerts WHERE id NOT IN (SELECT value FROM meta WHERE name LIKE 'attempted:%') LIMIT 10").fetchall()
            for ident,code in ids:
                result=notify_windows(code)
                with con:
                    set_meta(con,"attempted:"+ident,ident)
                print("NOTIFY_ATTEMPT",code, "REQUEST_ACCEPTED" if result else "UNAVAILABLE")
        return alerts
    finally:
        con.close()


def main():
    p=argparse.ArgumentParser(description="Codex App optional background-ish foreground watcher")
    p.add_argument("--log")
    p.add_argument("--db")
    p.add_argument("--once",action="store_true")
    p.add_argument("--notify",action="store_true",help="Windows balloon only, no remote push")
    p.add_argument("--include-existing",action="store_true",help="First run: replay previous log")
    p.add_argument("--interval",type=int,default=3)
    p.add_argument("--stall-seconds",type=int,default=300)
    p.add_argument("--failure-count",type=int,default=3)
    a=p.parse_args()
    if a.interval<1:
        p.error("interval must be positive")
    while True:
        try:
            report=poll(a.log,a.db,include_existing=a.include_existing,
                        stall_seconds=a.stall_seconds,failure_count=a.failure_count)
            report["recent_alerts"]=[{"code":x[0],"created":x[1],"detail":x[2]}
                                     for x in show_alerts(a.db,a.notify)]
            print(json.dumps(report,ensure_ascii=False,default=str),flush=True)
        except (OSError,sqlite3.Error,ValueError) as e:
            print(json.dumps({"status":"WATCHER_ERROR","error_type":type(e).__name__}),flush=True)
        if a.once:
            break
        try:
            time.sleep(a.interval)
        except KeyboardInterrupt:
            break


if __name__=="__main__":
    main()
