import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

WATCHDOG = Path(__file__).resolve().parents[1] / "watchdog"
sys.path.insert(0, str(WATCHDOG))
import execution_v2 as ev
import runtime_v2 as runtime
import step_links_v2


class ExecutionProjection(unittest.TestCase):
    def test_hook_redacts_private_command_and_unknown_completion(self):
        data = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
                "session_id": "s", "tool_use_id": "op", "cwd": "D:/test",
                "tool_input": {"command": "SUPER_PRIVATE_COMMAND"},
                "tool_response": {"stdout": "SUPER_SECRET_OUTPUT"}}
        row = ev.from_hook(data)
        self.assertEqual(row["phase"], "FINISHED")
        self.assertEqual(row["outcome"], "UNKNOWN")
        self.assertNotIn("SUPER_", json.dumps(row))
        self.assertTrue(row["linkable"])

    def test_hook_numeric_status_not_text_inference(self):
        base = {"hook_event_name": "PostToolUse", "session_id": "s", "tool_use_id": "t"}
        self.assertEqual(ev.from_hook({**base, "tool_response": {"exit_code": 1}})["outcome"], "FAILED")
        self.assertEqual(ev.from_hook({**base, "tool_response": {"exit_code": 0}})["outcome"], "SUCCEEDED")
        self.assertEqual(ev.from_hook({**base, "tool_response": {"exit_code": "0"}})["outcome"], "UNKNOWN")
        self.assertEqual(ev.from_hook({**base, "tool_response": {"success": True}})["outcome"], "UNKNOWN")
        self.assertEqual(ev.from_hook({**base, "tool_response": "exit code 1"})["outcome"], "UNKNOWN")

    def test_exec_and_appserver_status(self):
        item = {"type": "command_execution", "id": "a", "exit_code": 7,
                "command": "DO_NOT_PERSIST"}
        row = ev.from_exec({"type": "item.completed", "thread_id": "s", "item": item})
        self.assertEqual(row["outcome"], "FAILED")
        self.assertNotIn("DO_NOT_PERSIST", str(row))
        app = ev.from_appserver({"method": "item/completed",
                                "params": {"threadId": "s", "item": {
                                    "id": "a", "type": "commandExecution", "status": "declined"}}})
        self.assertEqual(app["outcome"], "CANCELLED")
        self.assertEqual(ev.from_appserver({"method": "item/started",
                              "params": {"item": {"id": "i"}}})["linkable"], False)

    def test_normalized_import_partial_and_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "input.ndjson"
            f.write_bytes(b'{"type":"item.started","thread_id":"s","item":{"id":"c"}}\n'
                          b'{"type":"item.completed","thread_id":"s","item":{"id":"c"}}\n'
                          b'{"type":"item.started"')
            rows = list(ev.safe_lines(f, ev.from_exec))
            self.assertEqual(len(rows), 2)
            self.assertNotEqual(rows[0]["event_id"], rows[1]["event_id"])
            self.assertEqual(rows[1]["outcome"], "UNKNOWN")
            again = ev.from_exec({"type":"item.completed","thread_id":"s","item":{"id":"c"}})
            self.assertEqual(again["event_id"], rows[1]["event_id"])

    def test_missing_field_and_malformed(self):
        self.assertIsNone(ev.from_hook({"hook_event_name": "notreal"}))
        self.assertIsNone(ev.from_exec([]))
        self.assertIsNone(ev.from_appserver({"method": "unsupported"}))
        self.assertIsNone(ev.number_code(True))


