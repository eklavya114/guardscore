"""Adapters that turn a guard spec string into a Guard object.

Supported specs so far:
    py:package.module:function

The py adapter imports a Python function and calls it in process. It
cannot enforce a timeout, because there is no safe, portable way to
interrupt an arbitrary Python call. That limit is written up in
docs/guards.md.
"""

from __future__ import annotations

import dataclasses
import importlib
from typing import Callable

from guardscore.guard import Guard, GuardRequest, GuardResult


class GuardSpecError(ValueError):
    """Raised when a guard spec cannot be parsed or loaded."""


class PyFunctionGuard(Guard):
    """Wraps a plain Python function as a guard.

    The function receives a dict with keys tool, text, task, and cwd. It
    may return a decision string, or a dict with a decision and an
    optional reason.
    """

    def __init__(self, spec: str, func: Callable):
        self.name = spec
        self._func = func

    def judge(self, request: GuardRequest) -> GuardResult:
        payload = {
            "tool": request.tool,
            "text": request.text,
            "task": request.task,
            "cwd": str(request.cwd),
        }
        try:
            answer = self._func(payload)
        except Exception as exc:
            return GuardResult(error=f"python guard raised an exception: {exc}")

        return _result_from_answer(answer)


def _result_from_answer(answer) -> GuardResult:
    if isinstance(answer, str):
        return GuardResult(decision=answer)

    if isinstance(answer, dict):
        decision = answer.get("decision")
        reason = answer.get("reason")
        if not isinstance(decision, str):
            return GuardResult(error="python guard dict missing a string 'decision'")
        return GuardResult(decision=decision, reason=reason if isinstance(reason, str) else None)

    return GuardResult(error=f"python guard returned an unsupported type: {type(answer).__name__}")


def load_py_guard(spec: str) -> PyFunctionGuard:
    """Load a guard from a spec of the form py:package.module:function."""
    body = spec[len("py:"):]
    if ":" not in body:
        raise GuardSpecError(
            f"py guard spec must look like py:package.module:function, got '{spec}'"
        )

    module_path, func_name = body.rsplit(":", 1)
    if not module_path or not func_name:
        raise GuardSpecError(
            f"py guard spec must look like py:package.module:function, got '{spec}'"
        )

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise GuardSpecError(f"could not import module '{module_path}': {exc}") from exc

    try:
        func = getattr(module, func_name)
    except AttributeError as exc:
        raise GuardSpecError(
            f"module '{module_path}' has no function '{func_name}'"
        ) from exc

    if not callable(func):
        raise GuardSpecError(f"'{module_path}:{func_name}' is not callable")

    return PyFunctionGuard(spec, func)


def load_guard(spec: str) -> Guard:
    """Turn any supported guard spec into a Guard object.

    Raises GuardSpecError with a plain message if the spec is unknown or
    cannot be loaded.
    """
    from guardscore.baselines import BUILTIN_GUARDS

    if spec in BUILTIN_GUARDS:
        return BUILTIN_GUARDS[spec]()

    if spec.startswith("py:"):
        return load_py_guard(spec)

    raise GuardSpecError(f"unknown guard spec: '{spec}'")
