"""Synthetic fixtures only. These cases are not real Codex detector efficacy."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"watchdog"
sys.path.insert(0,str(ROOT))
import evidence
import task_contract
import failure_review_v25 as failure
import stepwise_compare_v26 as compare
import drift_review_v27 as drift
import artifact_acceptance_v28 as artifacts


def event(source="fixture_only",session="s",call="c",outcome="FAILED",tool="Bash",turn="t"):
    return {"source":source, "session_id":session, "turn_id":turn,
            "tool_use_id":call, "tool":tool,"phase":"FINISHED",
            "outcome":outcome, "linkable":True,"event_id":"id-"+call}


class FailureTest(unittest.TestCase):
    def test_six_successful_bash_not_repetition(self):
        rows=[event(call=str(i),outcome="SUCCEEDED") for i in range(6)]
        self.assertEqual(failure.diagnose(rows)["signals"],[])
    def test_dedupe_and_unknown(self):
        rows=[event(call="a"),event(call="a"),event(call="b",outcome="UNKNOWN")]
        r=failure.diagnose(rows,min_failures=2)
        self.assertEqual(r["calls"],2)
        self.assertEqual(r["unknown_outcomes"],1)
        self.assertEqual(r["signals"],[])
    def test_conflicting_terminal_quarantined(self):
        r=failure.diagnose([event(outcome="FAILED"),event(outcome="SUCCEEDED")])
        self.assertEqual(r["calls"],0)
        self.assertEqual(r["conflicts"][0]["kind"],"CONFLICTING_TERMINAL")
    def test_cross_session_never_pooled(self):
        rows=[event(session="a",call=str(i)) for i in range(2)]
        rows += [event(session="b",call=str(i)) for i in range(2)]
        self.assertEqual(failure.diagnose(rows)["signals"],[])
    def test_manual_groups_require_matching_exact_ops(self):
        rows=[event(call="a"),event(call="b",outcome="SUCCEEDED")]
        x={"schema_version":1,"groups":[{"id":"G","calls":[
             {"source":"fixture_only","session_id":"s","turn_id":"t","tool_use_id":"a"},
             {"source":"fixture_only","session_id":"s","turn_id":"t","tool_use_id":"b"}]}]}
        r=failure.diagnose(rows,x)
        self.assertEqual(r["signals"][0]["review_outcome"],"POSSIBLE_RECOVERY")
        x["groups"][0]["calls"][1]["session_id"]="other"
        with self.assertRaises(ValueError):
            failure.diagnose(rows,x)
    def test_same_category_failures_only_review(self):
        r=failure.diagnose([event(call=str(i)) for i in range(3)])
        self.assertEqual(r["signals"][0]["code"],"FAILURE_CLUSTER_REVIEW")
        self.assertEqual(r["signals"][0]["interpretation"],"NOT_SAME_COMMAND_OR_NO_PROGRESS_PROOF")


class EvalTest(unittest.TestCase):
    def setUp(self):
        self.protocol={"schema_version":1,"task":"repeated_failure_review",
                       "data_kind":"synthetic","annotation_frozen":True,
                       "threshold":0.6,"min_test_positives":1}
        self.rows=[
             {"sample_id":"x1","session_id":"S1","split":"train","label":0,
              "rule_alarm":False,"model_score":0.1},
             {"sample_id":"x2","session_id":"S2","split":"test","label":1,
              "rule_alarm":True,"model_score":0.8},
             {"sample_id":"x3","session_id":"S3","split":"test","label":0,
              "rule_alarm":True,"model_score":0.1}]
    def test_paired_metrics_synthetic_cannot_be_go(self):
        r=compare.compare(self.protocol,self.rows)
        self.assertEqual(r["status"],"SYNTHETIC_ONLY")
        self.assertEqual(r["rule"]["fp"],1)
        self.assertEqual(r["external_model"]["fp"],0)
        self.assertEqual(r["paired_difference_f1"],1.0-2/3)
    def test_missing_model_scores_not_invented(self):
        self.rows[1]["model_score"]=None
        r=compare.compare(self.protocol,self.rows)
        self.assertEqual(r["external_model"],"NOT_EVALUATED")
    def test_session_leakage_rejected(self):
        self.rows[1]["session_id"]="S1"
        with self.assertRaisesRegex(ValueError,"leakage"):
            compare.compare(self.protocol,self.rows)
    def test_no_posthoc_thresholds(self):
        del self.protocol["threshold"]
        with self.assertRaises(ValueError):
            compare.compare(self.protocol,self.rows)
    def test_real_data_claim_does_not_certify(self):
        self.protocol["data_kind"]="real_reviewed"
        self.assertEqual(compare.compare(self.protocol,self.rows)["status"],
                         "PROVISIONAL_REVIEW_REQUIRED")
    def test_underpowered_gate(self):
        self.protocol["min_test_positives"]=2
        self.assertEqual(compare.compare(self.protocol,self.rows)["status"],
                         "INSUFFICIENT_FOR_PREDECLARED_GATE")


class LocalRepoTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)/"repo"
        self.repo.mkdir()
        for cmd in (["git","init"],["git","config","user.email","fixture@example.test"],
                    ["git","config","user.name","Fixture"]):
            subprocess.run(cmd,cwd=self.repo,check=True,capture_output=True)
        (self.repo/"GOAL.md").write_text("DO NOT TOUCH\n",encoding="utf-8")
        (self.repo/"report.txt").write_bytes(b"expected bytes\n")
        (self.repo/".gitignore").write_text("secret/\n",encoding="utf-8")
        subprocess.run(["git","add","."],cwd=self.repo,check=True,capture_output=True)
        subprocess.run(["git","commit","-m","baseline"],cwd=self.repo,check=True,capture_output=True)
        self.repo=evidence.root_for(self.repo)
        self.state=evidence.state_dir(self.repo)
        evidence.atomic_json(self.state/"baseline.json",{"files":evidence.snapshot(self.repo)})
        c={"schema_version":1,"goal":"Check report","protected_paths":["GOAL.md"],
           "acceptance":[{"id":"A1","description":"external test","command":[sys.executable,"-V"]}]}
        source=Path(self.temp.name)/"task.json"
        source.write_text(json.dumps(c),encoding="utf-8")
        task_contract.init(self.repo,source)
        task_contract.approve(self.repo)
        self.contract_hash=task_contract.contract_hash(c)
        self.plan={"schema_version":1,"contract_sha256":self.contract_hash,"checks":[
            {"id":"artifact1","path":"report.txt",
             "sha256":hashlib.sha256(b"expected bytes\n").hexdigest()}]}
        self.addCleanup(lambda: __import__("shutil").rmtree(self.state,ignore_errors=True))
    def test_artifact_approved_match_still_not_tested(self):
        self.assertEqual(artifacts.store_plan(self.repo,self.plan)["status"],"DRAFT_ONLY")
        self.assertEqual(artifacts.inspect(self.repo)["status"],"BLOCKED_UNAPPROVED_OR_CHANGED_PLAN")
        artifacts.approve_plan(self.repo)
        r=artifacts.inspect(self.repo)
        self.assertEqual(r["status"],"ARTIFACT_BYTES_MATCH_ONLY")
        self.assertEqual(r["contract_stage"],"IN_PROGRESS")
    def test_artifact_mismatch_and_protected_block(self):
        artifacts.store_plan(self.repo,self.plan)
        artifacts.approve_plan(self.repo)
        (self.repo/"report.txt").write_text("wrong\n",encoding="utf-8")
        self.assertEqual(artifacts.inspect(self.repo)["checks"][0]["result"],"MISMATCH")
        (self.repo/"GOAL.md").write_text("changed\n",encoding="utf-8")
        self.assertEqual(artifacts.inspect(self.repo)["status"],"BLOCKED_PROTECTED_FILE_CHANGE")
    def test_bad_traversal_and_ignored_path(self):
        self.plan["checks"][0]["path"]="../outside.txt"
        with self.assertRaises(ValueError):
            artifacts.validate(self.plan)
        self.plan["checks"][0]["path"]="secret/private.txt"
        artifacts.store_plan(self.repo,self.plan)
        artifacts.approve_plan(self.repo)
        (self.repo/"secret").mkdir()
        (self.repo/"secret"/"private.txt").write_text("x")
        self.assertEqual(artifacts.inspect(self.repo)["checks"][0]["result"],
                         "NOT_IN_GIT_VISIBLE_SCOPE")
    def test_plan_digest_mutation_does_not_silently_reapprove(self):
        artifacts.store_plan(self.repo,self.plan)
        artifacts.approve_plan(self.repo)
        saved=self.state/"artifact_plan_v28.json"
        altered=json.loads(saved.read_text(encoding="utf8"))
        altered["checks"][0]["sha256"]="0"*64
        saved.write_text(json.dumps(altered),encoding="utf8")
        self.assertEqual(artifacts.inspect(self.repo)["status"],"BLOCKED_UNAPPROVED_OR_CHANGED_PLAN")
    def test_drift_untrusted_input_stays_review_required(self):
        row={"source":"fixture_only","event_id":"id-1","linkable":True}
        cand={"schema_version":1,"contract_sha256":self.contract_hash,"items":[
             {"code":"POSSIBLE_GOAL_DEVIATION","acceptance_id":"A1","event_ids":["id-1"],
              "review_status":"CONFIRMED"}]}
        r=drift.assess(self.repo,[row],cand)
        self.assertEqual(r["candidates"][0]["verdict"],"HUMAN_REVIEW_REQUIRED")
        self.assertEqual(r["status"],"REVIEW_REQUIRED")
    def test_drift_no_evidence_refused(self):
        bad={"schema_version":1,"contract_sha256":self.contract_hash,"items":[
              {"code":"POSSIBLE_SCOPE_EXPANSION","acceptance_id":"A1","event_ids":["unknown"]}]}
        with self.assertRaises(ValueError):
            drift.assess(self.repo,[],bad)
    def test_drift_protected_change_not_actor_attribution(self):
        (self.repo/"GOAL.md").write_text("modified",encoding="utf8")
        r=drift.assess(self.repo)
        self.assertEqual(r["facts"][0]["code"],"PROTECTED_CHANGE")
        self.assertEqual(r["facts"][0]["attribution"],"UNKNOWN")


if __name__=="__main__":
    unittest.main()
