"""Opt-in Codex desktop lifecycle-hook observer. Never affects tools.
Creates only a minimal sanitized JSONL under the user's local app state.
Hook source is not authenticated; app E2E must be witnessed by user.
"""
import json
import os
import sys
from pathlib import Path

from execution_v2 import from_hook
from hook_logger_v04 import append, MAX_STDIN


def local_dir():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "AgentWatchdog"
    return Path.home() / ".local" / "state" / "AgentWatchdog"


def event_path():
    return local_dir() / "events.jsonl"


def observe(raw, out):
    if not isinstance(raw, (bytes, bytearray)) or not 0 < len(raw) <= MAX_STDIN:
        return False
    try:
        data = json.loads(raw.decode("utf-8-sig"))
        row = from_hook(data)
        if row is None:
            return False
        # No absolute workspace path or prompt/command/output is stored by default.
        row["cwd"] = None
        append(row, out)
        return True
    except (OSError, ValueError, TypeError, UnicodeError):
        return False


def main():
    # Hooks must never stop Codex, even if Python, IO or schema fails.
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN + 1)
        observe(raw, event_path())
    except Exception:
        pass
    print("{}")


if __name__ == "__main__":
    main()
