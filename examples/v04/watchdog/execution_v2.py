"""Round 21-22: strictly redacted execution projection. No source authentication.

New module; the v04 logger and its JSONL format remain supported. Python 3.9+.
Only explicit numeric exit status can establish command success/failure.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from hook_logger_v04 import append, clean, MAX_STDIN

HOOKS = {"PreToolUse", "PostToolUse", "Stop", "SessionStart", "SessionEnd"}
EXEC = {"thread.started", "turn.started", "turn.completed", "turn.failed",
        "item.started", "item.updated", "item.completed", "error"}
APP = {"thread/started", "turn/started", "turn/completed", "turn/failed",
       "item/started", "item/updated", "item/completed"}
PHASE = {"PreToolUse": "STARTED", "PostToolUse": "FINISHED",
         "SessionStart": "STARTED", "SessionEnd": "FINISHED", "Stop": "TURN_END"}
OUTCOMES = {"SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"}
FIELDS = ("source", "received_at", "event", "session_id", "turn_id", "tool",
          "cwd", "tool_use_id", "phase", "outcome", "exit_code", "result_basis",
          "event_id", "linkable")


def text_id(value, max_length=120):
    return clean(value, max_length) if isinstance(value, str) and value else None


def number_code(value):
    return value if type(value) is int and -999999 <= value <= 999999 else None


def compact(data, source, event, phase, tool=None, session=None, turn=None,
            operation=None, cwd=None, exit_code=None, explicit_status=None):
    """Do not accept arbitrary tool-input, output, prompts, commands or errors."""
    code = number_code(exit_code)
    status = explicit_status if explicit_status in ("failed", "declined", "interrupted", "cancelled") else None
    outcome = ("SUCCEEDED" if code == 0 else "FAILED" if code is not None
               else "CANCELLED" if status in ("declined", "interrupted", "cancelled")
               else "FAILED" if status == "failed" else "UNKNOWN")
    basis = ("numeric_exit_code" if code is not None else
             "explicit_terminal_status" if status is not None else "not_observed")
    row = {
        "source": source, "received_at": datetime.now(timezone.utc).isoformat(),
        "event": event, "session_id": text_id(session), "turn_id": text_id(turn),
        "tool": text_id(tool, 100), "cwd": text_id(cwd, 700),
        "tool_use_id": text_id(operation), "phase": phase,
        "outcome": outcome, "exit_code": code, "result_basis": basis,
    }
    # A natural observation without a stable call id cannot be safely attributed
    # to a specific operation or manually linked to a task step.
    row["linkable"] = bool(row["source"] and row["session_id"] and row["tool_use_id"])
    stable = {key: row[key] for key in row if key != "received_at"}
    if not row["linkable"]:
        stable["received_at"] = row["received_at"]
    row["event_id"] = hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]
    return row


def from_hook(data):
    if not isinstance(data, dict) or data.get("hook_event_name") not in HOOKS:
        return None
    event = data["hook_event_name"]
    response = data.get("tool_response")
    # Hook response shape varies by tool and Codex release. This narrow
    # optional extraction is deliberately NOT a generic success inference.
    code = None
    if event == "PostToolUse" and isinstance(response, dict):
        code = number_code(response.get("exit_code"))
        if code is None:
            code = number_code(response.get("exitCode"))
    return compact(data, "hook_input_unverified", event, PHASE[event],
                   data.get("tool_name"), data.get("session_id"),
                   data.get("turn_id"), data.get("tool_use_id"),
                   data.get("cwd"), exit_code=code)


def from_exec(data):
    if not isinstance(data, dict) or data.get("type") not in EXEC:
        return None
    event = data["type"]
    item = data.get("item") if isinstance(data.get("item"), dict) else {}
    terminal = event in ("item.completed", "turn.completed", "turn.failed", "error")
    phase = ("FINISHED" if terminal else "UPDATED" if event == "item.updated" else "STARTED")
    code = item.get("exit_code") if item.get("type") == "command_execution" and terminal else None
    status = ("failed" if event in ("turn.failed", "error") else
              item.get("status") if terminal else None)
    return compact(data, "codex_exec_export_unverified", event, phase,
                   item.get("type"), data.get("thread_id"),
                   data.get("turn_id"), item.get("id"), None, code, status)


def from_appserver(data):
    if not isinstance(data, dict) or data.get("method") not in APP:
        return None
    method = data["method"]
    p = data.get("params") if isinstance(data.get("params"), dict) else {}
    item = p.get("item") if isinstance(p.get("item"), dict) else {}
    thread = p.get("thread") if isinstance(p.get("thread"), dict) else {}
    turn = p.get("turn") if isinstance(p.get("turn"), dict) else {}
    terminal = method in ("item/completed", "turn/completed", "turn/failed")
    phase = "FINISHED" if terminal else "UPDATED" if method == "item/updated" else "STARTED"
    status = ("failed" if method == "turn/failed" else
              (item.get("status") if method == "item/completed" else
               turn.get("status") if method == "turn/completed" else None))
    code = (item.get("exitCode") if item.get("type") == "commandExecution"
            and terminal else None)
    return compact(data, "app_server_export_unverified", method, phase,
                   item.get("type"), p.get("threadId") or thread.get("id"),
                   p.get("turnId") or turn.get("id"), item.get("id"),
                   None, code, status)


def safe_lines(path, adapter, limit=1024 * 1024):
    """Explicit offline import, never follows Codex private databases."""
    with Path(path).open("rb") as stream:
        for line in stream:
            if len(line) > limit or not line.endswith(b"\n"):
                continue
            try:
                row = adapter(json.loads(line.decode("utf-8-sig")))
            except (UnicodeError, ValueError, TypeError):
                row = None
            if row is not None:
                yield row


def read_projected(path):
    """Read normalized or old journal rows; do not invent missing fields."""
    with Path(path).open("rb") as stream:
        for line in stream:
            if not line.endswith(b"\n") or len(line) > 1024 * 1024:
                continue
            try:
                data = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(data, dict) and data.get("source") and data.get("event"):
                yield {key: data.get(key) for key in FIELDS}


def main():
    p = argparse.ArgumentParser(description="Redacted Codex event adapter")
    sub = p.add_subparsers(dest="command", required=True)
    h = sub.add_parser("hook")
    h.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "logs" / "events.jsonl")
    i = sub.add_parser("import")
    i.add_argument("--format", required=True, choices=["exec", "appserver"])
    i.add_argument("--input", required=True)
    i.add_argument("--out", required=True)
    args = p.parse_args()
    if args.command == "hook":
        try:
            raw = sys.stdin.buffer.read(MAX_STDIN + 1)
            if not raw or len(raw) > MAX_STDIN:
                raise ValueError("oversized or missing hook data")
            row = from_hook(json.loads(raw.decode("utf-8-sig")))
            if row is None:
                raise ValueError("unsupported hook event")
            append(row, args.out)
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            print("Watchdog hook observer: " + type(error).__name__, file=sys.stderr)
        print("{}")  # observation only; never block or change a tool call
        return
    if Path(args.input).resolve() == Path(args.out).resolve():
        p.error("input and output must differ")
    adapter = from_exec if args.format == "exec" else from_appserver
    count = 0
    for row in safe_lines(args.input, adapter):
        append(row, Path(args.out))
        count += 1
    print(json.dumps({"imported": count, "authenticity": "NOT_VERIFIED"}))


if __name__ == "__main__":
    main()
