"""V0.9: replayable, sanitized JSONL -> SQLite ledger with transactional cursor."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LOG = HERE / "logs" / "events.jsonl"
DEFAULT_DB = HERE / "data" / "journal.sqlite3"
FIELDS = ("source", "received_at", "event", "session_id", "turn_id", "tool", "cwd", "tool_use_id",
          "phase", "outcome", "exit_code", "result_basis", "event_id", "linkable")


def connect(db):
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db), timeout=15)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=15000")
    connection.executescript("""
      CREATE TABLE IF NOT EXISTS events (
        source_path TEXT NOT NULL, file_generation TEXT NOT NULL, byte_offset INTEGER NOT NULL,
        payload TEXT NOT NULL, PRIMARY KEY(source_path,file_generation,byte_offset));
      CREATE TABLE IF NOT EXISTS cursors (
        source_path TEXT PRIMARY KEY, generation TEXT NOT NULL, offset INTEGER NOT NULL);
    """)
    return connection


def sync(log=DEFAULT_LOG, db=DEFAULT_DB, max_bytes=2*1024*1024):
    log, db = Path(log).resolve(), Path(db)
    if not log.exists():
        return 0
    state = log.stat()
    # Stable while the same file exists; not a cryptographic identity or perfect rotation detector.
    generation = f"{state.st_dev}:{state.st_ino}"
    con = connect(db)
    try:
        with con:
            row = con.execute("SELECT generation,offset FROM cursors WHERE source_path=?", (str(log),)).fetchone()
            offset = row[1] if row and row[0] == generation and state.st_size >= row[1] else 0
            with log.open("rb") as fh:
                fh.seek(offset)
                block = fh.read(max_bytes)
            # Never import an unfinished line.
            complete = block.rfind(b"\n")
            if complete < 0:
                return 0
            raw = block[:complete+1]
            added = 0
            position = offset
            for line in raw.splitlines(keepends=True):
                try:
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("non-object")
                    safe = {key: item.get(key) for key in FIELDS}
                    payload = json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
                    con.execute("INSERT OR IGNORE INTO events VALUES(?,?,?,?)",
                                (str(log), generation, position, payload))
                    added += con.execute("SELECT changes()").fetchone()[0]
                except (UnicodeDecodeError, ValueError):
                    # Redacted errors only; content never printed.
                    pass
                position += len(line)
            con.execute("INSERT INTO cursors(source_path,generation,offset) VALUES(?,?,?) "
                        "ON CONFLICT(source_path) DO UPDATE SET generation=excluded.generation, offset=excluded.offset",
                        (str(log), generation, offset+len(raw)))
        return added
    finally:
        con.close()


def summary(db=DEFAULT_DB):
    # sqlite3.Connection context managers commit/rollback but do NOT close.
    # Windows keeps a file handle open until close(), blocking tempfile cleanup.
    con = connect(db)
    try:
        n = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        sessions = con.execute("SELECT COUNT(DISTINCT json_extract(payload,'$.session_id')) FROM events").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        return {"events": n, "distinct_sessions": sessions, "integrity": integrity}
    finally:
        con.close()


def backup(db=DEFAULT_DB, dest="journal.backup.sqlite3"):
    source = connect(db)
    try:
        target = sqlite3.connect(str(dest))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("sync", "summary", "backup"))
    p.add_argument("--log", default=str(DEFAULT_LOG))
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--dest", default="journal.backup.sqlite3")
    args = p.parse_args()
    if args.action == "sync": print("Imported:", sync(args.log,args.db))
    elif args.action == "summary": print(json.dumps(summary(args.db),ensure_ascii=False,indent=2))
    else: backup(args.db,args.dest); print("Backup:",args.dest)


if __name__ == "__main__": main()
