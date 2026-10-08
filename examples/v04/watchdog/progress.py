"""Chapter 15: milestone-to-acceptance mapping with explicit evidence bounds.

Reads human-approved Task Contract and V0.6 acceptance status. Never infers
percentage of a natural-language project from tool call counts.
"""
import argparse
import json
import evidence
import task_contract


def compute(repo):
    repo = evidence.root_for(repo)
    contract, approved, _, _ = task_contract.load(repo)
    if not approved:
        return {'state': 'UNTRUSTED_CONTRACT', 'milestones': [], 'verified_checks': 0,
                'total_checks': 0, 'scope': 'No progress claim while approval is invalid'}
    status = task_contract.acceptance_status(repo)
    checks = status['acceptance']
    milestones = contract.get('milestones')
    if milestones is None:
        milestones = [{'id': x['id'], 'title': x['description'], 'acceptance_ids': [x['id']]}
                      for x in contract['acceptance']]
    used_ids = set()
    rows = []
    for milestone in milestones:
        if (not isinstance(milestone, dict) or not isinstance(milestone.get('id'), str)
                or not isinstance(milestone.get('title'), str)
                or not isinstance(milestone.get('acceptance_ids'), list)
                or not milestone['acceptance_ids']
                or any(x not in checks for x in milestone['acceptance_ids'])):
            raise ValueError('Invalid milestones: acceptance_ids must refer to contract acceptance checks')
        if milestone['id'] in used_ids:
            raise ValueError('Duplicate milestone id')
        used_ids.add(milestone['id'])
        values = {name: checks[name] for name in milestone['acceptance_ids']}
        level = ('VERIFIED' if all(x == 'PASSED' for x in values.values()) else
                 'NEEDS_RECHECK' if any(x in {'STALE', 'INCONCLUSIVE'} for x in values.values()) else
                 'FAILED' if any(x == 'FAILED' for x in values.values()) else 'PENDING')
        rows.append({'id': milestone['id'], 'title': milestone['title'], 'state': level, 'evidence': values})
    verified = sum(x == 'PASSED' for x in checks.values())
    return {'state': status['stage'], 'verified_checks': verified,
            'total_checks': len(checks), 'milestones': rows,
            'scope': 'Number of contract acceptance checks verified, NOT percentage of task work',
            'snapshot': status['snapshot']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    args = p.parse_args()
    print(json.dumps(compute(args.repo), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
