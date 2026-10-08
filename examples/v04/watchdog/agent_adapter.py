"""V1.0 optional, EXPLICIT import of redacted codex exec --json export.
Never points to the private Codex session database and never imports prompt text.
"""
import argparse
import json
from pathlib import Path
from hook_logger_v04 import append, clean
from datetime import datetime, timezone

# This is intentionally a conservative taxonomy, not a complete App Server adapter.
KINDS = {"thread.started", "turn.started", "turn.completed", "turn.failed", "item.started", "item.completed"}


def project(row):
    kind = row.get("type")
    if kind not in KINDS:
        return None
    item = row.get("item") or {}
    if not isinstance(item, dict):
        item = {}
    return {
        "source": "codex_exec_export", "received_at": datetime.now(timezone.utc).isoformat(),
        "event": kind, "session_id": clean(row.get("thread_id"),120),
        "turn_id": clean(row.get("turn_id"),120),
        "tool": clean(item.get("type"),80), "cwd": None, "tool_use_id": clean(item.get("id"),120),
    }


def import_file(file, out):
    count = 0
    with Path(file).open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            event = project(row)
            if event:
                append(event, Path(out)); count += 1
    return count


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file", help="Explicitly provided codex exec --json stream")
    p.add_argument("--out", required=True, help="Redacted output JSONL, not raw input")
    a = p.parse_args()
    print("Redacted event records:",import_file(a.file,a.out))

if __name__ == "__main__": main()
