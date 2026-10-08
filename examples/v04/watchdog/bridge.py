"""Event-to-evidence bridge for original V0.3 evidence.py.
Scans Git, never runs tests, never writes into the observed repository.
"""
import argparse
import fnmatch
import json
import os
import time
from pathlib import Path
import evidence

HERE = Path(__file__).resolve().parent
LOG = HERE / "logs" / "events.jsonl"
TRIGGERS = {"PostToolUse", "Stop", "SessionEnd"}


def tracked_repo_event(row, repo):
    cwd = row.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return False
    try:
        Path(cwd).resolve().relative_to(repo.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def scan(repo, trigger="poll"):
    repo = evidence.root_for(repo)
    state = evidence.state_dir(repo)
    files = evidence.snapshot(repo)
    base = evidence.read_json(state / "baseline.json")
    test = evidence.read_json(state / "last_test.json")
    changed = evidence.diff_files(base["files"], files) if base else []
    protected = [x for x in changed if any(fnmatch.fnmatchcase(x, p) for p in evidence.protected_patterns())]
    current = evidence.fingerprint(files)
    if test is None:
        test_status = "NOT_TESTED"
    elif test.get("start_snapshot") != test.get("end_snapshot"):
        test_status = "INCONCLUSIVE"
    elif test.get("end_snapshot") != current:
        test_status = "STALE"
    elif test.get("exit_code") == 0:
        test_status = "PASSED"
    else:
        test_status = "FAILED"
    report = {
        "repo": str(repo), "scanned_at": evidence.timestamp(), "trigger": trigger,
        "snapshot": current, "has_baseline": base is not None,
        "changed": changed, "protected": protected, "test_status": test_status,
        "scope": "Git tracked + non-ignored untracked only",
    }
    evidence.atomic_json(state / "bridge_report.json", report)
    return report


def read_new(path, offset):
    if not path.exists():
        return [], 0 if offset else offset
    size = path.stat().st_size
    if size < offset:
        offset = 0  # log truncated/rotated; see chapter 09 for a persistent event store
    with path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(2 * 1024 * 1024)
    # Keep an incomplete last line for next read, not as an event.
    end = data.rfind(b"\n")
    if end < 0:
        return [], offset
    block = data[:end + 1]
    rows = []
    for line in block.splitlines():
        try:
            r = json.loads(line)
            if isinstance(r, dict):
                rows.append(r)
        except (UnicodeDecodeError, ValueError):
            continue
    return rows, offset + end + 1


def watch(repo, interval=0.5, debounce=2.0, min_interval=5.0, max_delay=10.0):
    repo = evidence.root_for(repo)
    offset = LOG.stat().st_size if LOG.exists() else 0  # new events only, V0.4
    last_scan = time.monotonic()
    pending_since = None
    last_event = None
    print("[Bridge] repo:", repo, "| reading new Hook events", flush=True)
    print("[Bridge] Tests are NEVER started automatically.", flush=True)
    while True:
        now = time.monotonic()
        rows, offset = read_new(LOG, offset)
        for row in rows:
            if row.get("event") in TRIGGERS and tracked_repo_event(row, repo):
                if pending_since is None:
                    pending_since = now
                last_event = now
        should_scan = (pending_since is not None and now - last_scan >= min_interval
                       and ((now - last_event >= debounce) or (now - pending_since >= max_delay)))
        # 30-second fallback catches manual file changes not attributed to Codex.
        if should_scan or now - last_scan >= 30:
            try:
                r = scan(repo, "hook" if should_scan else "poll")
                print("[SCAN]", r["trigger"], "changed=", len(r["changed"]),
                      "protected=", len(r["protected"]), "test=", r["test_status"], flush=True)
            except Exception as exc:
                print("[SCAN ERROR]", type(exc).__name__, str(exc)[:180], flush=True)
            last_scan = time.monotonic()
            pending_since = last_event = None
        time.sleep(max(0.1, interval))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()
    if args.once:
        print(json.dumps(scan(args.repo, "manual"), ensure_ascii=False, indent=2))
    else:
        watch(args.repo)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bridge stopped")
