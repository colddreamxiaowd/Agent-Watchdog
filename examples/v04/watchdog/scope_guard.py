"""Chapter 16: bounded path-scope and protected-file review.

A deviation *signal* is NOT evidence that Codex made a change or that a
natural-language objective was semantically violated.
"""
import argparse
import fnmatch
import json
import evidence
import task_contract


def check(repo):
    repo = evidence.root_for(repo)
    contract, approved, _, _ = task_contract.load(repo)
    if not approved:
        return {'status': 'UNTRUSTED_CONTRACT', 'findings': [],
                'scope': 'Stop: contract approval is absent or invalid'}
    base = evidence.read_json(evidence.state_dir(repo) / 'baseline.json')
    if base is None:
        return {'status': 'NO_BASELINE', 'findings': [], 'scope': 'Cannot compare file changes'}
    now = evidence.snapshot(repo)
    changed = evidence.diff_files(base['files'], now)
    protected = set(contract.get('protected_paths') or [])
    allowed = contract.get('allowed_paths')
    if allowed is not None and (not isinstance(allowed, list) or
                                not all(isinstance(x, str) and x for x in allowed)):
        raise ValueError('allowed_paths must be a string list')
    findings = []
    for path in changed:
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in protected):
            findings.append({'path': path, 'code': 'PROTECTED_CHANGE',
                             'kind': 'deterministic_snapshot_difference', 'severity': 'high'})
        elif allowed is not None and not any(fnmatch.fnmatchcase(path, pattern) for pattern in allowed):
            findings.append({'path': path, 'code': 'OUTSIDE_DECLARED_PATH_SCOPE',
                             'kind': 'needs_human_review', 'severity': 'medium'})
    return {'status': 'FINDINGS' if findings else ('NOT_CONFIGURED' if allowed is None else 'NO_FINDINGS_IN_SCOPE'),
            'changed': changed, 'findings': findings,
            'scope': 'Git-visible worktree vs saved baseline, cannot attribute author or infer semantic drift',
            'allowed_paths_configured': allowed is not None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    a = p.parse_args()
    print(json.dumps(check(a.repo), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
