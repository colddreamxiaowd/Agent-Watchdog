"""LEGACY PROJECT-ONLY example generator. No overwrite of hooks.json.
Windows Desktop field results favor a reviewed GLOBAL commandWindows + ASCII
.cmd wrapper. This old project proposal may not dispatch on Desktop; use
app_trust_review_v33.py and the interactive codex CLI /hooks for trust.
"""
import argparse
import json
import sys
from pathlib import Path

import evidence
from app_hook_v29 import event_path

EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "Stop", "SessionEnd")


def config(python_path=None, script_path=None):
    py = Path(python_path or sys.executable).expanduser().resolve()
    script = Path(script_path or Path(__file__).with_name("app_hook_v29.py")).resolve()
    if not py.is_file() or not script.is_file():
        raise ValueError("Python interpreter or observer not found")
    if any('"' in str(x) for x in (py, script)):
        raise ValueError("quoted path unsupported")
    command = f'"{py}" "{script}"'
    return {"hooks": {key: [{"hooks": [{
        "type": "command", "command": command, "timeout": 3 if key == "SessionEnd" else 10,
        "statusMessage": "Agent Watchdog: read-only event capture"
    }]}] for key in EVENTS}}


def doctor(repo):
    root = evidence.root_for(repo)
    dst = root / ".codex" / "hooks.json"
    return {"project": str(root), "config_path": str(dst),
            "config_exists": dst.exists(), "observer": str(Path(__file__).with_name("app_hook_v29.py")),
            "event_path": str(event_path()), "codex_app_end_to_end": "NOT_VERIFIED",
            "next": "Legacy project-hook demo only. On Windows prefer existing working global Hook; inspect trust via interactive CLI /hooks with same CODEX_HOME. Never overwrite global configuration."}


def install(repo, config_obj, acknowledged=False):
    if not acknowledged:
        raise ValueError("explicit --ack-reviewed-hooks required")
    root = evidence.root_for(repo)
    target = root / ".codex" / "hooks.json"
    if target.is_symlink() or target.exists():
        raise FileExistsError("existing/symlinked hooks.json; do not overwrite or merge automatically")
    if (root / ".codex").is_symlink():
        raise ValueError("refuse symlinked .codex directory")
    target.parent.mkdir(exist_ok=True)
    # exclusive creation prevents races / silent replacement
    with target.open("x", encoding="utf-8", newline="\n") as fd:
        json.dump(config_obj, fd, indent=2)
        fd.write("\n")
    return target


def main():
    p = argparse.ArgumentParser(description="Codex App: review-first hook configuration")
    p.add_argument("--repo", required=True)
    p.add_argument("--apply", action="store_true", help="Create NEW hooks.json only")
    p.add_argument("--ack-reviewed-hooks", action="store_true")
    p.add_argument("--doctor", action="store_true")
    a = p.parse_args()
    report = doctor(a.repo)
    if a.doctor:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    c = config()
    if a.apply:
        target = install(a.repo, c, a.ack_reviewed_hooks)
        print(json.dumps({"created":str(target), "codex_app_end_to_end":"NOT_VERIFIED",
                          "action":"Open Codex App, inspect/trust hooks and perform actual call"},ensure_ascii=False))
    else:
        print(json.dumps({"proposal":c, "observed":report, "action":"Review first. Not installed."},
                         indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
