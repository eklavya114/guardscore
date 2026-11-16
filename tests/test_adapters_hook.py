"""Tests for the Claude Code hook guard adapter.

Each test writes a tiny Python stub hook to a temp folder and runs it
through the adapter with sys.executable.
"""

import shlex
import sys
import textwrap
from pathlib import Path

import pytest

from guardscore.adapters import GuardSpecError, load_hook_guard
from guardscore.guard import GuardRequest


def make_request(text="rm -rf /", tool="bash", task="clean up", cwd="."):
    return GuardRequest(tool=tool, text=text, task=task, cwd=Path(cwd))


def write_stub(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "stub_hook.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return script


def spec_for(script: Path) -> str:
    return f"claude-hook:{shlex.quote(sys.executable)} {shlex.quote(str(script))}"


class TestHookDecisionMapping:
    def test_exit_2_means_block(self, tmp_path):
        script = write_stub(tmp_path, """
            import sys
            print("destructive command blocked", file=sys.stderr)
            sys.exit(2)
        """)
        guard = load_hook_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.decision == "block"
        assert "destructive" in result.reason

    def test_json_deny_means_block(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "nope"}}))
        """)
        guard = load_hook_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.decision == "block"
        assert result.reason == "nope"

    def test_json_ask_means_ask(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask"}}))
        """)
        guard = load_hook_guard(spec_for(script))
        assert guard.judge(make_request()).decision == "ask"

    def test_json_allow_means_allow(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"}}))
        """)
        guard = load_hook_guard(spec_for(script))
        assert guard.judge(make_request()).decision == "allow"

    def test_exit_0_no_output_means_allow(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            sys.exit(0)
        """)
        guard = load_hook_guard(spec_for(script))
        assert guard.judge(make_request()).decision == "allow"

    def test_other_nonzero_exit_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            import sys
            print("something went wrong", file=sys.stderr)
            sys.exit(1)
        """)
        guard = load_hook_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.is_error
        assert "exit 1" in result.error

    def test_unknown_permission_decision_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "defer"}}))
        """)
        guard = load_hook_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.is_error

    def test_exit_2_overrides_json_allow(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow"}}))
            sys.exit(2)
        """)
        guard = load_hook_guard(spec_for(script))
        assert guard.judge(make_request()).decision == "block"


class TestHookToolApplicability:
    def test_non_bash_case_is_not_applicable(self, tmp_path):
        script = write_stub(tmp_path, "import sys; sys.exit(0)")
        guard = load_hook_guard(spec_for(script))
        assert guard.supports("bash") is True
        assert guard.supports("http") is False
        assert guard.supports("file") is False
        assert guard.supports("mcp") is False


class TestHookReceivesInput:
    def test_hook_sees_command_in_tool_input(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            data = json.loads(sys.stdin.read())
            cmd = data["tool_input"]["command"]
            decision = "deny" if "rm " in cmd else "allow"
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision}}))
        """)
        guard = load_hook_guard(spec_for(script))
        assert guard.judge(make_request(text="rm -rf /")).decision == "block"
        assert guard.judge(make_request(text="git status")).decision == "allow"


class TestHookNeverExecutesCaseText:
    def test_marker_file_not_created(self, tmp_path):
        marker = tmp_path / "marker.txt"
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            sys.exit(0)
        """)
        guard = load_hook_guard(spec_for(script))
        guard.judge(make_request(text=f"touch {marker} && echo pwned"))
        assert not marker.exists()


class TestHookSpecParsing:
    def test_empty_command_raises(self):
        with pytest.raises(GuardSpecError):
            load_hook_guard("claude-hook:")
