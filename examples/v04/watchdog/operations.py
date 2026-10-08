"""Chapter 19: local operational doctor, handoff and explicit backup.

No scheduling, logging of secrets, process killing, or autonomous recovery.
"""
import argparse
import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import evidence
import journal
import watchdog_cli


def check(repo, db=journal.DEFAULT_DB, report_age_seconds=120):
    repo = evidence.root_for(repo)
    info = {'repo': str(repo), 'database': 'MISSING', 'git_report': 'MISSING',
            'alerts': [], 'status': 'ACTION_REQUIRED'}
    saved = evidence.read_json(evidence.state_dir(repo) / 'bridge_report.json')
    if saved:
        try:
            stamp = datetime.fromisoformat(saved['scanned_at'])
            if stamp.tzinfo is None:
                raise ValueError('naive timestamp')
            seconds = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
            info['git_report'] = ('FRESH' if -30 <= seconds <= report_age_seconds else 'STALE')
        except (KeyError, TypeError, ValueError):
            info['git_report'] = 'UNTRUSTED_TIMESTAMP'
    if Path(db).is_file():
        try:
            with sqlite3.connect(str(db), timeout=3) as con:
                integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
                events = con.execute('SELECT COUNT(*) FROM events').fetchone()[0]
            info['database'] = 'OK' if integrity == 'ok' else 'FAILED_INTEGRITY'
            info['event_rows'] = events
        except (sqlite3.Error, OSError):
            info['database'] = 'READ_FAILED'
    if info['database'] != 'OK':
        info['alerts'].append('事件账本不可用；不能声称完整的历史记录')
    if info['git_report'] != 'FRESH':
        info['alerts'].append('Git 状态快照缺失或不新鲜；人工启动 Bridge 排查')
    info['status'] = 'CHECKS_OK' if not info['alerts'] else 'ACTION_REQUIRED'
    info['limits'] = 'CHECKS_OK means checks readable, not live Codex integration verified'
    return info


def archive(repo, db, dest):
    """Create an offline backup, never modify target repo or delete originals."""
    repo = evidence.root_for(repo)
    source = Path(db)
    if not source.is_file():
        raise FileNotFoundError('No existing database to back up')
    target = Path(dest).resolve()
    if target.exists():
        raise FileExistsError('Refusing to overwrite existing backup')
    if target.is_relative_to(repo):
        raise ValueError('Backups must be outside the monitored repository')
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        journal.backup(source, target)
        with sqlite3.connect(str(target)) as con:
            if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup failed integrity verification')
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {'path': str(target), 'bytes': target.stat().st_size, 'status': 'VERIFIED_BACKUP'}


def main():
    p = argparse.ArgumentParser(description='Local Agent Watchdog operational checks')
    p.add_argument('--repo', required=True)
    p.add_argument('--db', default=str(journal.DEFAULT_DB))
    sub = p.add_subparsers(dest='action', required=True)
    sub.add_parser('doctor')
    backup_parser = sub.add_parser('backup')
    backup_parser.add_argument('--out', required=True)
    args = p.parse_args()
    result = check(args.repo, args.db) if args.action == 'doctor' else archive(args.repo, args.db, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
