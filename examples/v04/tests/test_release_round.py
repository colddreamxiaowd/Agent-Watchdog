"""Chapters 17-20: synthetic repos only, no Codex, no external network."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULES = Path(__file__).resolve().parents[1] / 'watchdog'
sys.path.insert(0, str(MODULES))
import bridge
import dashboard
import evidence
import journal
import operations
import release_gate
import supervision
import task_contract


class FinalRoundTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)
        self.repo = self.root / 'demo'
        self.repo.mkdir()
        for cmd in (('git','init'),('git','config','user.email','course@example.test'),
                    ('git','config','user.name','Course')):
            subprocess.run(cmd, cwd=self.repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (self.repo/'GOAL.md').write_text('Protected\n', encoding='utf-8')
        (self.repo/'app.py').write_text('VALUE = 1\n', encoding='utf-8')
        subprocess.run(['git','add','.'],cwd=self.repo,check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['git','commit','-m','baseline'],cwd=self.repo,check=True,stdout=subprocess.DEVNULL)
        # Normalize once: Windows Git may return a canonical path different from the temporary alias.
        self.repo = evidence.root_for(self.repo)
        evidence.atomic_json(evidence.state_dir(self.repo) / 'baseline.json', {'files': evidence.snapshot(self.repo)})
        self.db = self.root / 'events.sqlite3'

    def pin(self):
        data = {'schema_version':1,'goal':'Test application','protected_paths':['GOAL.md'],
                'allowed_paths':['app.py'],
                'acceptance':[{'id':'A1','description':'Trivial stable test',
                               'command':[sys.executable, '-c','print(1)']} ]}
        path = self.root / 'contract.json'
        path.write_text(json.dumps(data),encoding='utf-8')
        task_contract.init(self.repo,path)
        task_contract.approve(self.repo)

    def test_17_no_repeated_tool_without_session_and_source(self):
        self.assertEqual(supervision.diagnose(self.repo, events=[{'tool':'Bash'}]*6)['hypotheses'], [])

    def test_17_different_sessions_not_combined(self):
        rows=[{'session_id':str(i%2),'source':'codex_hook','tool':'Bash'} for i in range(6)]
        self.assertEqual(supervision.diagnose(self.repo, events=rows)['hypotheses'], [])

    def test_17_same_session_is_low_confidence_heuristic(self):
        rows=[{'session_id':'one','source':'codex_hook','tool':'Bash'} for _ in range(6)]
        report=supervision.diagnose(self.repo,events=rows)
        self.assertEqual(report['hypotheses'][0]['code'],'POSSIBLE_REPETITION')
        self.assertEqual(report['hypotheses'][0]['kind'],'heuristic')
        self.assertEqual(report['hypotheses'][0]['confidence'],'NOT_CALIBRATED')

    def test_17_scope_violation_is_fact_not_attribution(self):
        self.pin()
        (self.repo/'GOAL.md').write_text('Changed\n',encoding='utf-8')
        r=supervision.diagnose(self.repo, events=[])
        self.assertTrue(any(x['code']=='PROTECTED_CHANGE' for x in r['facts']))
        self.assertIn('do not establish',r['limits'][0])

    def test_18_read_only_dashboard_not_create_database(self):
        p=dashboard.snapshot(self.repo,self.db)
        self.assertEqual(p['events'],[])
        self.assertFalse(self.db.exists())
        self.assertEqual(p['git'],{})

    def test_18_read_only_dashboard_no_git_report_creation(self):
        before=evidence.state_dir(self.repo)/'bridge_report.json'
        dashboard.snapshot(self.repo,self.db)
        self.assertFalse(before.exists())

    def test_19_doctor_requires_actual_files(self):
        status=operations.check(self.repo,self.db)
        self.assertEqual(status['status'],'ACTION_REQUIRED')
        self.assertEqual(status['database'],'MISSING')

    def test_19_backup_preserves_source_and_integrity(self):
        con=journal.connect(self.db)
        con.execute('INSERT INTO events VALUES(?,?,?,?)',('log','gen',0,'{}'))
        con.commit();con.close()
        before=bridge.scan(self.repo)
        dest=self.root/'archive'/'b.sqlite3'
        result=operations.archive(self.repo,self.db,dest)
        self.assertEqual(result['status'],'VERIFIED_BACKUP')
        self.assertTrue(self.db.is_file() and dest.is_file())
        with self.assertRaises(FileExistsError):
            operations.archive(self.repo,self.db,dest)
        with self.assertRaises(ValueError):
            operations.archive(self.repo,self.db,self.repo/'unsafe.sqlite3')

    def test_20_no_attestation_blocks_release(self):
        result=release_gate.gate(self.repo,self.db)
        self.assertEqual(result['result'],'BLOCKED')
        self.assertIn('real_codex_hook', result['remaining'])

    def test_20_empty_attestation_does_not_claim_verified(self):
        f=self.root/'attestation.json';f.write_text('{"observations":{}}',encoding='utf8')
        result=release_gate.gate(self.repo,self.db,f)
        self.assertEqual(result['result'],'BLOCKED')

    def test_20_invalid_attestation_rejected(self):
        f=self.root/'invalid.json';f.write_text('[]',encoding='utf8')
        with self.assertRaises(ValueError):
            release_gate.gate(self.repo,self.db,f)


if __name__=='__main__': unittest.main()
