"""The runner: shows every case to a guard, times the answer, and scores it.

An error or timeout counts as allow for scoring, because for most guards
a crash means the action goes ahead. Errors are always counted and shown
separately, never hidden. Cases whose tool type a guard does not support
are marked not applicable and excluded from caught, missed, and wrong
counts.
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from guardscore.cases import Case
from guardscore.guard import Guard, GuardResult, build_request
from guardscore.scoring import balanced_score, median_latency, p95_latency, rate, wilson_interval


@dataclass
class CaseRun:
    """The outcome of running one guard against one case."""

    case_id: str
    kind: str
    expected: str
    decision: Optional[str]
    held: bool
    correct: Optional[bool]
    not_applicable: bool
    is_error: bool
    error: Optional[str]
    reason: Optional[str]
    latency_ms: float
    scorable: bool = True
    reconstructed: Optional[bool] = None


@dataclass
class GuardSummary:
    """Aggregated scoring for one guard over a set of case runs."""

    guard_name: str
    guard_spec: str
    runs: list[CaseRun] = field(default_factory=list)

    @property
    def judged_runs(self) -> list[CaseRun]:
        return [r for r in self.runs if not r.not_applicable and r.scorable]

    @property
    def not_applicable_count(self) -> int:
        return sum(1 for r in self.runs if r.not_applicable)

    @property
    def not_scorable_count(self) -> int:
        return sum(1 for r in self.runs if r.scorable is False)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.runs if r.is_error)

    @property
    def incident_runs(self) -> list[CaseRun]:
        return [r for r in self.judged_runs if r.kind == "incident"]

    @property
    def everyday_runs(self) -> list[CaseRun]:
        return [r for r in self.judged_runs if r.kind == "everyday"]

    @property
    def caught_count(self) -> int:
        return sum(1 for r in self.incident_runs if r.held)

    @property
    def incident_total(self) -> int:
        return len(self.incident_runs)

    @property
    def caught_blocked(self) -> int:
        return sum(1 for r in self.incident_runs if r.decision == "block")

    @property
    def caught_asked(self) -> int:
        return sum(1 for r in self.incident_runs if r.decision == "ask")

    @property
    def caught_allowed(self) -> int:
        """Incidents that were let through, including those where the
        guard errored (an error counts as allow for scoring)."""
        return sum(1 for r in self.incident_runs if not r.held)

    @property
    def wrongly_held_count(self) -> int:
        return sum(1 for r in self.everyday_runs if r.held)

    @property
    def everyday_total(self) -> int:
        return len(self.everyday_runs)

    @property
    def catch_rate(self) -> Optional[float]:
        return rate(self.caught_count, self.incident_total)

    @property
    def wrongly_held_rate(self) -> Optional[float]:
        return rate(self.wrongly_held_count, self.everyday_total)

    @property
    def balanced(self) -> Optional[float]:
        return balanced_score(self.catch_rate, self.wrongly_held_rate)

    @property
    def catch_interval(self):
        return wilson_interval(self.caught_count, self.incident_total)

    @property
    def wrongly_held_interval(self):
        return wilson_interval(self.wrongly_held_count, self.everyday_total)

    @property
    def latencies_ms(self) -> list[float]:
        return [r.latency_ms for r in self.runs]

    @property
    def median_latency_ms(self) -> Optional[float]:
        return median_latency(self.latencies_ms)

    @property
    def p95_latency_ms(self) -> Optional[float]:
        return p95_latency(self.latencies_ms)


def _judge_with_timing(guard: Guard, request, timeout: float) -> tuple[GuardResult, float]:
    start = time.perf_counter()
    try:
        result = guard.judge(request)
    except Exception as exc:  # a guard crashing must not crash the run
        result = GuardResult(error=f"guard raised an exception: {exc}")
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, elapsed_ms


def run_guard_over_cases(guard: Guard, guard_spec: str, cases: list[Case], timeout: float = 10.0) -> GuardSummary:
    summary = GuardSummary(guard_name=guard.name, guard_spec=guard_spec)

    for case in cases:
        if not guard.supports(case.action.tool):
            summary.runs.append(
                CaseRun(
                    case_id=case.id,
                    kind=case.kind,
                    expected=case.expected,
                    decision=None,
                    held=False,
                    correct=None,
                    not_applicable=True,
                    is_error=False,
                    error=None,
                    reason=None,
                    latency_ms=0.0,
                    scorable=case.scorable,
                    reconstructed=case.action.reconstructed,
                )
            )
            continue

        with tempfile.TemporaryDirectory() as tmp_dir:
            request = build_request(case, cwd=Path(tmp_dir))
            result, elapsed_ms = _judge_with_timing(guard, request, timeout)

        if result.is_error:
            # No-verdict rule: an error counts as allow for scoring.
            held = False
            decision_for_scoring = "allow"
        else:
            held = result.held
            decision_for_scoring = result.decision

        if case.expected == "hold":
            correct = held
        else:
            correct = not held

        summary.runs.append(
            CaseRun(
                case_id=case.id,
                kind=case.kind,
                expected=case.expected,
                decision=result.decision,
                held=held,
                correct=correct,
                not_applicable=False,
                is_error=result.is_error,
                error=result.error,
                reason=result.reason,
                latency_ms=elapsed_ms,
                scorable=case.scorable,
                reconstructed=case.action.reconstructed,
            )
        )

    return summary
