"""The markdown scoreboard report."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from guardscore import __version__
from guardscore.cases import Case
from guardscore.report import (
    _fmt_caught,
    _fmt_ms,
    _fmt_rate,
    _fmt_wrongly_held,
    sort_summaries,
)
from guardscore.runner import GuardSummary

SCOPE_NOTE = (
    "This measures whether a guard holds an action when it is shown the "
    "action, not whether an agent would ever try the action. The sample "
    "is small, so read the numbers as a rough floor, not a ranking."
)


def _md_table(summaries: list[GuardSummary]) -> str:
    header = "| Guard | Judged | Caught | Wrongly held | Balanced | Errors | Median ms |"
    divider = "| --- | --- | --- | --- | --- | --- | --- |"
    lines = [header, divider]
    for s in sort_summaries(summaries):
        lines.append(
            f"| {s.guard_name} | {len(s.judged_runs)} | {_fmt_caught(s)} | "
            f"{_fmt_wrongly_held(s)} | {_fmt_rate(s.balanced)} | {s.error_count} | "
            f"{_fmt_ms(s.median_latency_ms)} |"
        )
    return "\n".join(lines)


def _cell_for(summary: GuardSummary, case_id: str) -> str:
    run = next((r for r in summary.runs if r.case_id == case_id), None)
    if run is None:
        return "n/a"
    if run.not_applicable:
        return "n/a"
    if run.is_error:
        return "error"
    mark = "ok" if run.correct else "wrong"
    return f"{run.decision} ({mark})"


def _md_grid(summaries: list[GuardSummary], cases: list[Case]) -> str:
    ordered = sort_summaries(summaries)
    guard_names = [s.guard_name for s in ordered]

    header = "| Case | " + " | ".join(guard_names) + " |"
    divider = "| --- | " + " | ".join("---" for _ in guard_names) + " |"
    lines = [header, divider]

    for case in cases:
        cells = [_cell_for(s, case.id) for s in ordered]
        lines.append(f"| {case.id} | " + " | ".join(cells) + " |")

    return "\n".join(lines)


def build_markdown_report(summaries: list[GuardSummary], cases: list[Case], case_set_id: str) -> str:
    parts = [
        "# guardscore results",
        "",
        "## Scores",
        "",
        _md_table(summaries),
        "",
        "## Per case",
        "",
        _md_grid(summaries, cases),
        "",
        "## About this run",
        "",
        f"Case set id: `{case_set_id}`",
        "",
        f"guardscore version: {__version__}",
        "",
        SCOPE_NOTE,
        "",
    ]
    return "\n".join(parts)


def write_markdown_report(path: Path, summaries: list[GuardSummary], cases: list[Case], case_set_id: str) -> None:
    path.write_text(build_markdown_report(summaries, cases, case_set_id), encoding="utf-8")
