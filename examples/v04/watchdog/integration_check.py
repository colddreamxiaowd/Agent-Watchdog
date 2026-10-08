"""Chapter 13: bounded integration readiness, never asserts 'real Codex verified'.

The report distinguishes configuration, locally observed artifacts and human-attested
end-to-end tests. It invokes an independent Git scan but never starts Codex or tests.
"""
import argparse
import json
from pathlib import Path
import bridge
import evidence
import journal
import task_contract


def inspect(repo, log=None, db=None):
    repo = evidence.root_for(repo)
    log = Path(log) if log else bridge.LOG
    db = Path(db) if db else journal.DEFAULT_DB
    result = {"repo": str(repo), "hook_log_exists": log.is_file(),
              "hook_records_observed": 0, "hook_events_are_authenticated": False,
              "journal_exists": db.is_file(), "journal_integrity": "NOT_CHECKED",
              "contract_stage": "NO_CONTRACT", "git": {},
              "real_codex_end_to_end": "NOT_VERIFIED",
              "reasons": ["A JSONL record does not authenticate its producer; verify the live Codex session manually."]}
    if log.is_file():
        # Complete JSONL lines only, newest 1MiB; never keep raw parameters or prompts.
        with log.open('rb') as fh:
            n = fh.seek(0, 2)
            start = max(0, n - 1024 * 1024)
            fh.seek(start)
            if start:
                fh.readline()
            for line in fh:
                if not line.endswith(b'\n'):
                    continue
                try:
                    row = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    continue
                if isinstance(row, dict) and row.get('event') and bridge.tracked_repo_event(row, repo):
                    result['hook_records_observed'] += 1
    try:
        scan = bridge.scan(repo, 'integration-readiness')
        result['git'] = {k: scan[k] for k in ('has_baseline', 'changed', 'protected', 'test_status', 'snapshot')}
    except (RuntimeError, OSError, ValueError) as exc:
        result['git'] = {'error_type': type(exc).__name__}
    try:
        result['contract_stage'] = task_contract.acceptance_status(repo)['stage']
    except (RuntimeError, OSError, ValueError):
        pass
    if db.is_file():
        try:
            result['journal_integrity'] = journal.summary(db)['integrity']
        except (RuntimeError, OSError, ValueError):
            result['journal_integrity'] = 'FAILED_TO_READ'
    return result


def main():
    p = argparse.ArgumentParser(description='Read-only Agent Watchdog integration readiness')
    p.add_argument('--repo', required=True)
    p.add_argument('--log')
    p.add_argument('--db')
    args = p.parse_args()
    print(json.dumps(inspect(args.repo, args.log, args.db), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
