"""Agent Watchdog 03 - local, on-demand Git and test evidence collector.

Commands:
  python evidence.py --repo PATH baseline
  python evidence.py --repo PATH scan
  python evidence.py --repo PATH test -- python -m unittest discover -v

Reads a Git worktree; baseline/test metadata is written beside this script,
NOT into the observed repository. Tests run only on an explicit 'test' command.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PROTECTED = ["GOAL.md", ".env", ".github/workflows/*"]


def timestamp():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "Git command failed")
    return result.stdout


def root_for(path):
    path = Path(path).expanduser().resolve()
    root = git(path, "rev-parse", "--show-toplevel").decode(errors="replace").strip()
    return Path(root).resolve()


def state_dir(repo):
    key = hashlib.sha256(os.fsencode(str(repo))).hexdigest()[:16]
    result = HERE / "state" / key
    result.mkdir(parents=True, exist_ok=True)
    return result


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def file_digest(path):
    if path.is_symlink():
        return "symlink:" + os.readlink(path)
    if not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def snapshot(repo):
    # Cached files include tracked files; others includes untracked (non-ignored) files.
    data = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    names = {os.fsdecode(name) for name in data.split(b"\0") if name}
    # Any tracked file that was deleted is still in the Git index and is marked MISSING.
    result = {}
    for name in sorted(names):
        target = repo / name
        result[name.replace("\\", "/")] = file_digest(target)
    return result


def fingerprint(files):
    canonical = json.dumps(files, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def protected_patterns():
    path = HERE / "watchdog_rules.json"
    if not path.exists():
        return DEFAULT_PROTECTED
    config = read_json(path)
    patterns = config.get("protected_paths")
    if not isinstance(patterns, list) or not all(isinstance(x, str) for x in patterns):
        raise ValueError("watchdog_rules.json must contain protected_paths: [string, ...]")
    return patterns


def diff_files(before, after):
    return [name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]


def summary(repo):
    state = state_dir(repo)
    current = snapshot(repo)
    base = read_json(state / "baseline.json")
    test = read_json(state / "last_test.json")
    print(f"\nAgent Watchdog 03 | Repository: {repo}")
    print(f"Snapshot: {fingerprint(current)[:16]} | Observed files: {len(current)}")

    if base is None:
        print("Baseline: MISSING (run baseline first)")
    else:
        changed = diff_files(base["files"], current)
        patterns = protected_patterns()
        protected = [name for name in changed if any(fnmatch.fnmatchcase(name, pat) for pat in patterns)]
        print(f"Changed vs baseline: {len(changed)}")
        for name in changed[:30]:
            old, new = base["files"].get(name), current.get(name)
            action = "ADDED" if old is None else "REMOVED" if new is None or new == "MISSING" else "MODIFIED"
            print(f"  {action:<8} {name}")
        if len(changed) > 30:
            print(f"  ... {len(changed) - 30} more")
        if protected:
            print("PROTECTED CHANGES: " + ", ".join(protected[:20]))
        else:
            print("Protected files: no changes detected in Git-visible scope")

    if test is None:
        print("Test evidence: NOT_TESTED")
    else:
        if test["start_snapshot"] != test["end_snapshot"]:
            status = "INCONCLUSIVE (files changed during test)"
        elif test["end_snapshot"] != fingerprint(current):
            status = "STALE (repository changed after test)"
        elif test["exit_code"] == 0:
            status = "PASS_FOR_TESTED_SNAPSHOT (only the chosen command)"
        else:
            status = "FAIL (test command returned non-zero)"
        print(f"Test evidence: {status}")
        print(f"  Command: {' '.join(test['command'])}")
        print(f"  Exit code: {test['exit_code']} | Recorded: {test['ended_at']}")
    print("Reminder: Git-visible scope excludes ignored files and external state.")
    print("Never infer complete task success solely from one passing test command.\n")


def run_test(repo, command, timeout):
    state = state_dir(repo)
    if not command or command == ["--"]:
        raise ValueError("Provide the test command after '--', e.g. -- python -m unittest discover -v")
    if command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("Missing test command")
    # No shell=True: executable + arguments remain separate.
    before = fingerprint(snapshot(repo))
    started_at = timestamp()
    print(f"Running user-requested test in {repo}: {' '.join(command)}")
    try:
        p = subprocess.run(
            command,
            cwd=repo,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
        code, output = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as exc:
        code = 124
        output = f"Timed out after {timeout} seconds; result is not a pass."
    except OSError as exc:
        code = 127
        output = f"Could not start test process: {exc}"
    after = fingerprint(snapshot(repo))
    record = {
        "command": command,
        "started_at": started_at,
        "ended_at": timestamp(),
        "exit_code": code,
        "start_snapshot": before,
        "end_snapshot": after,
    }
    atomic_json(state / "last_test.json", record)
    print("\n--- Test output (last 3000 characters; not persisted) ---")
    print(output[-3000:].strip() or "(no output)")
    print("--- End test output ---")
    summary(repo)


def main():
    parser = argparse.ArgumentParser(description="Read-only Git evidence + explicitly-run tests")
    parser.add_argument("--repo", required=True, help="Path to local Git repository")
    parser.add_argument("--timeout", type=int, default=180, help="Test timeout in seconds")
    parser.add_argument("action", choices=("baseline", "scan", "test"))
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Test command, preceded by --")
    args = parser.parse_args()
    repo = root_for(args.repo)
    if args.action == "baseline":
        files = snapshot(repo)
        atomic_json(state_dir(repo) / "baseline.json", {
            "saved_at": timestamp(), "repo": str(repo), "snapshot_id": fingerprint(files), "files": files
        })
        print(f"Baseline saved outside the repo: {len(files)} Git-visible files.")
        print("WARNING: replacing this baseline later resets the comparison reference.")
        summary(repo)
    elif args.action == "scan":
        summary(repo)
    else:
        run_test(repo, args.command, args.timeout)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(2)
