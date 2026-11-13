from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


ALLOWED_KINDS = {"incident", "everyday"}
ALLOWED_EXPECTED = {"hold", "allow"}
ALLOWED_TOOLS = {"bash", "http", "file", "mcp"}
ALLOWED_TAGS = {
    "filesystem", "git", "database", "cloud-api", "cloud-cli",
    "credentials", "prompt-injection", "network", "destructive", "everyday",
}
ALLOWED_RELIABILITY = {"primary", "reported", "secondhand"}

_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"),
]


def looks_like_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRET_PATTERNS)


@dataclass
class Action:
    tool: str
    text: str
    reconstructed: Optional[bool] = None


@dataclass
class Source:
    urls: list[str]
    date: str
    reliability: str


@dataclass
class Case:
    id: str
    kind: str
    title: str
    expected: str
    tags: list[str]
    why: str
    task: str
    action: Action
    source: Optional[Source] = None
    path: Optional[Path] = None


def _load_one(path: Path) -> Case:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    action_data = data.get("action", {})
    action = Action(
        tool=action_data.get("tool", ""),
        text=action_data.get("text", ""),
        reconstructed=action_data.get("reconstructed"),
    )

    source_data = data.get("source")
    source = None
    if source_data:
        source = Source(
            urls=source_data.get("urls", []),
            date=source_data.get("date", ""),
            reliability=source_data.get("reliability", ""),
        )

    return Case(
        id=data.get("id", ""),
        kind=data.get("kind", ""),
        title=data.get("title", ""),
        expected=data.get("expected", ""),
        tags=data.get("tags", []),
        why=data.get("why", ""),
        task=data.get("context", {}).get("task", ""),
        action=action,
        source=source,
        path=path,
    )


def load_cases(cases_dir: Path) -> list[Case]:
    cases = []
    for toml_file in sorted(cases_dir.rglob("*.toml")):
        cases.append(_load_one(toml_file))
    return cases


def validate_cases(cases: list[Case]) -> list[str]:
    errors: list[str] = []
    seen_ids: dict[str, Path] = {}

    for case in cases:
        fname = case.path.name if case.path else "<unknown>"
        stem = case.path.stem if case.path else ""
        prefix = f"{fname}:"

        if not case.id:
            errors.append(f"{prefix} 'id' is required")
        elif case.id != stem:
            errors.append(f"{prefix} 'id' value '{case.id}' must match file name '{stem}'")
        elif case.id in seen_ids:
            errors.append(f"{prefix} duplicate id '{case.id}' (also in {seen_ids[case.id].name})")
        else:
            seen_ids[case.id] = case.path

        if not case.kind:
            errors.append(f"{prefix} 'kind' is required")
        elif case.kind not in ALLOWED_KINDS:
            errors.append(f"{prefix} 'kind' must be one of {sorted(ALLOWED_KINDS)}, got '{case.kind}'")

        if not case.title:
            errors.append(f"{prefix} 'title' is required")

        if not case.expected:
            errors.append(f"{prefix} 'expected' is required")
        elif case.expected not in ALLOWED_EXPECTED:
            errors.append(f"{prefix} 'expected' must be one of {sorted(ALLOWED_EXPECTED)}, got '{case.expected}'")

        if not case.tags:
            errors.append(f"{prefix} 'tags' must not be empty")
        else:
            bad_tags = [t for t in case.tags if t not in ALLOWED_TAGS]
            if bad_tags:
                errors.append(f"{prefix} unknown tags: {bad_tags}")

        if not case.why:
            errors.append(f"{prefix} 'why' is required")

        if not case.task:
            errors.append(f"{prefix} 'context.task' is required")

        if not case.action.tool:
            errors.append(f"{prefix} 'action.tool' is required")
        elif case.action.tool not in ALLOWED_TOOLS:
            errors.append(f"{prefix} 'action.tool' must be one of {sorted(ALLOWED_TOOLS)}, got '{case.action.tool}'")

        if not case.action.text:
            errors.append(f"{prefix} 'action.text' is required")

        if case.kind == "incident":
            if case.expected != "hold":
                errors.append(f"{prefix} incident cases must have expected = 'hold'")

            if case.action.reconstructed is None:
                errors.append(f"{prefix} incident cases must set 'action.reconstructed'")

            if case.source is None:
                errors.append(f"{prefix} incident cases must have a [source] section")
            else:
                if not case.source.urls:
                    errors.append(f"{prefix} source.urls must not be empty")
                else:
                    bad_urls = [u for u in case.source.urls if not u.startswith("https://")]
                    if bad_urls:
                        errors.append(f"{prefix} all source URLs must start with https://, bad: {bad_urls}")

                if not case.source.date:
                    errors.append(f"{prefix} 'source.date' is required")
                elif not re.match(r"^\d{4}-\d{2}(-\d{2})?$", case.source.date):
                    errors.append(f"{prefix} 'source.date' must be YYYY-MM or YYYY-MM-DD, got '{case.source.date}'")

                if not case.source.reliability:
                    errors.append(f"{prefix} 'source.reliability' is required")
                elif case.source.reliability not in ALLOWED_RELIABILITY:
                    errors.append(
                        f"{prefix} 'source.reliability' must be one of {sorted(ALLOWED_RELIABILITY)}, "
                        f"got '{case.source.reliability}'"
                    )

        if case.kind == "everyday":
            if case.expected != "allow":
                errors.append(f"{prefix} everyday cases must have expected = 'allow'")
            if "everyday" not in case.tags:
                errors.append(f"{prefix} everyday cases must include the tag 'everyday'")

        if looks_like_secret(case.action.text):
            errors.append(f"{prefix} 'action.text' appears to contain a real secret")

    return errors
