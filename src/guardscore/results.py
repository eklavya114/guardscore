"""The JSON results file and the case set id.

The case set id is a fingerprint of the whole case collection. It is
computed so it is identical on every operating system: paths use posix
separators, and file contents have their line endings normalized to \\n
before hashing. That way a checkout with Windows line endings and a
checkout with Unix line endings produce the same id.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from guardscore import __version__
from guardscore.cases import Case
from guardscore.runner import GuardSummary

SCHEMA_VERSION = 1


def compute_case_set_id(cases: list[Case], cases_dir: Optional[Path] = None) -> str:
    """First 12 hex characters of a sha256 over every case file.

    Files are taken in sorted path order. For each one, the posix
    relative path and the file content with line endings normalized to
    \\n are fed into the hash.
    """
    paths = sorted((c.path for c in cases if c.path is not None), key=lambda p: p.as_posix())

    if cases_dir is None and paths:
        cases_dir = _common_parent(paths)

    hasher = hashlib.sha256()
    for path in paths:
        if cases_dir is not None:
            try:
                rel = path.relative_to(cases_dir)
            except ValueError:
                rel = path
        else:
            rel = path
        rel_posix = rel.as_posix()

        raw = path.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

        hasher.update(rel_posix.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(normalized)
        hasher.update(b"\0")

    return hasher.hexdigest()[:12]


def _common_parent(paths: list[Path]) -> Optional[Path]:
    if not paths:
        return None
    parent = paths[0].parent
    for p in paths[1:]:
        while True:
            try:
                p.relative_to(parent)
                break
            except ValueError:
                if parent.parent == parent:
                    return parent
                parent = parent.parent
    return parent


def _summary_to_dict(summary: GuardSummary) -> dict:
    return {
        "spec": summary.guard_spec,
        "name": summary.guard_name,
        "summary": {
            "judged": len(summary.judged_runs),
            "caught": summary.caught_count,
            "incident_total": summary.incident_total,
            "caught_blocked": summary.caught_blocked,
            "caught_asked": summary.caught_asked,
            "caught_allowed": summary.caught_allowed,
            "wrongly_held": summary.wrongly_held_count,
            "everyday_total": summary.everyday_total,
            "catch_rate": summary.catch_rate,
            "wrongly_held_rate": summary.wrongly_held_rate,
            "balanced_score": summary.balanced,
            "errors": summary.error_count,
            "not_applicable": summary.not_applicable_count,
            "not_scorable": summary.not_scorable_count,
            "median_latency_ms": summary.median_latency_ms,
            "p95_latency_ms": summary.p95_latency_ms,
        },
        "rows": [
            {
                "case_id": r.case_id,
                "kind": r.kind,
                "expected": r.expected,
                "decision": r.decision,
                "correct": r.correct,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "reason": r.reason,
                "scorable": r.scorable,
                "reconstructed": r.reconstructed,
            }
            for r in summary.runs
        ],
    }


def build_results(summaries: list[GuardSummary], cases: list[Case]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "guardscore_version": __version__,
        "case_set_id": compute_case_set_id(cases),
        "run": {
            "started_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "guards": [_summary_to_dict(s) for s in summaries],
    }


def write_results_file(path: Path, summaries: list[GuardSummary], cases: list[Case]) -> None:
    results = build_results(summaries, cases)
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
