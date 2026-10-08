"""Chapter 20: release *candidate* gate. Never creates a GitHub release.

Manual attestation must be produced by a human who observed Windows and Codex;
the program does not infer real integration from JSONL records.
"""
import argparse
import json
from pathlib import Path
import operations

REQUIRED = ('real_codex_hook', 'cross_repo_isolation', 'claim_not_completion',
            'test_stale_on_change', 'backup_restore', 'local_dashboard',
            'safety_review')


def gate(repo, db, attestation=None):
    health = operations.check(repo, db)
    observations = {}
    if attestation is not None:
        raw = json.loads(Path(attestation).read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            raise ValueError('Attestation must be a JSON object')
        observations = raw.get('observations', {})
        if not isinstance(observations, dict):
            raise ValueError('observations must be an object')
    human = {name: (observations.get(name) is True) for name in REQUIRED}
    # JSON file is only a declaration. Review signed logs / screenshots manually.
    pending = [name for name, value in human.items() if not value]
    if health['status'] != 'CHECKS_OK':
        pending.append('operational_checks')
    # Gate can mark candidate 'READY_FOR_REVIEW', never certify evidence authenticity.
    return {'result': 'READY_FOR_HUMAN_RELEASE_REVIEW' if not pending else 'BLOCKED',
            'human_attested': human, 'remaining': pending, 'doctor': health,
            'warning': 'The JSON attestation cannot authenticate evidence, prove security, or publish software. '
                       'Release requires independent Windows review and owner approval.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', required=True)
    p.add_argument('--db', required=True)
    p.add_argument('--attestation')
    a = p.parse_args()
    print(json.dumps(gate(a.repo, a.db, a.attestation), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
