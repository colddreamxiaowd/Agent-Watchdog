"""Chapter 17: evidence-labelled supervision, not an automatic Agent controller.

No secrets, prompt bodies or tool arguments are read or saved. A heuristic
requires manual review and never certifies an Agent as stuck or off-target.
"""
import argparse
import json
from pathlib import Path

import evidence
import journal
import progress
import scope_guard
import task_contract


def recent_events(db=journal.DEFAULT_DB, limit=30):
    """Return at most N *sanitized* events from a pre-existing SQLite file.

    Do not create a database while only displaying the status.
    """
    import sqlite3
    db = Path(db)
    if not db.is_file():
        return []
    with sqlite3.connect(str(db), timeout=2) as con:
        values = con.execute(
            "SELECT payload FROM events ORDER BY rowid DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [json.loads(value[0]) for value in reversed(values)]


def diagnose(repo, db=journal.DEFAULT_DB, events=None):
    """Evaluate independently checked facts before optional weak heuristics."""
    repo = evidence.root_for(repo)
    rows = list(events) if events is not None else recent_events(db)
    facts, hypotheses = [], []
    state = {'repo': str(repo), 'checks': 'UNAVAILABLE', 'scope': 'UNAVAILABLE'}
    try:
        contract = task_contract.acceptance_status(repo)
        state['checks'] = contract['acceptance']
        state['stage'] = contract['stage']
        for name, status in contract['acceptance'].items():
            if status in ('STALE', 'FAILED', 'INCONCLUSIVE'):
                facts.append({'code': 'ACCEPTANCE_' + status, 'severity': 'medium',
                              'evidence': {'id': name, 'status': status},
                              'next_step': '人工检查并显式运行已批准的验收项'})
        if not contract['approved']:
            facts.append({'code': 'UNTRUSTED_CONTRACT', 'severity': 'high',
                          'evidence': {'approved': False}, 'next_step': '重新检查任务契约并由用户批准'})
    except (RuntimeError, ValueError, OSError) as exc:
        state['stage'] = 'UNKNOWN'
        state['contract_error_type'] = type(exc).__name__
    try:
        scope = scope_guard.check(repo)
        state['scope'] = scope['status']
        for finding in scope['findings']:
            facts.append({'code': finding['code'], 'severity': finding['severity'],
                          'evidence': {'path': finding['path']},
                          'next_step': '人工核实变更来源及是否获准'})
    except (RuntimeError, ValueError, OSError) as exc:
        state['scope_error_type'] = type(exc).__name__
    # Tool type equality is *not* identical actions, identical arguments, or failure.
    # Restrict to one exact session and one source; never pool unrelated agents.
    last = rows[-6:]
    if (len(last) == 6 and all(x.get('tool') and x.get('session_id') and x.get('source') for x in last)
        and len({(x.get('session_id'), x.get('source'), x.get('tool')) for x in last}) == 1):
        hypotheses.append({'code': 'POSSIBLE_REPETITION', 'severity': 'low',
                           'kind': 'heuristic', 'confidence': 'NOT_CALIBRATED',
                           'evidence': {'tool_category': last[-1]['tool'], 'count': 6,
                                        'source': last[-1]['source'], 'session_id': last[-1]['session_id']},
                           'next_step': '查看允许查阅的执行上下文；不能据此认定死循环'})
    return {'state': state, 'facts': facts, 'hypotheses': hypotheses,
            'recent_events': len(rows), 'limits': [
                'Git path differences do not establish which actor made the change',
                'Event metadata cannot prove repeated failures or semantic drift',
                'No automatic kill/retry/rollback or model-based verdict',
                'NOT_TESTED and UNKNOWN are not success',
            ]}


def main():
    p = argparse.ArgumentParser(description='Evidence-first, bounded supervision')
    p.add_argument('--repo', required=True)
    p.add_argument('--db', default=str(journal.DEFAULT_DB))
    args = p.parse_args()
    print(json.dumps(diagnose(args.repo, args.db), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
