"""Tests for the case loader and validator."""

import textwrap
import tomllib
from pathlib import Path

import pytest

from guardscore.cases import (
    Case,
    Action,
    Source,
    load_cases,
    looks_like_secret,
    validate_cases,
)

CASES_DIR = Path(__file__).parent.parent / "cases"


def make_valid_incident(**overrides) -> Case:
    defaults = dict(
        id="test-incident",
        kind="incident",
        title="Test incident",
        expected="hold",
        tags=["destructive", "cloud-api"],
        why="This action is irreversible.",
        task="Do something dangerous.",
        action=Action(tool="bash", text="rm -rf /", reconstructed=True),
        source=Source(
            urls=["https://example.com/incident"],
            date="2025-01",
            reliability="reported",
        ),
        path=Path("test-incident.toml"),
    )
    defaults.update(overrides)
    return Case(**defaults)


def make_valid_everyday(**overrides) -> Case:
    defaults = dict(
        id="everyday-test",
        kind="everyday",
        title="Safe everyday action",
        expected="allow",
        tags=["everyday"],
        why="This action is harmless.",
        task="Run a safe command.",
        action=Action(tool="bash", text="git status", reconstructed=False),
        source=None,
        path=Path("everyday-test.toml"),
    )
    defaults.update(overrides)
    return Case(**defaults)


class TestLoader:
    def test_loads_all_cases(self):
        cases = load_cases(CASES_DIR)
        assert len(cases) > 0

    def test_incident_cases_have_source(self):
        cases = load_cases(CASES_DIR)
        for case in cases:
            if case.kind == "incident":
                assert case.source is not None, f"{case.id} has no source"

    def test_everyday_cases_have_no_source(self):
        cases = load_cases(CASES_DIR)
        for case in cases:
            if case.kind == "everyday":
                assert case.source is None, f"{case.id} should not have a source"

    def test_all_shipped_cases_pass_validation(self):
        cases = load_cases(CASES_DIR)
        errors = validate_cases(cases)
        assert errors == [], f"Validation errors:\n" + "\n".join(errors)


class TestValidationMissingFields:
    def test_missing_id(self):
        case = make_valid_incident(id="")
        errors = validate_cases([case])
        assert any("id" in e for e in errors)

    def test_missing_title(self):
        case = make_valid_incident(title="")
        errors = validate_cases([case])
        assert any("title" in e for e in errors)

    def test_missing_why(self):
        case = make_valid_incident(why="")
        errors = validate_cases([case])
        assert any("why" in e for e in errors)

    def test_missing_task(self):
        case = make_valid_incident(task="")
        errors = validate_cases([case])
        assert any("task" in e for e in errors)


class TestValidationKind:
    def test_invalid_kind(self):
        case = make_valid_incident(kind="unknown")
        errors = validate_cases([case])
        assert any("kind" in e for e in errors)

    def test_valid_kinds_accepted(self):
        for kind in ("incident", "everyday"):
            case = make_valid_everyday(kind=kind) if kind == "everyday" else make_valid_incident(kind=kind)
            errors = validate_cases([case])
            assert not any("kind" in e for e in errors)


class TestValidationExpected:
    def test_invalid_expected(self):
        case = make_valid_incident(expected="maybe")
        errors = validate_cases([case])
        assert any("expected" in e for e in errors)

    def test_incident_must_be_hold(self):
        case = make_valid_incident(expected="allow")
        errors = validate_cases([case])
        assert any("hold" in e for e in errors)

    def test_everyday_must_be_allow(self):
        case = make_valid_everyday(expected="hold")
        errors = validate_cases([case])
        assert any("allow" in e for e in errors)


class TestValidationTags:
    def test_empty_tags(self):
        case = make_valid_incident(tags=[])
        errors = validate_cases([case])
        assert any("tags" in e for e in errors)

    def test_unknown_tag(self):
        case = make_valid_incident(tags=["destructive", "not-a-real-tag"])
        errors = validate_cases([case])
        assert any("tag" in e for e in errors)

    def test_everyday_missing_everyday_tag(self):
        case = make_valid_everyday(tags=["filesystem"])
        errors = validate_cases([case])
        assert any("everyday" in e for e in errors)


class TestValidationId:
    def test_id_must_match_filename(self):
        case = make_valid_incident(id="wrong-id", path=Path("test-incident.toml"))
        errors = validate_cases([case])
        assert any("match" in e for e in errors)

    def test_duplicate_ids_rejected(self):
        case1 = make_valid_incident(id="dupe", path=Path("dupe.toml"))
        case2 = make_valid_incident(id="dupe", path=Path("dupe.toml"))
        errors = validate_cases([case1, case2])
        assert any("duplicate" in e for e in errors)


class TestValidationSource:
    def test_incident_missing_source(self):
        case = make_valid_incident(source=None)
        errors = validate_cases([case])
        assert any("source" in e for e in errors)

    def test_source_url_must_be_https(self):
        case = make_valid_incident(
            source=Source(urls=["http://example.com"], date="2025-01", reliability="reported")
        )
        errors = validate_cases([case])
        assert any("https" in e for e in errors)

    def test_bad_date_format(self):
        case = make_valid_incident(
            source=Source(urls=["https://example.com"], date="January 2025", reliability="reported")
        )
        errors = validate_cases([case])
        assert any("date" in e for e in errors)

    def test_bad_reliability(self):
        case = make_valid_incident(
            source=Source(urls=["https://example.com"], date="2025-01", reliability="rumor")
        )
        errors = validate_cases([case])
        assert any("reliability" in e for e in errors)

    def test_incident_missing_reconstructed(self):
        case = make_valid_incident(action=Action(tool="bash", text="rm -rf /", reconstructed=None))
        errors = validate_cases([case])
        assert any("reconstructed" in e for e in errors)


class TestSecretDetection:
    def test_sk_prefix_secret_blocked(self):
        assert looks_like_secret("sk-" + "a" * 20)

    def test_akia_secret_blocked(self):
        assert looks_like_secret("AKIA" + "A" * 16)

    def test_github_token_blocked(self):
        assert looks_like_secret("ghp_" + "a" * 36)

    def test_safe_text_passes(self):
        assert not looks_like_secret("rm -rf /tmp/old_logs/")

    def test_redacted_placeholder_passes(self):
        assert not looks_like_secret("aws s3 rm s3://REDACTED --recursive")

    def test_case_with_secret_flagged(self):
        secret = "sk-" + "x" * 25
        case = make_valid_incident(action=Action(tool="bash", text=f"curl -H 'Authorization: Bearer {secret}'", reconstructed=True))
        errors = validate_cases([case])
        assert any("secret" in e for e in errors)


class TestActionTool:
    def test_invalid_tool(self):
        case = make_valid_incident(action=Action(tool="curl", text="curl https://example.com", reconstructed=True))
        errors = validate_cases([case])
        assert any("tool" in e for e in errors)

    def test_valid_tools_accepted(self):
        for tool in ("bash", "http", "file", "mcp"):
            case = make_valid_incident(action=Action(tool=tool, text="some action", reconstructed=True))
            errors = validate_cases([case])
            assert not any("action.tool" in e for e in errors)
