"""Tests for chapters 13-16; artificial Git repos only, no live Codex."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / 'watchdog'
sys.path.insert(0, str(MOD))
import evidence
import integration_check
import appserver_adapter
import progress
import scope_guard
import task_contract


class NextChaptersTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / 'repo'
        self.repo.mkdir()
        for cmd in (['git','init'], ['git','config','user.email','guide@example.test'], ['git','config','user.name','Guide']):
            subprocess.run(cmd, cwd=self.repo, capture_output=True, check=True)
        (self.repo/'GOAL.md').write_text('Do not modify\n',encoding='utf8')
        (self.repo/'hello.py').write_text('def greet(): return "OK"\n',encoding='utf8')
        (self.repo/'test_hello.py').write_text('import unittest\nfrom hello import greet\nclass T(unittest.TestCase):\n def test_it(self): self.assertEqual(greet(),"OK")\n',encoding='utf8')
        (self.repo/'.gitignore').write_text('__pycache__/\n*.pyc\n',encoding='utf8')
        subprocess.run(['git','add','.'],cwd=self.repo,capture_output=True,check=True)
        subprocess.run(['git','commit','-m','start'],cwd=self.repo,capture_output=True,check=True)
        self.repo = evidence.root_for(self.repo)
        evidence.atomic_json(evidence.state_dir(self.repo)/'baseline.json', {'files':evidence.snapshot(self.repo)})
        self.tmp = Path(tmp.name)

    def pin(self, allowed=True, milestones=True):
        c = {'schema_version':1,'goal':'修复 hello','protected_paths':['GOAL.md'],
             'acceptance':[{'id':'A1','description':'test hello','command':[sys.executable,'-m','unittest','test_hello.py']}]}
        if allowed: c['allowed_paths']=['hello.py','test_hello.py']
        if milestones: c['milestones']=[{'id':'M1','title':'代码验证','acceptance_ids':['A1']}]
        dest=self.tmp/'contract.json'
        dest.write_text(json.dumps(c),encoding='utf8')
        task_contract.init(self.repo,dest)
        task_contract.approve(self.repo)

    def test_13_not_claim_live_verified(self):
        log=self.tmp/'fake.jsonl'
        log.write_text(json.dumps({'event':'PostToolUse','source':'codex_hook','cwd':str(self.repo)})+'\n',encoding='utf8')
        v=integration_check.inspect(self.repo,log,self.tmp/'missing.db')
        self.assertEqual(v['hook_records_observed'],1)
        self.assertEqual(v['real_codex_end_to_end'],'NOT_VERIFIED')
        self.assertFalse(v['hook_events_are_authenticated'])

    def test_13_empty_has_no_false_success(self):
        v=integration_check.inspect(self.repo,self.tmp/'missing.jsonl',self.tmp/'missing.db')
        self.assertEqual(v['hook_records_observed'],0)
        self.assertEqual(v['contract_stage'],'NO_CONTRACT')

    def test_14_removes_sensitive_fields(self):
        row={'method':'item/completed','params':{'threadId':'t','turnId':'v',
            'item':{'id':'x','type':'commandExecution','command':'SECRET-DO-NOT-SAVE','output':'TOKEN-SECRET'}}}
        projected=appserver_adapter.project(row)
        self.assertEqual(projected['tool'],'commandExecution')
        self.assertNotIn('SECRET',json.dumps(projected))
        self.assertEqual(projected['source'],'app_server_export_unverified')

    def test_14_skips_large_and_unknown(self):
        inp=self.tmp/'raw.ndjson'; out=self.tmp/'sanitized.jsonl'
        inp.write_text(json.dumps({'method':'item/started','params':{'item':{'type':'fileChange','path':'TOP-SECRET'}}})+'\n'+
                      json.dumps({'method':'other','prompt':'PROMPT'})+'\n'+'x'*50+'\n',encoding='utf8')
        r=appserver_adapter.import_export(inp,out,max_line_bytes=40) # both valid input lines exceed 40
        self.assertEqual(r['imported'],0)
        self.assertFalse(out.exists())

    def test_14_valid_export_saves_only_allowlisted_metadata(self):
        raw = {"method":"item/completed", "params":{"threadId":"th", "turnId":"tr",
               "item":{"id":"it","type":"commandExecution","command":"PRIVATE_COMMAND",
                       "output":"PRIVATE_OUTPUT"}}}
        inp = self.tmp/'valid.ndjson'; out=self.tmp/'safe.jsonl'
        inp.write_text(json.dumps(raw)+'\n',encoding='utf8')
        stats=appserver_adapter.import_export(inp,out)
        self.assertEqual(stats['imported'],1)
        content=out.read_text('utf8')
        self.assertNotIn('PRIVATE_COMMAND',content)
        self.assertNotIn('PRIVATE_OUTPUT',content)
        self.assertEqual(json.loads(content)['event'],'item/completed')

    def test_14_rejects_same_input_output(self):
        inp=self.tmp/'same.jsonl'
        inp.write_text('{}\n',encoding='utf8')
        with self.assertRaises(ValueError):
            appserver_adapter.import_export(inp,inp)

    def test_15_only_checked_acceptance_is_counted(self):
        self.pin()
        p=progress.compute(self.repo)
        self.assertEqual((p['verified_checks'],p['total_checks']),(0,1))
        self.assertEqual(p['milestones'][0]['state'],'PENDING')
        self.assertEqual(task_contract.run_one(self.repo,'A1'),0)
        p=progress.compute(self.repo)
        self.assertEqual(p['verified_checks'],1)
        (self.repo/'hello.py').write_text('def greet():return "CHANGED"\n',encoding='utf8')
        p=progress.compute(self.repo)
        self.assertEqual(p['verified_checks'],0)
        self.assertEqual(p['milestones'][0]['state'],'NEEDS_RECHECK')

    def test_15_rejects_unapproved_contract(self):
        self.pin()
        file=task_contract.locations(self.repo)[0]
        doc=evidence.read_json(file);doc['goal']='silently weakened';evidence.atomic_json(file,doc)
        self.assertEqual(progress.compute(self.repo)['state'],'UNTRUSTED_CONTRACT')

    def test_16_flags_path_scope_without_attribution(self):
        self.pin()
        (self.repo/'other.py').write_text('# hello\n',encoding='utf8')
        r=scope_guard.check(self.repo)
        self.assertEqual(r['findings'][0]['code'],'OUTSIDE_DECLARED_PATH_SCOPE')
        self.assertIn('cannot attribute author',r['scope'])
        (self.repo/'GOAL.md').write_text('modified\n',encoding='utf8')
        codes={item['code'] for item in scope_guard.check(self.repo)['findings']}
        self.assertIn('PROTECTED_CHANGE',codes)

    def test_16_missing_allowed_is_not_a_clean_bill(self):
        self.pin(allowed=False)
        self.assertEqual(scope_guard.check(self.repo)['status'],'NOT_CONFIGURED')


if __name__=='__main__': unittest.main()
