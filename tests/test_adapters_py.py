"""Tests for the py guard adapter and the load_guard dispatcher."""

from pathlib import Path

import pytest

from guardscore.adapters import GuardSpecError, load_guard, load_py_guard
from guardscore.baselines import AllowAllGuard
from guardscore.guard import GuardRequest


def make_request(text="ls -la") -> GuardRequest:
    return GuardRequest(tool="bash", text=text, task="do a thing", cwd=Path("."))


class TestLoadGuardDispatch:
    def test_loads_builtin(self):
        guard = load_guard("builtin:allow-all")
        assert isinstance(guard, AllowAllGuard)

    def test_unknown_spec_raises(self):
        with pytest.raises(GuardSpecError):
            load_guard("nonsense:spec")

    def test_loads_py_guard(self):
        guard = load_guard("py:sample_guards:block_everything")
        assert guard.judge(make_request()).decision == "block"


class TestPyAdapterDecisions:
    def test_string_decision(self):
        guard = load_py_guard("py:sample_guards:allow_everything")
        assert guard.judge(make_request()).decision == "allow"

    def test_dict_with_reason(self):
        guard = load_py_guard("py:sample_guards:dict_with_reason")
        result = guard.judge(make_request())
        assert result.decision == "ask"
        assert result.reason == "needs a human to look"

    def test_function_sees_the_text(self):
        guard = load_py_guard("py:sample_guards:echoes_text")
        assert guard.judge(make_request(text="rm -rf /")).decision == "block"
        assert guard.judge(make_request(text="git status")).decision == "allow"


class TestPyAdapterErrors:
    def test_bad_return_type_is_error(self):
        guard = load_py_guard("py:sample_guards:returns_bad_type")
        result = guard.judge(make_request())
        assert result.is_error

    def test_bad_decision_is_error(self):
        guard = load_py_guard("py:sample_guards:returns_bad_decision")
        result = guard.judge(make_request())
        assert result.is_error

    def test_dict_without_decision_is_error(self):
        guard = load_py_guard("py:sample_guards:dict_without_decision")
        result = guard.judge(make_request())
        assert result.is_error

    def test_crashing_function_is_error_not_exception(self):
        guard = load_py_guard("py:sample_guards:crashes")
        result = guard.judge(make_request())
        assert result.is_error
        assert "crash" in result.error


class TestPySpecParsing:
    def test_missing_function_part_raises(self):
        with pytest.raises(GuardSpecError):
            load_py_guard("py:sample_guards")

    def test_unknown_module_raises(self):
        with pytest.raises(GuardSpecError):
            load_py_guard("py:no_such_module_here:func")

    def test_unknown_function_raises(self):
        with pytest.raises(GuardSpecError):
            load_py_guard("py:sample_guards:no_such_function")

    def test_empty_function_name_raises(self):
        with pytest.raises(GuardSpecError):
            load_py_guard("py:sample_guards:")
