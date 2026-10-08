"""Chapter 27: deterministic scope evidence plus untrusted goal-drift candidates.
No LLM inference, automatic approval or contract edits.
"""
import argparse
import json

import evidence
import scope_guard
import task_contract
from execution_v2 import read_projected

CODES={"POSSIBLE_REQUIREMENT_MISREAD","POSSIBLE_SCOPE_EXPANSION","POSSIBLE_GOAL_DEVIATION"}

def assess(repo, events=(), candidates=None):
    repo=evidence.root_for(repo)
    contract,approved,_,_=task_contract.load(repo)
    if not approved:
        return {"status":"BLOCKED_UNAPPROVED_CONTRACT","facts":[],"candidates":[]}
    evidence_ids={r.get("event_id") for r in events if isinstance(r,dict)
                  and r.get("event_id") and r.get("linkable") is True}
    scope=scope_guard.check(repo)
    facts=[{"code":x["code"],"path":x["path"],"basis":"git_snapshot_difference",
            "attribution":"UNKNOWN"} for x in scope.get("findings",[])]
    output=[]
    if candidates is not None:
        if not isinstance(candidates,dict) or candidates.get("schema_version")!=1:
            raise ValueError("candidates schema")
        if candidates.get("contract_sha256")!=task_contract.contract_hash(contract):
            raise ValueError("stale or unrelated task contract")
        acceptable={x["id"] for x in contract["acceptance"]}
        rows=candidates.get("items")
        if not isinstance(rows,list):
            raise ValueError("items must be list")
        for x in rows:
            if (not isinstance(x,dict) or x.get("code") not in CODES
                or x.get("acceptance_id") not in acceptable):
                raise ValueError("invalid review candidate")
            ids=x.get("event_ids")
            if not isinstance(ids,list) or not ids or any(
                     not isinstance(i,str) or i not in evidence_ids for i in ids):
                raise ValueError("missing/unlinkable candidate evidence")
            output.append({"code":x["code"],"acceptance_id":x["acceptance_id"],
                "event_ids":sorted(set(ids)), "verdict":"HUMAN_REVIEW_REQUIRED",
                "candidate_origin":"UNVERIFIED_INPUT"})
    return {"status":"REVIEW_REQUIRED" if facts or output else
            "NO_FINDINGS_IN_OBSERVED_SCOPE",
            "facts":facts, "candidates":output,
            "scope_status":scope["status"],
            "limits":"Git differences cannot attribute an author. Candidates do not prove semantic deviation."}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--events",help="private sanitized JSONL")
    p.add_argument("--candidates",help="private optional review suggestions JSON")
    a=p.parse_args()
    candidates=json.loads(open(a.candidates,encoding="utf8").read()) if a.candidates else None
    events=list(read_projected(a.events)) if a.events else []
    print(json.dumps(assess(a.repo,events,candidates),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
