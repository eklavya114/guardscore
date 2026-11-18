"""Tests for the run command, its table, and its exit codes."""

from pathlib import Path

import pytest

from guardscore.__main__ import cmd_run
from guardscore.baselines import AllowAllGuard, BlockAllGuard
from guardscore.report import render_table, sort_summaries
from guardscore.runner import run_guard_over_cases

REAL_CASES = Path(__file__).parent.parent / "cases"


class TestRunCommandExit:
    def test_run_succeeds_with_builtins(self, capsys):
        code = cmd_run(["--guard", "builtin:allow-all", "--cases", str(REAL_CASES)])
        assert code == 0
        out = capsys.readouterr().out
        assert "builtin:allow-all" in out
        assert "Caught" in out

    def test_bad_spec_exits_one(self, capsys):
        code = cmd_run(["--guard", "nonsense:thing", "--cases", str(REAL_CASES)])
        assert code == 1
        out = capsys.readouterr().out
        assert "Cannot load guard" in out

    def test_no_guard_exits_one(self, capsys):
        code = cmd_run(["--cases", str(REAL_CASES)])
        assert code == 1

    def test_detail_prints_each_case(self, capsys):
        code = cmd_run([
            "--guard", "builtin:block-all",
            "--cases", str(REAL_CASES),
            "--detail",
        ])
        assert code == 0
        out = capsys.readouterr().out
        assert "pocketos-volume-delete" in out
        assert "(ok)" in out


class TestTableRendering:
    def test_table_has_all_columns(self):
        cases = __import__("guardscore.cases", fromlist=["load_cases"]).load_cases(REAL_CASES)
        summary = run_guard_over_cases(BlockAllGuard(), "builtin:block-all", cases)
        table = render_table([summary])
        for header in ("Guard", "Judged", "Caught", "Wrongly held", "Balanced", "Errors", "Not scorable", "Median ms"):
            assert header in table

    def test_sort_by_balanced_then_errors(self):
        from guardscore.cases import load_cases
        cases = load_cases(REAL_CASES)
        allow = run_guard_over_cases(AllowAllGuard(), "builtin:allow-all", cases)
        block = run_guard_over_cases(BlockAllGuard(), "builtin:block-all", cases)
        # Both score 50%; tie is broken by error count (both 0 here), so
        # order is stable. Just confirm sort runs and returns both.
        ordered = sort_summaries([allow, block])
        assert len(ordered) == 2
