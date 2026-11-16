"""Tests for the guard interface, request object, and result types."""

import dataclasses
from pathlib import Path

import pytest

from guardscore.cases import Action, Case, Source
from guardscore.guard import (
    ALLOWED_DECISIONS,
    REASON_MAX_LEN,
    Guard,
    GuardRequest,
    GuardResult,
    build_request,
)

FORBIDDEN_FIELDS = {"id", "title", "why", "expected", "tags", "outcome", "source"}


def make_case(**overrides) -> Case:
    defaults = dict(
        id="secret-incident-id",
        kind="incident",
        title="Secret title that must not leak",
        expected="hold",
        tags=["destructive"],
        why="Secret why that must not leak",
        task="Fix a broken build.",
        action=Action(tool="bash", text="rm -rf build/", reconstructed=True),
        source=Source(urls=["https://example.com"], date="2025-01", reliability="reported"),
        outcome="harm",
        path=Path("secret-incident-id.toml"),
    )
    defaults.update(overrides)
    return Case(**defaults)


class TestGuardRequest:
    def test_request_has_only_allowed_fields(self):
        case = make_case()
        request = build_request(case, cwd=Path("/tmp/fake"))

        field_names = {f.name for f in dataclasses.fields(request)}
        assert field_names == {"tool", "text", "task", "cwd"}

    def test_request_contains_no_forbidden_values(self):
        case = make_case()
        request = build_request(case, cwd=Path("/tmp/fake"))

        request_values = {request.tool, request.text, request.task, str(request.cwd)}
        for forbidden in (case.id, case.title, case.why):
            assert forbidden not in request_values

    def test_request_fields_match_case_action_and_task(self):
        case = make_case()
        request = build_request(case, cwd=Path("/tmp/fake"))

        assert request.tool == case.action.tool
        assert request.text == case.action.text
        assert request.task == case.task

    def test_request_dict_has_no_forbidden_keys(self):
        case = make_case()
        request = build_request(case, cwd=Path("/tmp/fake"))
        request_dict = dataclasses.asdict(request)

        for forbidden_field in FORBIDDEN_FIELDS:
            assert forbidden_field not in request_dict


class TestGuardResult:
    def test_allow_decision(self):
        result = GuardResult(decision="allow")
        assert result.decision == "allow"
        assert not result.is_error
        assert not result.held

    def test_ask_and_block_are_held(self):
        assert GuardResult(decision="ask").held
        assert GuardResult(decision="block").held

    def test_allow_is_not_held(self):
        assert not GuardResult(decision="allow").held

    def test_error_result(self):
        result = GuardResult(error="guard crashed")
        assert result.is_error
        assert not result.held

    def test_invalid_decision_becomes_error(self):
        result = GuardResult(decision="maybe")
        assert result.is_error
        assert result.decision is None

    def test_reason_is_trimmed_to_300_chars(self):
        long_reason = "x" * 500
        result = GuardResult(decision="block", reason=long_reason)
        assert len(result.reason) == REASON_MAX_LEN

    def test_reason_is_one_line(self):
        result = GuardResult(decision="block", reason="first line\nsecond line")
        assert "\n" not in result.reason
        assert result.reason == "first line"

    def test_all_allowed_decisions_valid(self):
        for decision in ALLOWED_DECISIONS:
            result = GuardResult(decision=decision)
            assert not result.is_error


class TestGuardBaseClass:
    def test_supports_defaults_to_true(self):
        guard = Guard()
        assert guard.supports("bash") is True
        assert guard.supports("http") is True

    def test_judge_not_implemented(self):
        guard = Guard()
        with pytest.raises(NotImplementedError):
            guard.judge(GuardRequest(tool="bash", text="ls", task="list files", cwd=Path(".")))
