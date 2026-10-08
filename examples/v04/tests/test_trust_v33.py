"""Tests for v33 read-only trust preflight; synthetic config, no real trust actions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"watchdog"))
import app_trust_review_v33 as trust


def handler(command="python foo.py", windows=None, timeout=None):
    row={"type":"command","command":command}
    if windows is not None:
        row["commandWindows"]=windows
    if timeout is not None:
        row["timeout"]=timeout
    return row


def hooks(**kw):
    return {"hooks":{event:[{"hooks":values}] for event,values in kw.items()}}


class TrustPreflightTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.home=Path(self.t.name)/"codex-home"
        self.home.mkdir()
        self.project=Path(self.t.name)/"test-project"
        (self.project/".codex").mkdir(parents=True)
    def save(self,folder,content):
        path=folder/"hooks.json"
        path.write_text(json.dumps(content),encoding="utf8")
        return path
    def test_no_config_never_reports_trusted(self):
        out=trust.audit(self.home)
        self.assertEqual(out["hook_trust"],"NOT_VERIFIED_USE_INTERACTIVE_CODEX_CLI_SLASH_HOOKS")
        self.assertIn("NO_GLOBAL_HOOKS_DETECTED_AT_SELECTED_CODEX_HOME",out["warnings"])
        self.assertNotIn(str(self.home),json.dumps(out))
    def test_global_only_five_events(self):
        win="cmd.exe /d /s /c C:\\safe\\watchdog.cmd"
        self.save(self.home,hooks(**{x:[handler(windows=win)] for x in trust.EVENTS}))
        result=trust.audit(self.home)
        self.assertEqual(set(result["matching_group_counts"]),set(trust.EVENTS))
        self.assertTrue(all(n==1 for n in result["matching_group_counts"].values()))
        self.assertFalse(result["warnings"])
        self.assertEqual(result["layers"][0]["windows_override_commands"],5)
    def test_same_event_project_and_global_flagged_but_no_command_leak(self):
        self.save(self.home,hooks(PreToolUse=[handler(windows="cmd.exe /d /s /c C:\\private\\global.cmd")]))
        self.save(self.project/".codex",hooks(PreToolUse=[handler(windows="cmd.exe /d /s /c C:\\private\\project.cmd")]))
        report=trust.audit(self.home,self.project)
        self.assertEqual(report["matching_group_counts"]["PreToolUse"],2)
        self.assertIn("MULTIPLE_EVENT_GROUPS_MAY_DISPATCH_TOGETHER",report["warnings"])
        self.assertIn("PROJECT_HOOKS_PRESENT_ALONGSIDE_GLOBAL_OR_INDEPENDENT",report["warnings"])
        for secret in ("global.cmd","project.cmd","C:\\private"):
            self.assertNotIn(secret,json.dumps(report))
    def test_quoted_command_risk_detected_without_leaking(self):
        self.save(self.home,hooks(SessionStart=[handler('"C:\\Secret Path\\python.exe" "C:\\Secret Path\\hook.py"')]))
        warnings=trust.audit(self.home)["layers"][0]["warnings"]
        self.assertIn("NO_EXPLICIT_COMMAND_WINDOWS",warnings)
        self.assertIn("QUOTED_DEFAULT_COMMAND_WINDOWS_RISK",warnings)
    def test_windows_override_quotes_warn(self):
        self.save(self.home,hooks(Stop=[handler(windows='cmd.exe /d /s /c "C:\\Secret Path\\hook.cmd"')]))
        self.assertIn("WINDOWS_COMMAND_HAS_QUOTES_REVIEW_LAUNCH_COMPATIBILITY",
                      trust.audit(self.home)["layers"][0]["warnings"])
    def test_session_end_oversize_timeout(self):
        self.save(self.home,hooks(SessionEnd=[handler(windows="cmd.exe /d /s /c C:\\run.cmd",timeout=10)]))
        self.assertIn("SESSION_END_TIMEOUT_GT_3",trust.audit(self.home)["layers"][0]["warnings"])
    def test_invalid_json_never_echoes_contents(self):
        (self.home/"hooks.json").write_text('PRIVATE_TOKEN{not-json',encoding="utf8")
        out=trust.audit(self.home)
        self.assertIn("UNREADABLE_OR_INVALID_HOOKS_JSON",out["layers"][0]["warnings"])
        self.assertNotIn("PRIVATE_TOKEN",json.dumps(out))
    def test_invalid_handler_does_not_crash(self):
        self.save(self.home,{"hooks":{"PreToolUse":[{"hooks":["raw","bad"]}],"Stop":"oops"}})
        out=trust.audit(self.home)
        self.assertIn("INVALID_EVENT_SHAPE",out["layers"][0]["warnings"])
        self.assertIn("UNSUPPORTED_OR_INVALID_HANDLER",out["layers"][0]["warnings"])
    def test_codex_home_env_selection_not_desktop_proof(self):
        p,origin=trust.codex_home({"CODEX_HOME":str(self.home)},home=self.project)
        self.assertEqual(p,self.home.resolve())
        self.assertEqual(origin,"CODEX_HOME")
        p,origin=trust.codex_home({},home=self.project)
        self.assertEqual(p,self.project.resolve()/".codex")
        self.assertEqual(origin,"default_user_home")
    def test_toml_state_never_leaked_or_counted_as_hook(self):
        toml='''[hooks.state.'C:\\\\private\\\\hook']
trusted_hash = "SECRET_HASH"
[[hooks.PreToolUse]]
matcher = "Bash"
[[hooks.PreToolUse.hooks]]
type = "command"
command = "PRIVATE_COMMAND"'''
        (self.home/"config.toml").write_text(toml,encoding="utf8")
        report=trust.audit(self.home)
        # Python 3.9 compatibility: TOML parsing is optional; 3.11 CI has tomllib.
        self.assertNotIn("SECRET_HASH",json.dumps(report))
        self.assertNotIn("PRIVATE_COMMAND",json.dumps(report))
        if sys.version_info >= (3,11):
            self.assertEqual(report["matching_group_counts"]["PreToolUse"],1)


if __name__=="__main__":
    unittest.main()
