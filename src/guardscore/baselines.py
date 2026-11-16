"""Baseline guards built into guardscore.

These are sanity floors, not rivals and not recommendations. They exist
so every real guard has something simple to be compared against. The
naive-patterns list is small and generic on purpose. It was written
without looking at the shipped incident cases, so it may miss some of
them or wrongly hold some everyday cases. That is expected and is not
a bug to fix.
"""

from __future__ import annotations

import hashlib
import re

from guardscore.guard import Guard, GuardRequest, GuardResult

# Generic patterns for well known destructive actions. This list is not
# tuned against the cases in this repository.
_NAIVE_PATTERNS = [
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b"),  # recursive force delete
    re.compile(r"\bgit\s+push\s+.*--force\b"),  # force push
    re.compile(r"\bgit\s+reset\s+--hard\b"),  # hard reset discards work
    re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE),  # SQL drop
    re.compile(r"\|\s*(sh|bash|zsh)\b"),  # pipe to a shell
    re.compile(r"\bmkfs(\.\w+)?\b"),  # reformat a filesystem
]


class AllowAllGuard(Guard):
    """Always answers allow. A floor for how low a guard can score."""

    name = "builtin:allow-all"

    def judge(self, request: GuardRequest) -> GuardResult:
        return GuardResult(decision="allow", reason="allow-all always allows")


class BlockAllGuard(Guard):
    """Always answers block. A floor for how high wrongly-held can go."""

    name = "builtin:block-all"

    def judge(self, request: GuardRequest) -> GuardResult:
        return GuardResult(decision="block", reason="block-all always blocks")


class CoinFlipGuard(Guard):
    """Allows or blocks based on a hash of the request, so repeated runs
    over the same case give the same answer."""

    name = "builtin:coin-flip"
    _SEED = "guardscore-coin-flip-v1"

    def judge(self, request: GuardRequest) -> GuardResult:
        digest = hashlib.sha256(f"{self._SEED}:{request.tool}:{request.text}".encode("utf-8")).hexdigest()
        is_even = int(digest[:8], 16) % 2 == 0
        decision = "allow" if is_even else "block"
        return GuardResult(decision=decision, reason="coin-flip hashed the request")


class NaivePatternsGuard(Guard):
    """Blocks when the action text matches one of a small list of
    generic destructive patterns. This is a sanity floor, not a
    production ready guard."""

    name = "builtin:naive-patterns"

    def judge(self, request: GuardRequest) -> GuardResult:
        for pattern in _NAIVE_PATTERNS:
            if pattern.search(request.text):
                return GuardResult(
                    decision="block",
                    reason=f"matched generic destructive pattern: {pattern.pattern}",
                )
        return GuardResult(decision="allow", reason="no generic destructive pattern matched")


BUILTIN_GUARDS = {
    "builtin:allow-all": AllowAllGuard,
    "builtin:block-all": BlockAllGuard,
    "builtin:coin-flip": CoinFlipGuard,
    "builtin:naive-patterns": NaivePatternsGuard,
}
