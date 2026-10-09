"""Round4: isolated Git fixtures + synthetic Hook rows. NOT App detection efficacy."""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1] / "watchdog"
sys.path.insert(0, str(HERE))
import app_task_watch_v37 as united
import evidence
import session_binding_v34 as binding
import task_contract
import task_overview_v35 as view
import task_pulse_v36 as pulse


def stamp():
    return datetime.now(timezone.utc).isoformat()


def event(event="PreToolUse", phase="STARTED", outcome="UNKNOWN",
          session="S", call="T1", number=0, src="hook_input_unverified"):
    return {"event":event,"source":src,"session_id":session,
            "turn_id":"turn-1","tool_use_id":call,"tool":"Bash",
            "received_at":stamp(),"event_id":f"id-{number}-{call}-{event}",
            "linkable":True,"phase":phase,"outcome":outcome,"cwd":None}


class TaskLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.repo=self.root/"repo"
        self.repo.mkdir()
        subprocess.run(["git","init"],cwd=self.repo,check=True,capture_output=True)
        subprocess.run(["git","config","user.name","Fixture"],cwd=self.repo,check=True,capture_output=True)
        subprocess.run(["git","config","user.email","fixture@example.invalid"],cwd=self.repo,check=True,capture_output=True)
        (self.repo/"GOAL.md").write_bytes(b"immutable goal\n")
        (self.repo/"src.py").write_bytes(b"print(1)\n")
        subprocess.run(["git","add","."],cwd=self.repo,check=True,capture_output=True)
        subprocess.run(["git","commit","-m","baseline"],cwd=self.repo,check=True,capture_output=True)
        # Git on Windows normalizes drive/root representation; state_dir keys
        # must use the same canonical Git root as bind() and CLI.
        self.repo=evidence.root_for(self.repo)
        self.contract=self.root/"contract.json"
        self.contract.write_text(json.dumps({
            "schema_version":1,"goal":"Only modify src.py and pass tests",
            "protected_paths":["GOAL.md"],"allowed_paths":["src.py"],
            "acceptance":[{"id":"A1","description":"approved isolated check",
                           "command":[sys.executable,"-c","print('ok')"]}]
        }),encoding="utf8")
        task_contract.init(self.repo,self.contract)
        task_contract.approve(self.repo)
        base=evidence.snapshot(self.repo)
        evidence.atomic_json(evidence.state_dir(self.repo)/"baseline.json",
                             {"repo":str(self.repo),"saved_at":stamp(),"files":base,
                              "snapshot_id":evidence.fingerprint(base)})
        self.log=self.root/"events.jsonl"
        self.registry=self.root/"private"/"registry.json"
        self.db=self.root/"pulse.sqlite3"
        self.watch_db=self.root/"watch.sqlite3"
        self.rows=[]
        self.append(event(number=1))
    def append(self,*rows):
        with self.log.open("a",encoding="utf8",newline="\n") as f:
            for x in rows:
                self.rows.append(x)
                f.write(json.dumps(x)+"\n")
    def alias(self):
        return binding.sessions(self.log)[0]["alias"]
    def bind(self):
        return binding.bind(self.repo,self.alias(),self.log,self.registry,approved=True)
    def report(self):
        return view.overview(self.log,self.registry)
    def task(self):
        return self.report()["tasks"][0]
    def test_session_alias_is_private_not_raw(self):
        rows=binding.sessions(self.log)
        self.assertEqual(len(rows),1)
        self.assertNotEqual(rows[0]["alias"],"S")
        self.assertNotIn("repo",json.dumps(rows))
        self.assertIn("_session",rows[0])
    def test_manual_binding_only_and_strict_contract(self):
        with self.assertRaises(ValueError):
            binding.bind(self.repo,self.alias(),self.log,self.registry)
        self.assertFalse(self.registry.exists())
        saved=self.bind()
        self.assertTrue(saved["bound"])
        self.assertFalse(saved["source_authenticated"])
        self.assertNotIn(str(self.repo),json.dumps(saved))
        self.assertEqual(len(binding.read_registry(self.registry)["bindings"]),1)
        with self.assertRaises(ValueError):
            self.bind()
    def test_unknown_alias_or_stale_observation_rejected(self):
        with self.assertRaises(ValueError):
            binding.bind(self.repo,"not-a-real-alias",self.log,self.registry,approved=True)
        valid_alias=self.alias()
        with patch.object(binding,"sessions",return_value=[]):
            with self.assertRaises(ValueError):
                binding.bind(self.repo,valid_alias,self.log,self.registry,approved=True)
    def test_registry_refuses_observed_repo_and_symlink(self):
        with self.assertRaises(ValueError):
            binding.bind(self.repo,self.alias(),self.log,self.repo/"bad.json",approved=True)
    def test_unapproved_contract_cannot_bind(self):
        task_contract.locations(self.repo)[1].unlink()
        with self.assertRaises(ValueError):
            self.bind()
    def test_missing_baseline_cannot_bind(self):
        (evidence.state_dir(self.repo)/"baseline.json").unlink()
        with self.assertRaises(ValueError):
            self.bind()
    def test_no_binding_means_no_assumed_task(self):
        self.assertEqual(self.report()["task_count"],0)
    def test_matching_session_only(self):
        self.bind()
        self.append(event(number=2,session="OTHER",phase="FINISHED",outcome="FAILED"),
                    event(number=3,call="X",phase="FINISHED",outcome="FAILED"))
        stats=self.task()["observations"]
        self.assertEqual(stats["observed_events"],2)
        self.assertEqual(stats["outcomes"]["FAILED"],1)
        self.assertEqual(stats["started_calls"],1)
    def test_unmatched_source_never_in_task(self):
        self.bind()
        self.append(event(number=2,src="untrusted_other",phase="FINISHED",outcome="FAILED"))
        self.assertEqual(self.task()["observations"]["observed_events"],1)
    def test_successful_hook_is_not_task_complete(self):
        self.bind()
        self.append(event(event="PostToolUse",phase="FINISHED",
                          outcome="SUCCEEDED",number=2))
        task=self.task()
        self.assertEqual(task["observations"]["outcomes"]["SUCCEEDED"],1)
        self.assertEqual(task["contract_checks_stage"],"IN_PROGRESS")
        self.assertIn("RUN_APPROVED_TEST_MANUALLY",task["actions"])
        self.assertNotIn("goal",task)
    def test_approved_check_and_semantic_boundary(self):
        self.bind()
        self.assertEqual(task_contract.run_one(self.repo,"A1"),0)
        task=self.task()
        self.assertEqual(task["contract_checks_stage"],"VERIFIED_COMPLETE")
        self.assertIn("INDEPENDENT_CHECKS_PASSED_REVIEW_SEMANTIC_GOAL",task["actions"])
        self.assertIn("goal",view.overview(self.log,self.registry,show_goal=True)["tasks"][0])
    def test_changed_protected_file_is_fact_not_author(self):
        self.bind()
        (self.repo/"GOAL.md").write_bytes(b"changed by ANY actor\n")
        task=self.task()
        self.assertEqual(task["scope_findings"][0]["code"],"PROTECTED_CHANGE")
        self.assertEqual(task["author_attribution"],"UNKNOWN")
        self.assertIn("REVIEW_GIT_SCOPE_NO_AUTHOR_ATTRIBUTION",task["actions"])
    def test_out_of_scope_new_file(self):
        self.bind()
        (self.repo/"other.txt").write_bytes(b"outside\n")
        task=self.task()
        self.assertIn("OUTSIDE_DECLARED_PATH_SCOPE",[x["code"] for x in task["scope_findings"]])
    def test_saved_acceptance_stale_after_edit(self):
        self.bind()
        task_contract.run_one(self.repo,"A1")
        (self.repo/"src.py").write_bytes(b"print(2)\n")
        self.assertEqual(self.task()["acceptance"]["A1"],"STALE")
    def test_contract_reapprove_breaks_binding(self):
        self.bind()
        task_contract.approve(self.repo)
        # Same bytes -> same hash, approval still valid; actual contract edit required.
        target=task_contract.locations(self.repo)[0]
        contract=json.loads(target.read_text())
        contract["goal"]="new goal"
        evidence.atomic_json(target,contract)
        self.assertEqual(self.task()["state"],"CONTRACT_CHANGED_OR_UNAPPROVED")
    def test_baseline_change_invalidates_link(self):
        self.bind()
        base=evidence.state_dir(self.repo)/"baseline.json"
        info=json.loads(base.read_text())
        info["snapshot_id"]="OTHER"
        evidence.atomic_json(base,info)
        self.assertEqual(self.task()["state"],"BASELINE_CHANGED")
    def test_first_pulse_suppresses_old_findings_then_notices(self):
        self.bind()
        first=pulse.evaluate(self.report(),self.db)
        self.assertEqual(first["new_notices"],[])
        (self.repo/"GOAL.md").write_bytes(b"unsafe\n")
        second=pulse.evaluate(self.report(),self.db)
        self.assertIn("PROTECTED_FILE_REVIEW",[x["code"] for x in second["new_notices"]])
        self.assertEqual(pulse.evaluate(self.report(),self.db)["new_notices"],[])
    def test_pulse_restart_dedup_persists_sqlite(self):
        self.bind()
        pulse.evaluate(self.report(),self.db)
        (self.repo/"other.txt").write_bytes(b"out of scope\n")
        self.assertEqual(len(pulse.evaluate(self.report(),self.db)["new_notices"]),1)
        self.assertEqual(pulse.evaluate(self.report(),self.db)["new_notices"],[])
    def test_repeated_risk_after_recovery_is_new_transition(self):
        self.bind()
        pulse.evaluate(self.report(),self.db)
        original=(self.repo/"GOAL.md").read_bytes()
        (self.repo/"GOAL.md").write_bytes(b"first new violation\n")
        self.assertEqual(len(pulse.evaluate(self.report(),self.db)["new_notices"]),1)
        (self.repo/"GOAL.md").write_bytes(original)
        self.assertEqual(pulse.evaluate(self.report(),self.db)["new_notices"],[])
        (self.repo/"GOAL.md").write_bytes(b"first new violation\n")
        second=pulse.evaluate(self.report(),self.db)
        self.assertEqual(len(second["new_notices"]),1)
        self.assertEqual(second["new_notices"][0]["code"],"PROTECTED_FILE_REVIEW")
        self.assertEqual(pulse.evaluate(self.report(),self.db)["new_notices"],[])

    def test_contract_change_notification_is_not_auto_approval(self):
        self.bind()
        pulse.evaluate(self.report(),self.db)
        target=task_contract.locations(self.repo)[0]
        doc=json.loads(target.read_text())
        doc["goal"]="unexpected"
        evidence.atomic_json(target,doc)
        self.assertIn("CONTRACT_REAPPROVAL_REVIEW",[a["code"] for a in
                     pulse.evaluate(self.report(),self.db)["new_notices"]])
        self.assertEqual(self.task()["state"],"CONTRACT_CHANGED_OR_UNAPPROVED")
    def test_no_goal_or_path_sent_to_notify(self):
        self.bind()
        pulse.evaluate(self.report(),self.db)
        (self.repo/"GOAL.md").write_bytes(b"changed\n")
        from unittest.mock import patch as mockpatch
        with mockpatch.object(united.app_watch_v30,"notify_windows",return_value=True) as notified:
            x=united.cycle(self.log,self.registry,self.watch_db,self.db,notify=True)
            self.assertGreater(x["task_evidence"]["new_notices"].__len__(),0)
            notified.assert_called_with("PROTECTED_FILE_REVIEW")
            self.assertNotIn(str(self.repo),json.dumps(x))
    def test_raw_session_not_in_published_report(self):
        self.bind()
        out=json.dumps(self.report())
        self.assertNotIn('"session_id": "S"',out)
    def test_incomplete_row_not_used_for_binding(self):
        broken=self.root/"half.jsonl"
        broken.write_bytes(json.dumps(event()).encode("utf8"))
        self.assertEqual(binding.sessions(broken),[])
    def test_stale_session_older_than_window(self):
        self.assertEqual(binding.sessions(self.log,now=datetime.now(timezone.utc).timestamp()+49*3600),[])
    def test_conflicting_status_quarantined(self):
        self.bind()
        self.append(event(event="PostToolUse",phase="FINISHED",outcome="FAILED",number=2),
                    event(event="PostToolUse",phase="FINISHED",outcome="SUCCEEDED",number=3))
        self.assertEqual(self.task()["observations"]["outcomes"]["CONFLICT"],1)
    def test_no_repeat_notifications_after_watcher_restart(self):
        self.bind()
        united.cycle(self.log,self.registry,self.watch_db,self.db)
        (self.repo/"other.txt").write_bytes(b"new\n")
        a=united.cycle(self.log,self.registry,self.watch_db,self.db)
        b=united.cycle(self.log,self.registry,self.watch_db,self.db)
        self.assertEqual(len(a["task_evidence"]["new_notices"]),1)
        self.assertEqual(b["task_evidence"]["new_notices"],[])


if __name__=="__main__":
    unittest.main()