class RuntimeRules(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)

    def row(self, t, phase, op, outcome="UNKNOWN", tool="Bash", session="one"):
        return {"source": "fixture_only", "received_at": t.isoformat(), "event": "tool",
                "event_id": op + phase, "phase": phase, "outcome": outcome,
                "session_id": session, "tool_use_id": op, "linkable": True,
                "tool": tool, "result_basis": "numeric_exit_code" if outcome == "FAILED" else "not_observed"}

    def test_slow_start_is_suspected_never_certain(self):
        a = self.row(self.now - timedelta(seconds=400), "STARTED", "a")
        report = runtime.diagnose([a], now=self.now, quiet_seconds=100)
        self.assertEqual(report["state"], "SUSPECTED_STALL")
        self.assertIn("SUSPECTED_NOT_CONFIRMED", str(report))

    def test_no_hook_not_stuck(self):
        result = runtime.diagnose([], now=self.now)
        self.assertEqual(result["state"], "NO_OBSERVATION")
        self.assertNotIn("SUSPECTED_STALL", str(result))

    def test_repeated_bash_success_not_failure_or_loop(self):
        rows = []
        for i in range(6):
            rows += [self.row(self.now - timedelta(seconds=9-i), "STARTED", str(i)),
                     self.row(self.now - timedelta(seconds=8-i), "FINISHED", str(i), "SUCCEEDED")]
        result = runtime.diagnose(rows, now=self.now)
        self.assertNotIn("FAILURE_CLUSTER_REVIEW", str(result))
        self.assertEqual(result["state"], "OBSERVING")

    def test_three_distinct_failures_only_cluster_review(self):
        rows = [self.row(self.now, "FINISHED", str(i), "FAILED") for i in range(3)]
        result = runtime.diagnose(rows, now=self.now)
        self.assertIn("FAILURE_CLUSTER_REVIEW", str(result))
        self.assertNotIn("LOOP_CONFIRMED", str(result))

    def test_cross_session_never_pool_cluster(self):
        rows = [self.row(self.now, "FINISHED", str(i), "FAILED", session="A") for i in range(2)]
        rows += [self.row(self.now, "FINISHED", str(i), "FAILED", session="B") for i in range(2)]
        self.assertNotIn("FAILURE_CLUSTER_REVIEW", str(runtime.diagnose(rows, now=self.now)))

    def test_orphan_and_conflicting_terminal(self):
        a = self.row(self.now, "FINISHED", "x", "SUCCEEDED")
        b = self.row(self.now, "FINISHED", "x", "FAILED")
        b["event_id"] = "different"
        self.assertIn("CONFLICTING_TERMINAL", str(runtime.diagnose([a, b], now=self.now)))
        self.assertIn("ORPHAN_TERMINAL", str(runtime.diagnose([a], now=self.now)))

    def test_future_timestamp_invalid(self):
        row = self.row(self.now + timedelta(seconds=1), "STARTED", "p")
        self.assertEqual(runtime.diagnose([row], now=self.now)["invalid_or_future_time"], 1)


class ManualStepLinks(unittest.TestCase):
    def test_manual_mapping_does_not_promote_stale_or_unlinked(self):
        contract = {"schema_version": 1, "goal": "check", "acceptance": [
            {"id":"A1","description":"test","command":["python","-V"]}]}
        anchor = {"event_id": "event-1", "linkable": True, "source": "fixture_only",
                  "session_id": "s", "turn_id": "t", "tool": "Bash"}
        mapping = {"schema_version":1, "contract_sha256":step_links_v2.task_contract.contract_hash(contract),
                   "links":[{"step_id":"A1", "event_id":"event-1", "acceptance_id":"A1"},
                            {"step_id":"A1", "event_id":"not-present"}]}
        with patch.object(step_links_v2.evidence, "root_for", return_value=Path(".")), \
             patch.object(step_links_v2.task_contract, "load", return_value=(contract, True, {}, None)), \
             patch.object(step_links_v2.task_contract, "acceptance_status",
                          return_value={"stage":"IN_PROGRESS","acceptance":{"A1":"STALE"}}):
            result = step_links_v2.build(".", [anchor], mapping)
        self.assertEqual(result["links"][0]["acceptance_status"], "STALE")
        self.assertEqual(result["links"][0]["association"], "LINKED_MANUALLY")
        self.assertEqual(result["links"][1]["association"], "UNLINKED")
        self.assertEqual(result["unlinked"], 1)

    def test_wrong_contract_hash_and_unapproved_rejected(self):
        contract = {"schema_version":1, "goal":"x", "acceptance":[]}
        links = {"schema_version":1, "contract_sha256":"wrong", "links":[]}
        with patch.object(step_links_v2.evidence, "root_for", return_value=Path(".")), \
             patch.object(step_links_v2.task_contract, "load", return_value=(contract, True, {}, None)), \
             patch.object(step_links_v2.task_contract, "acceptance_status",
                          return_value={"stage":"IN_PROGRESS","acceptance":{}}):
            with self.assertRaises(ValueError):
                step_links_v2.build(".", [], links)
        with patch.object(step_links_v2.evidence, "root_for", return_value=Path(".")), \
             patch.object(step_links_v2.task_contract, "load", return_value=(contract, False, {}, None)), \
             patch.object(step_links_v2.task_contract, "acceptance_status",
                          return_value={"stage":"BLOCKED","acceptance":{}}):
            with self.assertRaises(ValueError):
                step_links_v2.build(".", [], links)


if __name__ == "__main__":
    unittest.main()
