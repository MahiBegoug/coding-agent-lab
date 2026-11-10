"""Decide which one repair action is allowed, then record the outcome.

The model may suggest a next step. This module checks that suggestion and
calls at most one tool. It does not start Docker or import an adapter.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

from core.models import ModelAction, RepairResult, TestResult
from core.ports import ChatClient, RepairToolsPort
from core.prompts import case_request, system_instruction, tool_result_message

DECISION_BUDGET = 8

_TOOL_FIELDS = {
    "read_file": {"path"},
    "run_tests": set(),
    "edit_file": {"path", "content"},
}


def _pairs_to_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object and reject a repeated key."""

    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def parse_model_action(reply: str) -> ModelAction:
    """Convert one raw reply into a single permitted tool action."""

    text = reply.strip()
    if not text:
        raise ValueError("invalid reply")
    try:
        value, end = json.JSONDecoder(object_pairs_hook=_pairs_to_object).raw_decode(text)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid reply") from exc
    if text[end:].strip() or not isinstance(value, dict):
        raise ValueError("invalid reply")

    tool = value.get("tool")
    if not isinstance(tool, str) or tool not in _TOOL_FIELDS:
        raise ValueError("unknown tool")
    required = _TOOL_FIELDS[tool]
    allowed = required | {"tool", "summary"}
    if set(value) - allowed:
        raise ValueError("field not allowed")
    if required - set(value):
        raise ValueError("missing field")

    arguments: dict[str, object] = {}
    for field in required:
        field_value = value[field]
        if not isinstance(field_value, str):
            raise ValueError("invalid field")
        arguments[field] = field_value
    summary = value.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("invalid summary")
    return ModelAction(tool=tool, arguments=arguments, summary=summary)


class RepairAgent:
    """Run a bounded repair conversation and stop on a clear outcome."""

    def __init__(
        self,
        client: ChatClient,
        tools: RepairToolsPort,
        *,
        case_name: str,
        relative_files: list[str],
        workspace: str = "",
        decision_budget: int = DECISION_BUDGET,
        trace_listener: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.case_name = case_name
        self.relative_files = list(relative_files)
        self.workspace = workspace
        self.decision_budget = decision_budget
        self.trace_listener = trace_listener

    def repair(self) -> RepairResult:
        """Ask for one action at a time until the repair succeeds or stops."""

        trace: list[dict[str, object]] = []

        def emit(event: dict[str, object]) -> None:
            trace.append(event)
            if self.trace_listener is not None:
                self.trace_listener(event)

        emit({"event": "repair_started", "case": self.case_name})
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_instruction()},
            {"role": "user", "content": case_request(self.case_name, self.relative_files)},
        ]
        saw_read = False
        saw_failing_test = False
        edited = False
        changed_files: list[str] = []
        test_result: TestResult | None = None

        def finish(passed: bool, reason: str) -> RepairResult:
            emit({"event": "repair_finished", "passed": passed, "reason": reason})
            return RepairResult(
                passed=passed,
                trace=trace,
                changed_files=list(changed_files),
                workspace=self.workspace,
                test_result=test_result,
            )

        def remember(action: ModelAction, observation: str, *, ok: bool, detail: str) -> None:
            event: dict[str, object] = {
                "event": "tool_result",
                "tool": action.tool,
                "ok": ok,
                "detail": detail,
            }
            if action.summary:
                event["summary"] = action.summary
            event["observation"] = observation
            emit(event)
            messages.append({"role": "user", "content": tool_result_message(observation)})

        for _ in range(self.decision_budget):
            try:
                reply = self.client.chat(messages)
            except Exception as exc:
                reason = f"client error: {exc}"
                emit({"event": "model_response", "accepted": False, "reason": reason})
                return finish(False, reason)

            try:
                action = parse_model_action(reply)
            except ValueError as exc:
                emit({"event": "model_response", "accepted": False, "reason": str(exc)})
                return finish(False, str(exc))

            response: dict[str, object] = {
                "event": "model_response",
                "tool": action.tool,
                "accepted": True,
            }
            if action.summary:
                response["summary"] = action.summary
            if action.tool in {"read_file", "edit_file"}:
                response["path"] = action.arguments.get("path")
            emit(response)
            messages.append({"role": "assistant", "content": reply})

            if action.tool == "edit_file" and not (saw_read and saw_failing_test):
                observation = (
                    "policy error: an edit requires one successful read_file "
                    "and one failing run_tests"
                )
                remember(action, observation, ok=False, detail=observation)
                continue

            try:
                observation, detail, outcome = self._run_action(action, edited=edited)
            except Exception as exc:
                remember(action, f"error: {exc}", ok=False, detail=f"error: {exc}")
                continue

            if outcome.get("read"):
                saw_read = True
            if outcome.get("failing_test"):
                saw_failing_test = True
            if outcome.get("edited_path"):
                edited = True
                edited_path = str(outcome["edited_path"])
                if edited_path not in changed_files:
                    changed_files.append(edited_path)
            if "test_result" in outcome:
                test_result = outcome["test_result"]

            remember(action, observation, ok=True, detail=detail)
            stop = outcome.get("stop")
            if isinstance(stop, str):
                return finish(bool(outcome.get("passed")), stop)

        return finish(False, "decision budget reached")

    def _run_action(
        self,
        action: ModelAction,
        *,
        edited: bool,
    ) -> tuple[str, str, dict[str, object]]:
        """Execute one accepted action and describe what happened."""

        if action.tool == "read_file":
            path = _argument(action.arguments, "path")
            text = self.tools.read_file(path)
            return f"read_file {path}\n{text}", f"read {path}", {"read": True}

        if action.tool == "run_tests":
            result = self.tools.run_tests()
            observation = (
                f"run_tests passed={result.passed} returncode={result.returncode}\n{result.output}"
            )
            if result.passed and edited:
                return observation, "passed", {"test_result": result, "stop": "tests passed", "passed": True}
            if result.passed:
                return (
                    observation,
                    "passed before any edit",
                    {"test_result": result, "stop": "no reproducible bug", "passed": False},
                )
            return observation, "failed", {"test_result": result, "failing_test": True}

        path = _argument(action.arguments, "path")
        content = _argument(action.arguments, "content")
        self.tools.edit_file(path, content)
        return f"edit_file {path} saved", f"saved {path}", {"edited_path": path}


def _argument(arguments: Mapping[str, object], name: str) -> str:
    value = arguments[name]
    if not isinstance(value, str):
        raise ValueError(f"invalid field: {name}")
    return value
