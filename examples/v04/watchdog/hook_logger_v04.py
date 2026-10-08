"""Minimal, non-intervening Codex Hook logger. Python 3.9+.
Only allowlisted metadata is stored; tool arguments and output are discarded.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "logs" / "events.jsonl"
MAX_STDIN = 2 * 1024 * 1024
EVENTS = {"PreToolUse", "PostToolUse", "Stop", "SessionStart", "SessionEnd"}


def clean(value, limit=300):
    if not isinstance(value, str):
        return None
    value = "".join(ch for ch in value if ch.isprintable())
    return value[:limit]


def prepare(payload):
    if not isinstance(payload, dict):
        raise ValueError("Hook input must be an object")
    event = clean(payload.get("hook_event_name"), 40)
    if event not in EVENTS:
        raise ValueError("Unknown or unsupported hook event")
    return {
        "source": "hook_input_unverified",  # Caller identity is NOT authenticated by stdin
        "received_at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "session_id": clean(payload.get("session_id"), 120),
        "turn_id": clean(payload.get("turn_id"), 120),
        "tool": clean(payload.get("tool_name"), 120),
        "cwd": clean(payload.get("cwd"), 700),
        "tool_use_id": clean(payload.get("tool_use_id"), 120),
    }


def append(record, path=LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        if os.write(fd, data) != len(data):
            raise OSError("short write")
    finally:
        os.close(fd)


def main():
    raw = sys.stdin.buffer.read(MAX_STDIN + 1)
    if not raw or len(raw) > MAX_STDIN:
        raise ValueError("empty or oversized Hook input")
    append(prepare(json.loads(raw.decode("utf-8-sig"))))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not disclose input contents on stderr.
        print("Watchdog logger error: " + type(exc).__name__, file=sys.stderr)
    print("{}")  # observer only; never block/rewrite a Codex operation
