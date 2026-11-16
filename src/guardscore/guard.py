"""The guard interface: what a guard receives and what it must answer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ALLOWED_DECISIONS = {"allow", "ask", "block"}

HELD_DECISIONS = {"ask", "block"}

REASON_MAX_LEN = 300


@dataclass(frozen=True)
class GuardRequest:
    """The only information a guard is allowed to see about a case."""

    tool: str
    text: str
    task: str
    cwd: Path


@dataclass
class GuardResult:
    """What a guard answered, or why it could not answer."""

    decision: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.reason is not None:
            trimmed = self.reason.splitlines()[0] if self.reason else ""
            self.reason = trimmed[:REASON_MAX_LEN]

        if self.error is None and self.decision is not None:
            if self.decision not in ALLOWED_DECISIONS:
                self.error = f"unknown decision '{self.decision}'"
                self.decision = None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @property
    def held(self) -> bool:
        """True if this result counts as holding the action (ask or block)."""
        if self.is_error:
            return False
        return self.decision in HELD_DECISIONS


def build_request(case, cwd: Path) -> GuardRequest:
    """Build the request object a guard is allowed to see for a case.

    Only tool, text, task, and a working directory are included. The case
    id, title, why, expected, tags, outcome, and source must never appear.
    """
    return GuardRequest(
        tool=case.action.tool,
        text=case.action.text,
        task=case.task,
        cwd=cwd,
    )


class Guard:
    """Base interface for anything that judges a GuardRequest."""

    name: str = "guard"

    def supports(self, tool: str) -> bool:
        """Return True if this guard can judge a case with this tool type."""
        return True

    def judge(self, request: GuardRequest) -> GuardResult:
        raise NotImplementedError
