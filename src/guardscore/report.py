"""Turning guard summaries into text tables and detail listings."""

from __future__ import annotations

from typing import Optional

from guardscore.runner import GuardSummary


def _fmt_rate(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.0f}%"


def _fmt_ms(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}"


def _fmt_caught(summary: GuardSummary) -> str:
    if summary.incident_total == 0:
        return "n/a"
    return f"{summary.caught_count} of {summary.incident_total}"


def _fmt_wrongly_held(summary: GuardSummary) -> str:
    if summary.everyday_total == 0:
        return "n/a"
    return f"{summary.wrongly_held_count} of {summary.everyday_total}"


def _fmt_balanced(summary: GuardSummary) -> str:
    return _fmt_rate(summary.balanced)


def sort_summaries(summaries: list[GuardSummary]) -> list[GuardSummary]:
    """Sort by balanced score descending, then by error count ascending."""
    def key(s: GuardSummary):
        balanced = s.balanced if s.balanced is not None else -1.0
        return (-balanced, s.error_count)

    return sorted(summaries, key=key)


def render_table(summaries: list[GuardSummary]) -> str:
    headers = ["Guard", "Judged", "Caught", "Wrongly held", "Balanced", "Errors", "Not scorable", "Median ms"]
    rows = []
    for s in sort_summaries(summaries):
        rows.append([
            s.guard_name,
            str(len(s.judged_runs)),
            _fmt_caught(s),
            _fmt_wrongly_held(s),
            _fmt_balanced(s),
            str(s.error_count),
            str(s.not_scorable_count),
            _fmt_ms(s.median_latency_ms),
        ])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(cells):
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    for row in rows:
        lines.append(fmt_row(row))
    return "\n".join(lines)


def render_detail(summaries: list[GuardSummary]) -> str:
    blocks = []
    for s in sort_summaries(summaries):
        lines = [f"{s.guard_name}:"]
        for run in s.runs:
            if run.not_applicable:
                verdict = "n/a"
            elif not run.scorable:
                verdict = "not scorable"
            elif run.is_error:
                verdict = "error"
            else:
                mark = "ok" if run.correct else "wrong"
                verdict = f"{run.decision} ({mark})"
            lines.append(f"  {run.case_id}: {verdict}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
