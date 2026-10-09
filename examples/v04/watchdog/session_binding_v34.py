"""Explicit Codex App session → approved Task Contract mapping. NOT identity attestation.
The hook removes cwd; user must manually associate a recent session with a Git repo.
Registry is private and outside any monitored Git worktree; no Hook auto-approval.
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import app_hook_v29
import evidence
import task_contract

MAX_TAIL = 8 * 1024 * 1024
SCHEMA = 1


def registry_path():
    return app_hook_v29.local_dir() / "task_bindings.json"


def alias_for(source, session):
    return hashlib.sha256((source + "\0" + session).encode("utf-8")).hexdigest()[:16]


def recent_events(log=None, limit=MAX_TAIL):
    path = Path(log or app_hook_v29.event_path())
    if not path.is_file():
        return []
    with path.open("rb") as f:
        size = f.seek(0, 2)
        start = max(0, size - limit)
        f.seek(start)
        data = f.read(limit)
    if start:
        split = data.find(b"\n")
        data = data[split + 1:] if split >= 0 else b""
    if not data.endswith(b"\n"):
        data = data[:data.rfind(b"\n") + 1] if b"\n" in data else b""
    out = []
    for line in data.splitlines():
        if len(line) > 1024 * 1024:
            continue
        try:
            x = json.loads(line.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            continue
        if isinstance(x, dict) and all(isinstance(x.get(k), str) and x[k] for k in
                                       ("source", "session_id", "received_at", "event")):
            out.append(x)
    return out


def sessions(log=None, now=None, max_age_hours=48):
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    known = {}
    for x in recent_events(log):
        try:
            stamp = datetime.fromisoformat(x["received_at"].replace("Z", "+00:00"))
            seconds = stamp.timestamp() if stamp.tzinfo else None
        except (ValueError, OverflowError, OSError):
            continue
        if seconds is None or not 0 <= now - seconds <= max_age_hours * 3600:
            continue
        src, sid = x["source"], x["session_id"]
        if len(src) > 150 or len(sid) > 150:
            continue
        alias = alias_for(src, sid)
        prev = known.get(alias)
        if prev and (prev["_source"], prev["_session"]) != (src, sid):
            raise ValueError("short alias hash collision")
        if not prev:
            known[alias] = {"alias": alias, "source_label": src, "events_seen": 0,
                            "latest_at": x["received_at"], "_source": src, "_session": sid}
        known[alias]["events_seen"] += 1
        if x["received_at"] > known[alias]["latest_at"]:
            known[alias]["latest_at"] = x["received_at"]
    return sorted(known.values(), key=lambda v: v["latest_at"], reverse=True)


def read_registry(path=None):
    p = Path(path or registry_path())
    if not p.exists():
        return {"schema_version": SCHEMA, "bindings": []}
    if p.is_symlink():
        raise ValueError("registry symlink not allowed")
    data = json.loads(p.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema_version") != SCHEMA or
            not isinstance(data.get("bindings"), list)):
        raise ValueError("invalid registry schema")
    return data


def private_registry(repo, registry=None):
    root = evidence.root_for(repo)
    dest = Path(registry or registry_path()).expanduser().resolve()
    if dest == root or root in dest.parents:
        raise ValueError("registry must stay outside the monitored repository")
    return root, dest


def bind(repo, alias, log=None, registry=None, approved=False, now=None):
    if not approved:
        raise ValueError("explicit --approve-binding required")
    root, dest = private_registry(repo, registry)
    contract, is_approved, _, _ = task_contract.load(root)
    if not is_approved:
        raise ValueError("task contract not approved")
    base = evidence.read_json(evidence.state_dir(root) / "baseline.json")
    if not isinstance(base, dict) or not isinstance(base.get("files"), dict):
        raise ValueError("Git baseline missing; run evidence.py baseline explicitly")
    matching = [x for x in sessions(log, now) if x["alias"] == alias]
    if len(matching) != 1:
        raise ValueError("unknown/stale session alias; review latest session list")
    record = matching[0]
    data = read_registry(dest)
    if any(x.get("alias") == alias for x in data["bindings"]):
        raise ValueError("session already bound; no silent reassignment")
    # Avoid one repo accidentally receiving multiple silent project identities.
    entry = {"alias": alias, "source": record["_source"],
             "session_id": record["_session"], "repo": str(root),
             "contract_sha256": task_contract.contract_hash(contract),
             "baseline_snapshot": base.get("snapshot_id"),
             "bound_at": datetime.now(timezone.utc).isoformat(),
             "authorization": "HUMAN_REVIEWED_MAPPING_NOT_SOURCE_AUTHENTICATION"}
    data["bindings"].append(entry)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        raise ValueError("registry symlink not allowed")
    evidence.atomic_json(dest, data)
    if os.name != "nt":
        os.chmod(dest, 0o600)
    return {"session_alias": alias, "bound": True, "contract_pinned": True,
            "source_authenticated": False, "repo_path_echoed": False}


def main():
    p = argparse.ArgumentParser(description="Human-reviewed binding; no Hook mutation")
    sub = p.add_subparsers(dest="action", required=True)
    x = sub.add_parser("sessions"); x.add_argument("--log")
    x = sub.add_parser("bind")
    x.add_argument("--repo", required=True)
    x.add_argument("--alias", required=True)
    x.add_argument("--log")
    x.add_argument("--registry")
    x.add_argument("--approve-binding", action="store_true")
    args = p.parse_args()
    if args.action == "sessions":
        rows = [{k: v for k, v in x.items() if not k.startswith("_")} for x in sessions(args.log)]
        print(json.dumps({"sessions": rows, "identity": "HOOK_SOURCE_UNVERIFIED"}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(bind(args.repo, args.alias, args.log, args.registry,
                              args.approve_binding), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
