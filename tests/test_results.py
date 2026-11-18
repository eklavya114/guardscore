"""Tests for the JSON results file and the case set id."""

import json
from pathlib import Path

import pytest

from guardscore.cases import Action, Case, Source, load_cases
from guardscore.results import (
    SCHEMA_VERSION,
    build_results,
    compute_case_set_id,
    write_results_file,
)
from guardscore.baselines import BlockAllGuard
from guardscore.runner import run_guard_over_cases

REAL_CASES = Path(__file__).parent.parent / "cases"


def write_case_file(folder: Path, name: str, content: str) -> Path:
    path = folder / name
    path.write_bytes(content.encode("utf-8"))
    return path


def make_case(path: Path) -> Case:
    return Case(
        id=path.stem,
        kind="everyday",
        title="x",
        expected="allow",
        tags=["everyday"],
        why="x",
        task="x",
        action=Action(tool="bash", text="ls", reconstructed=False),
        source=None,
        outcome=None,
        path=path,
    )


class TestCaseSetId:
    def test_stable_across_line_endings(self, tmp_path):
        unix_dir = tmp_path / "unix"
        win_dir = tmp_path / "win"
        unix_dir.mkdir()
        win_dir.mkdir()

        p1 = write_case_file(unix_dir, "a.toml", "id = \"a\"\ntext = \"x\"\n")
        p2 = write_case_file(win_dir, "a.toml", "id = \"a\"\r\ntext = \"x\"\r\n")

        id_unix = compute_case_set_id([make_case(p1)], cases_dir=unix_dir)
        id_win = compute_case_set_id([make_case(p2)], cases_dir=win_dir)

        assert id_unix == id_win

    def test_id_changes_when_content_changes(self, tmp_path):
        d = tmp_path / "cases"
        d.mkdir()
        p1 = write_case_file(d, "a.toml", "id = \"a\"\n")
        first = compute_case_set_id([make_case(p1)], cases_dir=d)

        p1.write_bytes(b"id = \"a\"\ndifferent\n")
        second = compute_case_set_id([make_case(p1)], cases_dir=d)

        assert first != second

    def test_id_is_twelve_hex_chars(self):
        cases = load_cases(REAL_CASES)
        case_set_id = compute_case_set_id(cases)
        assert len(case_set_id) == 12
        int(case_set_id, 16)  # must parse as hex

    def test_id_is_deterministic(self):
        cases = load_cases(REAL_CASES)
        assert compute_case_set_id(cases) == compute_case_set_id(cases)

    def test_order_independent(self, tmp_path):
        d = tmp_path / "cases"
        d.mkdir()
        pa = write_case_file(d, "a.toml", "id = \"a\"\n")
        pb = write_case_file(d, "b.toml", "id = \"b\"\n")

        forward = compute_case_set_id([make_case(pa), make_case(pb)], cases_dir=d)
        backward = compute_case_set_id([make_case(pb), make_case(pa)], cases_dir=d)
        assert forward == backward


class TestResultsFile:
    def test_schema_and_fields(self):
        cases = load_cases(REAL_CASES)
        summary = run_guard_over_cases(BlockAllGuard(), "builtin:block-all", cases)
        results = build_results([summary], cases)

        assert results["schema_version"] == SCHEMA_VERSION
        assert "guardscore_version" in results
        assert len(results["case_set_id"]) == 12
        assert "started_utc" in results["run"]
        assert "python_version" in results["run"]
        assert "platform" in results["run"]
        assert len(results["guards"]) == 1

    def test_guard_rows_have_expected_keys(self):
        cases = load_cases(REAL_CASES)
        summary = run_guard_over_cases(BlockAllGuard(), "builtin:block-all", cases)
        results = build_results([summary], cases)

        guard = results["guards"][0]
        assert guard["spec"] == "builtin:block-all"
        row = guard["rows"][0]
        for key in ("case_id", "kind", "expected", "decision", "correct", "latency_ms", "error", "reason", "scorable", "reconstructed"):
            assert key in row

    def test_schema_version_is_two(self):
        assert SCHEMA_VERSION == 2

    def test_summary_has_literal_and_reconstructed_groups(self):
        cases = load_cases(REAL_CASES)
        summary = run_guard_over_cases(BlockAllGuard(), "builtin:block-all", cases)
        results = build_results([summary], cases)

        group_summary = results["guards"][0]["summary"]
        for key in ("caught_literal", "caught_reconstructed"):
            assert key in group_summary
            group = group_summary[key]
            for field in ("caught", "total", "rate", "interval_low", "interval_high", "small_sample"):
                assert field in group

    def test_write_results_file_is_valid_json(self, tmp_path):
        cases = load_cases(REAL_CASES)
        summary = run_guard_over_cases(BlockAllGuard(), "builtin:block-all", cases)
        out = tmp_path / "results.json"
        write_results_file(out, [summary], cases)

        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["schema_version"] == SCHEMA_VERSION
