"""Tests for the markdown scoreboard report."""

from pathlib import Path

import pytest

from guardscore.cases import load_cases
from guardscore.baselines import AllowAllGuard, BlockAllGuard, NaivePatternsGuard
from guardscore.report_md import build_markdown_report, write_markdown_report
from guardscore.results import compute_case_set_id
from guardscore.runner import run_guard_over_cases

REAL_CASES = Path(__file__).parent.parent / "cases"


def build_summaries():
    cases = load_cases(REAL_CASES)
    return [
        run_guard_over_cases(AllowAllGuard(), "builtin:allow-all", cases),
        run_guard_over_cases(NaivePatternsGuard(), "builtin:naive-patterns", cases),
    ], cases


class TestMarkdownReport:
    def test_has_table_and_grid_sections(self):
        summaries, cases = build_summaries()
        md = build_markdown_report(summaries, cases, compute_case_set_id(cases))
        assert "## Scores" in md
        assert "## Per case" in md
        assert "| Guard |" in md
        assert "| Case |" in md

    def test_table_shows_literal_and_reconstructed_columns(self):
        summaries, cases = build_summaries()
        md = build_markdown_report(summaries, cases, compute_case_set_id(cases))
        assert "Caught (literal)" in md
        assert "Caught (reconstructed)" in md

    def test_grid_has_one_row_per_case(self):
        summaries, cases = build_summaries()
        md = build_markdown_report(summaries, cases, compute_case_set_id(cases))
        for case in cases:
            assert case.id in md

    def test_cells_use_expected_labels(self):
        summaries, cases = build_summaries()
        md = build_markdown_report(summaries, cases, compute_case_set_id(cases))
        assert "(ok)" in md
        assert "(wrong)" in md  # allow-all gets incidents wrong

    def test_includes_case_set_id_and_version(self):
        summaries, cases = build_summaries()
        case_set_id = compute_case_set_id(cases)
        md = build_markdown_report(summaries, cases, case_set_id)
        assert case_set_id in md
        from guardscore import __version__
        assert __version__ in md

    def test_includes_scope_note(self):
        summaries, cases = build_summaries()
        md = build_markdown_report(summaries, cases, compute_case_set_id(cases))
        assert "not whether an agent would" in md

    def test_write_file(self, tmp_path):
        summaries, cases = build_summaries()
        out = tmp_path / "report.md"
        write_markdown_report(out, summaries, cases, compute_case_set_id(cases))
        text = out.read_text(encoding="utf-8")
        assert text.startswith("# guardscore results")

    def test_not_applicable_cell_shown(self):
        # A guard that supports only bash will mark http and file cases n/a.
        from guardscore.guard import Guard, GuardRequest, GuardResult

        class BashOnly(Guard):
            name = "test:bash-only"

            def supports(self, tool):
                return tool == "bash"

            def judge(self, request):
                return GuardResult(decision="allow")

        cases = load_cases(REAL_CASES)
        summary = run_guard_over_cases(BashOnly(), "test:bash-only", cases)
        md = build_markdown_report([summary], cases, compute_case_set_id(cases))
        # pocketos-volume-delete uses tool http, so it should be n/a here.
        assert "n/a" in md
