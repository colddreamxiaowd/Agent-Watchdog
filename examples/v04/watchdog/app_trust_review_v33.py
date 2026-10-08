"""Codex App Hook trust preflight (v33). READ-ONLY, NO TRUST/INSTALL ACTION.
Does not read Hook input, user prompts, commands or tool output, and does not
claim that a config is trusted. Python 3.9+; TOML inspection needs Python 3.11.
"""
import argparse
import json
import os
import sys
from pathlib import Path

EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "Stop", "SessionEnd")


def codex_home(environ=None, home=None):
    env = os.environ if environ is None else environ
    if env.get("CODEX_HOME"):
        return Path(env["CODEX_HOME"]).expanduser().resolve(), "CODEX_HOME"
    return (Path.home() if home is None else Path(home)).expanduser().resolve() / ".codex", "default_user_home"


def describe_hookfile(path, label):
    """Return only event counts and flags; NEVER print command strings."""
    entry = {"layer": label, "exists": path.is_file(), "events": {},
             "commands": 0, "windows_override_commands": 0, "warnings": []}
    if path.is_symlink():
        entry["warnings"].append("SYMLINK_HOOK_CONFIG_REVIEW_MANUALLY")
    if not path.is_file():
        return entry
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        entry["warnings"].append("UNREADABLE_OR_INVALID_HOOKS_JSON")
        return entry
    if not isinstance(data, dict) or not isinstance(data.get("hooks"), dict):
        entry["warnings"].append("MISSING_HOOKS_MAP")
        return entry
    hooks = data["hooks"]
    for event, entries in hooks.items():
        if not isinstance(event, str) or not isinstance(entries, list):
            entry["warnings"].append("INVALID_EVENT_SHAPE")
            continue
        entry["events"][event] = len(entries)
        if event not in EVENTS:
            entry["warnings"].append("OTHER_EVENT_PRESENT")
        for group in entries:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                entry["warnings"].append("INVALID_MATCHER_GROUP")
                continue
            for h in group["hooks"]:
                if not isinstance(h, dict) or h.get("type") != "command":
                    entry["warnings"].append("UNSUPPORTED_OR_INVALID_HANDLER")
                    continue
                entry["commands"] += 1
                win = h.get("commandWindows")
                unix = h.get("command")
                if isinstance(win, str) and win.strip():
                    entry["windows_override_commands"] += 1
                    if '"' in win:
                        entry["warnings"].append("WINDOWS_COMMAND_HAS_QUOTES_REVIEW_LAUNCH_COMPATIBILITY")
                    if not win.strip().lower().startswith("cmd.exe /d /s /c "):
                        entry["warnings"].append("WINDOWS_COMMAND_WRAPPER_DIFFERS_FROM_WORKING_EXAMPLE")
                else:
                    entry["warnings"].append("NO_EXPLICIT_COMMAND_WINDOWS")
                    if isinstance(unix, str) and '"' in unix:
                        entry["warnings"].append("QUOTED_DEFAULT_COMMAND_WINDOWS_RISK")
                if event == "SessionEnd" and isinstance(h.get("timeout"), (int, float)):
                    if h["timeout"] > 3:
                        entry["warnings"].append("SESSION_END_TIMEOUT_GT_3")
    entry["warnings"] = sorted(set(entry["warnings"]))
    return entry


def describe_toml(path, label):
    """TOML can contain sensitive data. Parse locally; return no config values."""
    out = {"layer": label, "exists": path.is_file(), "inline_hook_events": {},
           "warnings": []}
    if not path.is_file():
        return out
    try:
        import tomllib
    except ImportError:
        out["warnings"].append("TOML_PARSE_UNAVAILABLE_PYTHON_LT_311")
        return out
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, UnicodeError, ValueError):
        out["warnings"].append("TOML_PARSE_ERROR")
        return out
    hooks = data.get("hooks", {})
    if isinstance(hooks, dict):
        for event, value in hooks.items():
            if event == "state":  # trust hashes are private and not external proof
                continue
            if event == "managed_dir" or event == "windows_managed_dir":
                continue
            if isinstance(value, (list, dict)):
                out["inline_hook_events"][str(event)] = (len(value) if isinstance(value, list) else 1)
    return out


def audit(global_home=None, project=None, environ=None):
    if global_home is None:
        global_home, origin = codex_home(environ)
    else:
        global_home, origin = Path(global_home).expanduser().resolve(), "explicit_cli_argument"
    layers = [("global", Path(global_home))]
    if project is not None:
        layers.append(("project", Path(project).expanduser().resolve() / ".codex"))
    files = [describe_hookfile(layer / "hooks.json", name) for name, layer in layers]
    tomls = [describe_toml(layer / "config.toml", name) for name, layer in layers]
    counts = {}
    for record in files:
        for event, n in record["events"].items():
            counts[event] = counts.get(event, 0) + n
    for t in tomls:
        for event, n in t["inline_hook_events"].items():
            counts[event] = counts.get(event, 0) + n
    # Matches across multiple config sources run (may overlap); can't assert
    # they are duplicate commands without reading command bodies.
    warnings = []
    if any(n > 1 for n in counts.values()):
        warnings.append("MULTIPLE_EVENT_GROUPS_MAY_DISPATCH_TOGETHER")
    if not files[0]["exists"] and not tomls[0]["inline_hook_events"]:
        warnings.append("NO_GLOBAL_HOOKS_DETECTED_AT_SELECTED_CODEX_HOME")
    if any(x["exists"] for x in files[1:]) or any(x["inline_hook_events"] for x in tomls[1:]):
        warnings.append("PROJECT_HOOKS_PRESENT_ALONGSIDE_GLOBAL_OR_INDEPENDENT")
    return {"mode": "READ_ONLY_PRETRUST_CHECK", "codex_home_source": origin,
            "layers": files, "toml_layers": tomls, "matching_group_counts": counts,
            "warnings": warnings,
            "hook_trust": "NOT_VERIFIED_USE_INTERACTIVE_CODEX_CLI_SLASH_HOOKS",
            "app_delivery": "NOT_VERIFIED_BY_THIS_TOOL",
            "next": "Use interactive codex CLI with the SAME CODEX_HOME; type /hooks; review exact definitions; restart Desktop and confirm fresh events WITHOUT any trust bypass.",
            "privacy": "Command text, config paths, trust hashes, model settings and environment values are never included in this JSON."}


def main():
    p = argparse.ArgumentParser(description="Read-only Codex App hook trust-layer diagnostics")
    p.add_argument("--codex-home", help="Override for inspecting a specific Codex home; never modifies it")
    p.add_argument("--project", help="Optional repository root to detect layered project hooks")
    a = p.parse_args()
    print(json.dumps(audit(global_home=a.codex_home, project=a.project),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
