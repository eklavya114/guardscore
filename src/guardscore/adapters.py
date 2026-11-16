"""Adapters that turn a guard spec string into a Guard object.

Supported specs so far:
    py:package.module:function

The py adapter imports a Python function and calls it in process. It
cannot enforce a timeout, because there is no safe, portable way to
interrupt an arbitrary Python call. That limit is written up in
docs/guards.md.
"""

from __future__ import annotations

import importlib
import json
import shlex
import subprocess
import tempfile
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


class CommandGuard(Guard):
    """Runs an external program as a guard.

    The request is sent to the program as one JSON object on stdin. The
    program must print one line of JSON {"decision": ..., "reason": ...}
    on stdout. The case text is never placed on the command line.

    guardscore runs whatever command you give it, so only use guards you
    trust.
    """

    def __init__(self, spec: str, argv: list[str], timeout: float = 10.0):
        self.name = spec
        self._argv = argv
        self._timeout = timeout

    def judge(self, request: GuardRequest) -> GuardResult:
        payload = json.dumps(
            {
                "tool": request.tool,
                "text": request.text,
                "task": request.task,
                "cwd": str(request.cwd),
            }
        )

        with tempfile.TemporaryDirectory() as work_dir:
            try:
                completed = subprocess.run(
                    self._argv,
                    input=payload,
                    capture_output=True,
                    text=True,
                    cwd=work_dir,
                    timeout=self._timeout,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                return GuardResult(error=f"command timed out after {self._timeout} seconds")
            except (OSError, ValueError) as exc:
                return GuardResult(error=f"could not run command: {exc}")

        return _result_from_command_output(completed.returncode, completed.stdout, completed.stderr)


def _result_from_command_output(returncode: int, stdout: str, stderr: str) -> GuardResult:
    text = stdout.strip()
    if not text:
        detail = stderr.strip()[:200]
        return GuardResult(error=f"command printed no output (exit {returncode}): {detail}")

    first_line = text.splitlines()[0]
    try:
        data = json.loads(first_line)
    except json.JSONDecodeError:
        return GuardResult(error=f"command output was not JSON: {first_line[:200]}")

    if not isinstance(data, dict) or "decision" not in data:
        return GuardResult(error="command JSON missing a 'decision' field")

    decision = data.get("decision")
    reason = data.get("reason")
    if not isinstance(decision, str):
        return GuardResult(error="command 'decision' must be a string")

    return GuardResult(decision=decision, reason=reason if isinstance(reason, str) else None)


def load_cmd_guard(spec: str, timeout: float = 10.0) -> CommandGuard:
    """Load a guard from a spec of the form cmd:COMMAND LINE."""
    command_line = spec[len("cmd:"):]
    try:
        argv = shlex.split(command_line)
    except ValueError as exc:
        raise GuardSpecError(f"could not parse command line: {exc}") from exc

    if not argv:
        raise GuardSpecError("cmd guard spec has an empty command line")

    return CommandGuard(spec, argv, timeout=timeout)


class ClaudeHookGuard(Guard):
    """Runs a Claude Code PreToolUse hook script as a guard.

    This tests the hook script by itself. It does not run Claude Code and
    does not prove that an agent would really be stopped. It only shows
    how the hook script would answer for a given command.

    Only bash cases are supported. They are sent as tool_name "Bash".
    Every other tool type is not applicable.

    Mapping, based on the Claude Code hooks documentation:
      - exit 2, or a JSON permissionDecision of "deny": block
      - a JSON permissionDecision of "ask": ask
      - exit 0 with no decision, or permissionDecision "allow": allow
      - any other non-zero exit: error
      - an unrecognized permissionDecision value: error

    guardscore runs whatever command you give it, so only use hooks you
    trust.
    """

    def __init__(self, spec: str, argv: list[str], timeout: float = 10.0):
        self.name = spec
        self._argv = argv
        self._timeout = timeout

    def supports(self, tool: str) -> bool:
        return tool == "bash"

    def judge(self, request: GuardRequest) -> GuardResult:
        hook_input = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": request.text},
                "cwd": str(request.cwd),
                "session_id": "guardscore",
                "transcript_path": "",
            }
        )

        with tempfile.TemporaryDirectory() as work_dir:
            try:
                completed = subprocess.run(
                    self._argv,
                    input=hook_input,
                    capture_output=True,
                    text=True,
                    cwd=work_dir,
                    timeout=self._timeout,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                return GuardResult(error=f"hook timed out after {self._timeout} seconds")
            except (OSError, ValueError) as exc:
                return GuardResult(error=f"could not run hook: {exc}")

        return _result_from_hook_output(completed.returncode, completed.stdout, completed.stderr)


def _result_from_hook_output(returncode: int, stdout: str, stderr: str) -> GuardResult:
    # A JSON permissionDecision, when present, decides, except that exit 2
    # always blocks.
    decision_from_json = _hook_decision_from_json(stdout)

    if returncode == 2:
        reason = stderr.strip()[:300] or "hook exited 2 (block)"
        return GuardResult(decision="block", reason=reason)

    if decision_from_json is not None:
        mapped, reason = decision_from_json
        if mapped == "error":
            return GuardResult(error=reason)
        return GuardResult(decision=mapped, reason=reason)

    if returncode == 0:
        return GuardResult(decision="allow", reason="hook exited 0 with no decision")

    reason = stderr.strip()[:300] or f"hook exited {returncode}"
    return GuardResult(error=f"hook non-blocking error (exit {returncode}): {reason}")


def _hook_decision_from_json(stdout: str):
    """Return (mapped_decision, reason) from hook JSON output, or None if
    the output is not a hook decision object. mapped_decision is one of
    allow, ask, block, or error."""
    text = stdout.strip()
    if not text:
        return None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    specific = data.get("hookSpecificOutput")
    if not isinstance(specific, dict):
        return None

    permission = specific.get("permissionDecision")
    reason = specific.get("permissionDecisionReason")
    reason = reason if isinstance(reason, str) else None

    mapping = {"deny": "block", "ask": "ask", "allow": "allow"}
    if permission in mapping:
        return mapping[permission], reason

    return "error", f"hook returned an unsupported permissionDecision: {permission!r}"


def load_hook_guard(spec: str, timeout: float = 10.0) -> ClaudeHookGuard:
    """Load a guard from a spec of the form claude-hook:COMMAND LINE."""
    command_line = spec[len("claude-hook:"):]
    try:
        argv = shlex.split(command_line)
    except ValueError as exc:
        raise GuardSpecError(f"could not parse hook command line: {exc}") from exc

    if not argv:
        raise GuardSpecError("claude-hook guard spec has an empty command line")

    return ClaudeHookGuard(spec, argv, timeout=timeout)


def load_guard(spec: str, timeout: float = 10.0) -> Guard:
    """Turn any supported guard spec into a Guard object.

    Raises GuardSpecError with a plain message if the spec is unknown or
    cannot be loaded.
    """
    from guardscore.baselines import BUILTIN_GUARDS

    if spec in BUILTIN_GUARDS:
        return BUILTIN_GUARDS[spec]()

    if spec.startswith("py:"):
        return load_py_guard(spec)

    if spec.startswith("cmd:"):
        return load_cmd_guard(spec, timeout=timeout)

    if spec.startswith("claude-hook:"):
        return load_hook_guard(spec, timeout=timeout)

    raise GuardSpecError(f"unknown guard spec: '{spec}'")
