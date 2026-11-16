"""Tests for the command guard adapter.

Each test writes a tiny Python stub to a temp folder and runs it through
the adapter with sys.executable, so the tests work on every platform.
"""

import shlex
import sys
import textwrap
from pathlib import Path

import pytest

from guardscore.adapters import GuardSpecError, load_cmd_guard
from guardscore.guard import GuardRequest


def make_request(text="ls -la", tool="bash", task="list files", cwd="."):
    return GuardRequest(tool=tool, text=text, task=task, cwd=Path(cwd))


def write_stub(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "stub_guard.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return script


def spec_for(script: Path) -> str:
    # shlex-safe quoting of the interpreter and the script path.
    return f"cmd:{shlex.quote(sys.executable)} {shlex.quote(str(script))}"


class TestValidAnswers:
    def test_block_answer(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"decision": "block", "reason": "no good"}))
        """)
        guard = load_cmd_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.decision == "block"
        assert result.reason == "no good"

    def test_allow_answer(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"decision": "allow"}))
        """)
        guard = load_cmd_guard(spec_for(script))
        assert guard.judge(make_request()).decision == "allow"

    def test_ask_answer(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"decision": "ask"}))
        """)
        guard = load_cmd_guard(spec_for(script))
        assert guard.judge(make_request()).decision == "ask"

    def test_guard_receives_request_on_stdin(self, tmp_path):
        script = write_stub(tmp_path, """
            import json, sys
            req = json.loads(sys.stdin.read())
            decision = "block" if "rm " in req["text"] else "allow"
            print(json.dumps({"decision": decision}))
        """)
        guard = load_cmd_guard(spec_for(script))
        assert guard.judge(make_request(text="rm -rf /")).decision == "block"
        assert guard.judge(make_request(text="git status")).decision == "allow"


class TestErrorConditions:
    def test_timeout_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            import time
            time.sleep(5)
        """)
        guard = load_cmd_guard(spec_for(script), timeout=0.5)
        result = guard.judge(make_request())
        assert result.is_error
        assert "timed out" in result.error

    def test_crash_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            import sys
            sys.exit("stub crashed on purpose")
        """)
        guard = load_cmd_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.is_error

    def test_garbage_output_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            print("this is not json at all")
        """)
        guard = load_cmd_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.is_error
        assert "not JSON" in result.error

    def test_invalid_decision_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            import json
            print(json.dumps({"decision": "maybe"}))
        """)
        guard = load_cmd_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.is_error

    def test_no_output_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            pass
        """)
        guard = load_cmd_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.is_error

    def test_json_without_decision_is_error(self, tmp_path):
        script = write_stub(tmp_path, """
            import json
            print(json.dumps({"reason": "I forgot the decision"}))
        """)
        guard = load_cmd_guard(spec_for(script))
        result = guard.judge(make_request())
        assert result.is_error


class TestCommandNeverExecutesCaseText:
    def test_marker_file_not_created(self, tmp_path):
        marker = tmp_path / "marker.txt"
        script = write_stub(tmp_path, """
            import json, sys
            json.loads(sys.stdin.read())
            print(json.dumps({"decision": "allow"}))
        """)
        guard = load_cmd_guard(spec_for(script))
        dangerous = make_request(text=f"touch {marker} && echo pwned")
        guard.judge(dangerous)
        assert not marker.exists()


class TestSpecParsing:
    def test_empty_command_raises(self):
        with pytest.raises(GuardSpecError):
            load_cmd_guard("cmd:")

    def test_unbalanced_quotes_raises(self):
        with pytest.raises(GuardSpecError):
            load_cmd_guard('cmd:python "unterminated')
