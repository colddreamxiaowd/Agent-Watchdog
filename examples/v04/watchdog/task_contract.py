"""V0.5-0.6: pinned human-approved task contract and independent acceptance.
The contract controls what tests may be run, but nothing runs on a Hook event.
"""
import argparse
import fnmatch
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import evidence

SCHEMA_VERSION = 1


def validate(contract):
    if not isinstance(contract, dict) or contract.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("expected schema_version=1")
    if not isinstance(contract.get("goal"), str) or not contract["goal"].strip():
        raise ValueError("goal must be a nonempty string")
    constraints = contract.get("protected_paths", [])
    if not isinstance(constraints, list) or not all(isinstance(x, str) and x for x in constraints):
        raise ValueError("protected_paths must be a string list")
    checks = contract.get("acceptance")
    if not isinstance(checks, list) or not checks:
        raise ValueError("acceptance must be a nonempty list")
    ids = []
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("acceptance items must be objects")
        ident, argv = check.get("id"), check.get("command")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("acceptance ids must be unique nonempty strings")
        if not isinstance(check.get("description"), str) or not check["description"]:
            raise ValueError("acceptance descriptions required")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ValueError("command must be nonempty argv string list, not a shell command")
        ids.append(ident)
    return contract


def locations(repo):
    state = evidence.state_dir(repo)
    return state / "task_contract.json", state / "contract_approval.json", state / "acceptance_results.json", state / "agent_claim.json"


def contract_hash(contract):
    data = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load(repo):
    path, approved_path, results_path, claim_path = locations(repo)
    raw = evidence.read_json(path)
    if raw is None:
        raise RuntimeError("No task contract: run init")
    contract = validate(raw)
    approval = evidence.read_json(approved_path)
    valid = bool(approval and approval.get("sha256") == contract_hash(contract))
    return contract, valid, evidence.read_json(results_path) or {}, evidence.read_json(claim_path)


def init(repo, path):
    contract = validate(json.loads(Path(path).read_text(encoding="utf-8")))
    target, approve_file, result_file, claim_file = locations(repo)
    if target.exists():
        raise RuntimeError("Contract already exists; deliberate updates require --replace then approve")
    evidence.atomic_json(target, contract)
    for stale in (approve_file, result_file, claim_file):
        stale.unlink(missing_ok=True)
    print("Draft saved outside repository; inspect and run approve explicitly.")


def approve(repo):
    contract_path, approval_path, results_path, claim_path = locations(repo)
    contract = validate(evidence.read_json(contract_path))
    evidence.atomic_json(approval_path, {"sha256": contract_hash(contract), "approved_at": evidence.timestamp()})
    # Old evidence cannot be carried to a newly approved contract version.
    results_path.unlink(missing_ok=True)
    claim_path.unlink(missing_ok=True)
    print("Approved contract", contract_hash(contract)[:16], "| previous acceptance results cleared")


def acceptance_status(repo):
    contract, approved, saved, claim = load(repo)
    file_snapshot = evidence.snapshot(repo)
    current = evidence.fingerprint(file_snapshot)
    base = evidence.read_json(evidence.state_dir(repo) / "baseline.json")
    changed = evidence.diff_files(base["files"], file_snapshot) if base else []
    violations = sorted(x for x in changed if any(fnmatch.fnmatchcase(x, p) for p in contract["protected_paths"]))
    checks = {}
    for a in contract["acceptance"]:
        data = saved.get(a["id"])
        if not data:
            status = "NOT_TESTED"
        elif data.get("before") != data.get("after"):
            status = "INCONCLUSIVE"
        elif data.get("after") != current:
            status = "STALE"
        elif data.get("exit_code") == 0:
            status = "PASSED"
        else:
            status = "FAILED"
        checks[a["id"]] = status
    completed = bool(approved and base is not None and not violations
                     and all(x == "PASSED" for x in checks.values()))
    stage = ("BLOCKED" if not approved or violations else
             "VERIFIED_COMPLETE" if completed else
             "CLAIMED_COMPLETE" if claim else "IN_PROGRESS")
    return {
        "repo": str(repo), "goal": contract["goal"], "approved": approved,
        "contract_sha256": contract_hash(contract), "snapshot": current,
        "baseline_available": base is not None, "violations": violations,
        "acceptance": checks, "agent_claim": bool(claim), "stage": stage,
        "limits": "Only configured tests and Git-visible files; no semantic completeness proof",
    }


def run_one(repo, name, timeout=180):
    contract, approved, results, _ = load(repo)
    if not approved:
        raise RuntimeError("Contract changed or not approved")
    matches = [x for x in contract["acceptance"] if x["id"] == name]
    if not matches:
        raise ValueError("Unknown acceptance ID")
    argv = matches[0]["command"]
    print("WARNING: Running approved local test code; use only a trusted test repository.")
    before = evidence.fingerprint(evidence.snapshot(repo))
    try:
        result = subprocess.run(argv, cwd=repo, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", shell=False,
                                timeout=max(1, min(1800, timeout)), check=False)
        code = result.returncode
        output = (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        code, output = 124, "Test timeout; not a pass"
    except OSError as e:
        code, output = 127, "Could not launch test: " + type(e).__name__
    after = evidence.fingerprint(evidence.snapshot(repo))
    results[name] = {"before": before, "after": after, "exit_code": code,
                     "at": evidence.timestamp(), "command": argv}
    evidence.atomic_json(locations(repo)[2], results)
    print(output[-2000:] or "(no output)")  # not saved
    print("Exit code:", code, "| current:", acceptance_status(repo)["acceptance"][name])
    return code


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("init"); x.add_argument("--contract", required=True)
    sub.add_parser("approve"); sub.add_parser("status")
    x = sub.add_parser("verify"); x.add_argument("id"); x.add_argument("--timeout", type=int, default=180)
    x = sub.add_parser("claim"); x.add_argument("--text", default="Agent says task is finished")
    args = p.parse_args()
    repo = evidence.root_for(args.repo)
    if args.command == "init":
        init(repo, args.contract)
    elif args.command == "approve":
        approve(repo)
    elif args.command == "verify":
        run_one(repo, args.id, args.timeout)
    elif args.command == "claim":
        evidence.atomic_json(locations(repo)[3], {"time": evidence.timestamp(), "text": args.text[:300]})
        print("Claim recorded; NOT independently verified")
    else:
        print(json.dumps(acceptance_status(repo), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print("ERROR:", str(e), file=sys.stderr)
        sys.exit(2)
