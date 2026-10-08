"""Chapter 28: pinned, read-only expected-bytes checks for non-test artifacts.
Does not execute commands, fetch URLs or promote task_contract VERIFIED_COMPLETE.
Data and approval are stored in watchdog-owned state, outside observed repository.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

import evidence
import task_contract

LIMIT=20*1024*1024

def canonical(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def sha256(data):
    return hashlib.sha256(canonical(data)).hexdigest()

def safe_relative(path):
    if not isinstance(path,str) or not path or "\\" in path or "\x00" in path:
        return False
    posix=PurePosixPath(path)
    return not posix.is_absolute() and not any(x in (".","..") for x in path.split("/")) and len(posix.parts)>0 and ":" not in posix.parts[0]

def validate(plan):
    if not isinstance(plan,dict) or plan.get("schema_version")!=1:
        raise ValueError("plan schema")
    if not isinstance(plan.get("contract_sha256"),str):
        raise ValueError("missing contract hash")
    checks=plan.get("checks")
    if not isinstance(checks,list) or not checks:
        raise ValueError("non-empty artifact checks required")
    ids=set()
    for x in checks:
        if (not isinstance(x,dict) or not isinstance(x.get("id"),str)
                or not x["id"] or x["id"] in ids
                or not safe_relative(x.get("path"))
                or not isinstance(x.get("sha256"),str)
                or len(x["sha256"])!=64
                or any(c not in "0123456789abcdef" for c in x["sha256"])):
            raise ValueError("invalid check id/path/hash")
        ids.add(x["id"])
    return plan

def locations(repo):
    d=evidence.state_dir(repo)
    return d/"artifact_plan_v28.json",d/"artifact_approval_v28.json"

def store_plan(repo,plan):
    repo=evidence.root_for(repo)
    contract,approved,_,_=task_contract.load(repo)
    if not approved or plan.get("contract_sha256")!=task_contract.contract_hash(contract):
        raise ValueError("approved task contract mismatch")
    validate(plan)
    target,approval=locations(repo)
    if target.exists():
        raise FileExistsError("refuse to overwrite existing plan")
    evidence.atomic_json(target,plan)
    return {"status":"DRAFT_ONLY","sha256":sha256(plan)}

def approve_plan(repo):
    repo=evidence.root_for(repo)
    contract,approved,_,_=task_contract.load(repo)
    target,approval=locations(repo)
    plan=validate(evidence.read_json(target))
    if not approved or plan["contract_sha256"]!=task_contract.contract_hash(contract):
        raise ValueError("contract no longer approved/matching")
    evidence.atomic_json(approval,{"sha256":sha256(plan),"approved_at":evidence.timestamp()})
    return {"status":"APPROVED_PLAN","sha256":sha256(plan)}

def check_one(repo,entry,visible):
    path=entry["path"]
    if path not in visible:
        return "NOT_IN_GIT_VISIBLE_SCOPE"
    target=repo/path
    if not target.exists():
        return "MISSING"
    if target.is_symlink():
        return "UNSUPPORTED_SYMLINK"
    try:
        if repo not in target.resolve().parents or not target.is_file():
            return "UNSAFE_PATH"
        if target.stat().st_size>LIMIT:
            return "OVERSIZED"
        with target.open("rb") as fd:
            actual=hashlib.sha256()
            for chunk in iter(lambda:fd.read(1024*1024),b""):
                actual.update(chunk)
    except OSError:
        return "UNREADABLE"
    return "MATCHED_EXPECTED_BYTES" if actual.hexdigest()==entry["sha256"] else "MISMATCH"

def inspect(repo):
    repo=evidence.root_for(repo)
    contract,approved,_,_=task_contract.load(repo)
    target,approval=locations(repo)
    plan=evidence.read_json(target)
    if plan is None:
        return {"status":"NO_PLAN","checks":[]}
    validate(plan)
    approved_plan=evidence.read_json(approval)
    if (not approved or plan["contract_sha256"]!=task_contract.contract_hash(contract)
            or not approved_plan or approved_plan.get("sha256")!=sha256(plan)):
        return {"status":"BLOCKED_UNAPPROVED_OR_CHANGED_PLAN","checks":[]}
    base=evidence.read_json(evidence.state_dir(repo)/"baseline.json")
    if not base:
        return {"status":"NO_BASELINE","checks":[]}
    snapshot=evidence.snapshot(repo)
    checks=[{"id":x["id"],"path":x["path"],"result":check_one(repo,x,snapshot)}
            for x in plan["checks"]]
    contract_status=task_contract.acceptance_status(repo)
    if contract_status["violations"]:
        state="BLOCKED_PROTECTED_FILE_CHANGE"
    elif all(x["result"]=="MATCHED_EXPECTED_BYTES" for x in checks):
        state="ARTIFACT_BYTES_MATCH_ONLY"
    else:
        state="REVIEW_REQUIRED"
    return {"status":state,"checks":checks,"contract_stage":contract_status["stage"],
            "snapshot":evidence.fingerprint(snapshot),
            "limits":"Expected-byte match is NOT task completion, authorship, API behavior or release readiness."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    sub=p.add_subparsers(dest="action",required=True)
    a=sub.add_parser("init");a.add_argument("--plan",required=True)
    sub.add_parser("approve");sub.add_parser("status")
    args=p.parse_args()
    if args.action=="init":
        result=store_plan(args.repo,json.loads(Path(args.plan).read_text(encoding="utf8")))
    elif args.action=="approve":
        result=approve_plan(args.repo)
    else:
        result=inspect(args.repo)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
