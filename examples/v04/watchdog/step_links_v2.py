"""Round 24: human-reviewed event-to-step links, never auto-upgrade acceptance."""
import argparse
import json
from pathlib import Path

import evidence
import task_contract
from execution_v2 import read_projected


def build(repo, events, links):
    repo = evidence.root_for(repo)
    contract, approved, _, _ = task_contract.load(repo)
    status = task_contract.acceptance_status(repo)
    # No unapproved contract is accepted as an authority.
    if not approved:
        raise ValueError("task contract must be explicitly approved")
    if not isinstance(links, dict) or links.get("schema_version") != 1:
        raise ValueError("links must be schema_version=1")
    if links.get("contract_sha256") != task_contract.contract_hash(contract):
        raise ValueError("links contract hash mismatches current approval")
    anchors = links.get("links")
    if not isinstance(anchors, list):
        raise ValueError("links must be a list")
    known = {row.get("event_id"): row for row in events
             if isinstance(row, dict) and row.get("event_id") and row.get("linkable") is True}
    steps = {m["id"] for m in contract.get("milestones", [])
             if isinstance(m, dict) and isinstance(m.get("id"), str)}
    if not steps:
        steps = {a["id"] for a in contract["acceptance"]}
    acceptances = {a["id"] for a in contract["acceptance"]}
    output = []
    seen = set()
    for link in anchors:
        if not isinstance(link, dict):
            raise ValueError("link must be object")
        step, event_id, check = link.get("step_id"), link.get("event_id"), link.get("acceptance_id")
        if (not isinstance(step, str) or step not in steps or
                not isinstance(event_id, str) or
                check is not None and check not in acceptances):
            raise ValueError("unknown step or acceptance id")
        pair = (step, event_id, check)
        if pair in seen:
            continue
        seen.add(pair)
        event = known.get(event_id)
        output.append({"step_id": step, "event_id": event_id,
                       "association": "LINKED_MANUALLY" if event else "UNLINKED",
                       "source": event.get("source") if event else None,
                       "session_id": event.get("session_id") if event else None,
                       "turn_id": event.get("turn_id") if event else None,
                       "tool": event.get("tool") if event else None,
                       "acceptance_id": check,
                       "acceptance_status": status["acceptance"].get(check) if check else "NOT_LINKED",
                       "meaning": "Event association is not proof of task completion"})
    return {"contract_sha256": links["contract_sha256"], "approved": True,
            "contract_stage": status["stage"], "links": output,
            "unlinked": sum(x["association"] == "UNLINKED" for x in output),
            "scope": "Only human links + existing independent acceptance snapshot"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--events", required=True)
    p.add_argument("--links", required=True, help="Private file outside observed project")
    args = p.parse_args()
    links_path = Path(args.links).resolve()
    if links_path == evidence.root_for(args.repo) or evidence.root_for(args.repo) in links_path.parents:
        p.error("link records must be outside the observed repository")
    links = json.loads(links_path.read_text(encoding="utf-8"))
    print(json.dumps(build(args.repo, read_projected(args.events), links), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
