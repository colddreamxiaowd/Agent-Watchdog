"""Round3: synthetic unit tests for Codex App sidecar. Not real app certification."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]/"watchdog"
sys.path.insert(0,str(HERE))
import app_hook_v29 as hook
import app_setup_v29 as setup
import app_watch_v30 as watch
import app_recovery_v31 as recovery


def raw_event(event,call="c1",outcome="FAILED",stamp=100000):
    fields={"source":"hook_input_unverified","event":event,"session_id":"S",
            "turn_id":"T","tool":"Bash","tool_use_id":call,"linkable":True,
            "event_id":str(stamp)+"-"+call+"-"+event,
            "received_at":datetime.fromtimestamp(stamp,timezone.utc).isoformat()}
    if event=="PreToolUse":
        fields["phase"]="STARTED"; fields["outcome"]="UNKNOWN"
    else:
        fields["phase"]="FINISHED"; fields["outcome"]=outcome
    return fields


class AppHookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
    def test_private_fields_not_written(self):
        p=Path(self.temp.name)/"events.jsonl"
        original={"hook_event_name":"PostToolUse","session_id":"S","turn_id":"T",
            "tool_name":"Bash","tool_use_id":"call", "cwd":"C:\\private\\school",
            "tool_input":{"command":"api-key SECRET_CANARY"},"tool_response":
            {"exit_code":1,"stdout":"PRIVATE_OUTPUT"}}
        self.assertTrue(hook.observe(json.dumps(original).encode(),p))
        stored=p.read_text(encoding="utf8")
        for token in ("SECRET_CANARY","PRIVATE_OUTPUT","school","api-key"):
            self.assertNotIn(token,stored)
        row=json.loads(stored)
        self.assertIsNone(row["cwd"])
        self.assertEqual(row["outcome"],"FAILED")
    def test_missing_terminal_result_is_unknown(self):
        p=Path(self.temp.name)/"events.jsonl"
        self.assertTrue(hook.observe(json.dumps({"hook_event_name":"PostToolUse",
                    "tool_use_id":"t","session_id":"S","tool_response":{"message":"failed"}}).encode(),p))
        self.assertEqual(json.loads(p.read_text())["outcome"],"UNKNOWN")
    def test_bad_hook_never_logged(self):
        p=Path(self.temp.name)/"events.jsonl"
        self.assertFalse(hook.observe(b"not json",p))
        self.assertFalse(p.exists())
    def test_reviewed_config_and_no_overwrite(self):
        root=Path(self.temp.name)/"repo"
        root.mkdir()
        for cmd in (["git","init"],["git","config","user.email","fixture@example.invalid"],
                    ["git","config","user.name","Fixture"]):
            subprocess.run(cmd,cwd=root,check=True,capture_output=True)
        c=setup.config()
        self.assertEqual(len(c["hooks"]),5)
        self.assertFalse((root/".codex"/"hooks.json").exists())
        with self.assertRaises(ValueError):
            setup.install(root,c)
        target=setup.install(root,c,acknowledged=True)
        self.assertTrue(target.exists())
        with self.assertRaises(FileExistsError):
            setup.install(root,c,acknowledged=True)
        self.assertEqual(setup.doctor(root)["codex_app_end_to_end"],"NOT_VERIFIED")


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log=Path(self.temp.name)/"events.jsonl"
        self.db=Path(self.temp.name)/"state.sqlite3"
        self.t=100000
    def put(self,*rows):
        with self.log.open("a",encoding="utf8",newline="\n") as fd:
            for row in rows:
                fd.write(json.dumps(row)+"\n")
    def poll(self,**kw):
        return watch.poll(self.log,self.db,sec=self.t+40,stall_seconds=30,**kw)
    def alerts(self):
        con=sqlite3.connect(self.db)
        try:
            return con.execute("SELECT code FROM alerts").fetchall()
        finally:
            con.close()
    def test_missing_log_is_not_proof_app_offline(self):
        self.assertEqual(self.poll()["status"],"NO_LOG_NOT_CODEX_OFFLINE")
    def test_new_watcher_starts_at_tail(self):
        self.put(raw_event("PostToolUse",call="old",stamp=self.t))
        self.assertEqual(self.poll()["events_new"],0)
        self.put(raw_event("PostToolUse",call="new",stamp=self.t+10))
        self.assertEqual(self.poll()["events_new"],1)
    def test_explicit_failures_alert_and_reboot_dedupe(self):
        self.put(*(raw_event("PostToolUse",call=str(i),stamp=self.t+i) for i in range(3)))
        first=self.poll(include_existing=True)
        self.assertEqual(first["alerts_new"],1)
        self.assertEqual(self.alerts(),[("FAILURE_CLUSTER_REVIEW",)])
        self.assertEqual(self.poll()["alerts_new"],0)
        self.put(*(raw_event("PostToolUse",call=str(i+3),stamp=self.t+i+3) for i in range(3)))
        self.assertEqual(self.poll()["alerts_new"],0) # cooldown
        self.assertEqual(len(self.alerts()),1)
    def test_unknown_and_successful_bash_not_alert(self):
        self.put(*(raw_event("PostToolUse",call=str(i),outcome="UNKNOWN" if i%2 else "SUCCEEDED",stamp=self.t+i) for i in range(8)))
        self.poll(include_existing=True)
        self.assertEqual(self.alerts(),[])
    def test_suspected_stall_one_alert_and_terminal_no_repeat(self):
        self.put(raw_event("PreToolUse",stamp=self.t))
        self.assertEqual(self.poll(include_existing=True)["alerts_new"],1)
        self.assertEqual(self.alerts(),[("SUSPECTED_STALL",)])
        self.assertEqual(self.poll()["alerts_new"],0)
        self.put(raw_event("PostToolUse",outcome="SUCCEEDED",stamp=self.t+10))
        self.assertEqual(self.poll()["alerts_new"],0)
    def test_terminal_before_deadline_no_stall(self):
        self.put(raw_event("PreToolUse",stamp=self.t+20),
                 raw_event("PostToolUse",outcome="SUCCEEDED",stamp=self.t+21))
        self.poll(include_existing=True)
        self.assertEqual(self.alerts(),[])
    def test_partial_line_cannot_advance_cursor(self):
        self.put(raw_event("PreToolUse",stamp=self.t+30))
        self.poll(include_existing=True)
        raw=json.dumps(raw_event("PostToolUse",call="half",stamp=self.t+35)).encode()
        with self.log.open("ab") as f:
            f.write(raw)
        self.assertEqual(self.poll()["events_new"],0)
        with self.log.open("ab") as f:
            f.write(b"\n")
        self.assertEqual(self.poll()["events_new"],1)
    def test_truncated_log_replays_without_duplicate_alarm(self):
        self.put(*(raw_event("PostToolUse",call=str(i),stamp=self.t+i) for i in range(3)))
        self.poll(include_existing=True)
        self.log.write_text("",encoding="utf8")
        self.put(raw_event("PostToolUse",call="0",stamp=self.t))
        r=self.poll()
        self.assertTrue(r["cursor_reset"])
        self.assertEqual(r["alerts_new"],0)
    def test_cannot_use_nonpositive_safety_thresholds(self):
        self.put(raw_event("PostToolUse",stamp=self.t))
        with self.assertRaises(ValueError):
            self.poll(failure_count=1)
    def test_six_bash_across_session_not_falsely_joined(self):
        rows=[]
        for session in ("A","B"):
            for i in range(2):
                r=raw_event("PostToolUse",call=f"{session}{i}",stamp=self.t+i)
                r["session_id"]=session
                rows.append(r)
        self.put(*rows)
        self.poll(include_existing=True)
        self.assertEqual(self.alerts(),[])
    def test_backup_health_without_restore(self):
        self.put(raw_event("PostToolUse",outcome="FAILED",stamp=self.t))
        self.poll(include_existing=True)
        r=recovery.status(self.db,self.log)
        self.assertEqual(r["codex_app_e2e"],"NOT_VERIFIED")
        dest=Path(self.temp.name)/"backups"
        b=recovery.backup(self.db,dest)
        self.assertEqual(b["integrity"],"ok")
        self.assertIn("NOT_AUTOMATED",b["restore"])
        self.assertTrue(Path(b["path"]).is_file())


if __name__=="__main__":
    unittest.main()
