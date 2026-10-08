import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WATCHDOG = Path(__file__).resolve().parents[1] / "watchdog"
sys.path.insert(0, str(WATCHDOG))
import evidence
import bridge
import hook_logger_v04 as hook
import task_contract as task
import risk
import journal
import agent_adapter
import watchdog_cli


class CourseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        for cmd in (["git", "init"], ["git", "config", "user.email", "tutorial@example.test"],
                    ["git", "config", "user.name", "Tutorial"]):
            subprocess.run(cmd, cwd=self.repo, capture_output=True, check=True)
        (self.repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.repo / "GOAL.md").write_text("Protected\n", encoding="utf-8")
        (self.repo / "hello.py").write_text("def greet(): return 'OK'\n", encoding="utf-8")
        (self.repo / "test_hello.py").write_text("import unittest\nfrom hello import greet\nclass T(unittest.TestCase):\n def test_ok(self): self.assertEqual(greet(), 'OK')\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.repo, capture_output=True, check=True)
        self.repo = evidence.root_for(self.repo)
        evidence.atomic_json(evidence.state_dir(self.repo) / "baseline.json", {
            "files": evidence.snapshot(self.repo),
        })
        (self.repo.parent / "contract.json").write_text((WATCHDOG / "task_contract.example.json").read_text(encoding="utf-8"), encoding="utf-8")
        self.addCleanup(lambda: None)

    def test_redaction(self):
        r = hook.prepare({"hook_event_name": "PostToolUse", "tool_name": "Bash", "session_id": "s",
                          "cwd": str(self.repo), "tool_input": {"secret": "PASSWORD"},
                          "tool_response": {"TOKEN": "X"}})
        self.assertNotIn("PASSWORD", str(r))
        self.assertNotIn("TOKEN", str(r))

    def test_bridge_stale_protected(self):
        result = bridge.scan(self.repo)
        self.assertEqual(result["changed"], [])
        (self.repo / "GOAL.md").write_text("Changed\n")
        self.assertIn("GOAL.md", bridge.scan(self.repo)["protected"])

    def test_partial_line(self):
        f = self.repo / "events.jsonl"
        f.write_bytes(b'{"event":"Stop"}\n{"event":')
        rows, pos = bridge.read_new(f, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(pos, len(b'{"event":"Stop"}\n'))

    def test_repo_filter(self):
        self.assertTrue(bridge.tracked_repo_event({"cwd":str(self.repo)},self.repo))
        self.assertFalse(bridge.tracked_repo_event({"cwd":str(self.repo.parent)},self.repo))

    def test_contract_verified_then_stale_and_blocked(self):
        contract = {"schema_version": 1, "goal": "Test", "protected_paths": ["GOAL.md"],
            "acceptance": [{"id":"A1","description":"Check","command":[sys.executable,"-m","unittest","test_hello.py","-v"]}]}
        cpath = self.repo.parent / "contract_external.json"
        cpath.write_text(json.dumps(contract), encoding="utf-8")
        task.init(self.repo,cpath)
        task.approve(self.repo)
        self.assertEqual(task.acceptance_status(self.repo)["stage"],"IN_PROGRESS")
        self.assertEqual(task.run_one(self.repo,"A1"),0)
        self.assertEqual(task.acceptance_status(self.repo)["stage"],"VERIFIED_COMPLETE")
        (self.repo / "hello.py").write_text("def greet(): return 'BAD'\n")
        self.assertEqual(task.acceptance_status(self.repo)["acceptance"]["A1"],"STALE")
        (self.repo / "GOAL.md").write_text("Changed\n")
        self.assertEqual(task.acceptance_status(self.repo)["stage"],"BLOCKED")

    def test_contract_tamper(self):
        contract = {"schema_version": 1, "goal": "Test", "protected_paths": [],
            "acceptance": [{"id":"A1","description":"Check","command":[sys.executable,"-m","unittest","test_hello.py"]}]}
        cpath = self.repo.parent / "c.json"
        cpath.write_text(json.dumps(contract), encoding="utf-8")
        task.init(self.repo,cpath)
        task.approve(self.repo)
        saved = task.locations(self.repo)[0]
        contract["goal"] = "Weaker Goal"
        evidence.atomic_json(saved, contract)
        self.assertEqual(task.acceptance_status(self.repo)["stage"],"BLOCKED")

    def test_journal_dedup_and_partial(self):
        logfile = self.repo.parent / "input.jsonl"
        dbfile = self.repo.parent / "events.sqlite3"
        logfile.write_bytes(b'{"event":"PostToolUse","tool":"Bash"}\n{"event":')
        self.assertEqual(journal.sync(logfile, dbfile), 1)
        self.assertEqual(journal.sync(logfile, dbfile), 0)
        with logfile.open("ab") as f:
            f.write(b'"Stop"}\n')
        self.assertEqual(journal.sync(logfile, dbfile), 1)
        self.assertEqual(journal.summary(dbfile)["events"], 2)
        dest = self.repo.parent / "backup.sqlite3"
        journal.backup(dbfile,dest)
        self.assertEqual(journal.summary(dest)["integrity"], "ok")

    def test_adapter_redacts_command(self):
        raw = {"type":"item.completed","thread_id":"abc",
               "item":{"type":"command_execution","id":"it","command":"SECRET_PASS"}}
        result = agent_adapter.project(raw)
        self.assertEqual(result["tool"], "command_execution")
        self.assertNotIn("SECRET_PASS",str(result))

    def test_handoff_does_not_claim_success_without_contract(self):
        data=watchdog_cli.report(self.repo)
        doc=watchdog_cli.markdown_report(data)
        self.assertIn("交接快照",doc)
        self.assertIn("不是完整审计日志",doc)

    def test_risk_not_stuck(self):
        events = [{"tool":"Bash"}]*6
        alerts = risk.evaluate({},recent_events=events)
        self.assertEqual(alerts[0]["code"],"REPEATED_TOOL_CATEGORY")
        self.assertEqual(alerts[0]["kind"],"heuristic")

if __name__=="__main__": unittest.main()
