"""Chapter 14: OPT-IN sanitized import of *exported* Codex App Server notifications.

Never launches App Server, handles approvals, or persists raw output/commands.
Exports can be fabricated; source string is NOT an authenticity guarantee.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from hook_logger_v04 import append, clean

METHODS = {'thread/started', 'turn/started', 'turn/completed', 'turn/failed',
           'item/started', 'item/completed', 'item/updated'}
CATEGORIES = {'commandExecution', 'fileChange', 'agentMessage', 'reasoning',
              'mcpToolCall', 'webSearch', 'dynamicToolCall', 'plan', 'collabAgentToolCall'}


def project(row):
    if not isinstance(row, dict):
        return None
    method = row.get('method')
    if method not in METHODS:
        return None
    params = row.get('params')
    if not isinstance(params, dict):
        params = {}
    item = params.get('item')
    if not isinstance(item, dict):
        item = {}
    thread = params.get('thread')
    if not isinstance(thread, dict):
        thread = {}
    turn = params.get('turn')
    if not isinstance(turn, dict):
        turn = {}
    item_type = item.get('type')
    return {
        'source': 'app_server_export_unverified',
        'received_at': datetime.now(timezone.utc).isoformat(),
        'event': method,
        'session_id': clean(params.get('threadId') or thread.get('id'), 120),
        'turn_id': clean(params.get('turnId') or turn.get('id'), 120),
        'tool': item_type if item_type in CATEGORIES else None,
        'cwd': None,  # Never infer the destination project from an exported trace.
        'tool_use_id': clean(item.get('id'), 120),
    }


def import_export(input_path, out, max_line_bytes=1_000_000):
    src, dst = Path(input_path).resolve(), Path(out).resolve()
    if src == dst:
        raise ValueError('Input and output must be different files')
    accepted, rejected = 0, 0
    with src.open('rb') as fh:
        for line in fh:
            if len(line) > max_line_bytes:
                rejected += 1
                continue
            try:
                row = json.loads(line)
                safe = project(row)
            except (ValueError, UnicodeDecodeError):
                safe = None
            if safe is None:
                rejected += 1
                continue
            append(safe, dst)
            accepted += 1
    return {'imported': accepted, 'skipped': rejected, 'provenance': 'explicit_offline_export'}


def main():
    p = argparse.ArgumentParser(description='Import a manually exported App Server NDJSON stream')
    p.add_argument('input_file', help='Explicitly supplied newline-delimited App Server messages')
    p.add_argument('--out', required=True, help='Sanitized output, never commit logs')
    args = p.parse_args()
    print(json.dumps(import_export(args.input_file, args.out), ensure_ascii=False))


if __name__ == '__main__':
    main()
