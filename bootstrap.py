"""Connect the repair rules to the scripted client and sandbox tools.

This is the only module that imports both core and adapters.
"""

import json
from pathlib import Path

from collections.abc import Callable

from adapters.models.scripted import ScriptedClient
from adapters.sandbox.repair_tools import RepairTools
from adapters.sandbox.runner import WorkspaceRunner
from core.repair_agent import RepairAgent
from core.repair_service import RepairService

REPO_ROOT = Path(__file__).resolve().parent
EVALS_ROOT = REPO_ROOT / "evals"

_CALCULATOR_PY = '''def add(left, right):
    """Return the sum of two numbers."""
    return left + right
'''

_BRACKETS_PY = '''def is_balanced(text):
    """Return whether parentheses, brackets, and braces are properly nested."""
    opening = "([{"
    closing = ")]}"
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []

    for character in text:
        if character in opening:
            stack.append(character)
        elif character in closing:
            if not stack or stack[-1] != pairs[character]:
                return False
            stack.pop()

    return not stack
'''

_STATISTICS_TOOLS_PY = '''def median(values):
    """Return the median value without changing the input sequence."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 0:
        return (ordered[middle - 1] + ordered[middle]) / 2
    return ordered[middle]
'''

_TEXT_TOOLS_PY = '''def normalize_name(name):
    """Trim surrounding whitespace and lowercase a supplied name."""
    return name.strip().lower()


def greeting(name):
    """Create a greeting from a normalized name."""
    return f"Hello, {normalize_name(name).title()}!"


def initials(name):
    """Return uppercase initials for the whitespace-separated parts of a name."""
    return "".join(part[0].upper() for part in name.split())
'''

_WORD_TOOLS_PY = '''def unique_words(text):
    """Return lowercase words once, in the order first seen."""
    seen: list[str] = []
    for word in text.lower().split():
        if word not in seen:
            seen.append(word)
    return seen
'''


def _reply(tool: str, summary: str, **arguments: str) -> str:
    payload: dict[str, str] = {"tool": tool, "summary": summary, **arguments}
    return json.dumps(payload)


def scripted_replies(case_name: str) -> list[str]:
    """Return one read, failing test, edit, and passing test sequence."""

    sequences = {
        "arithmetic": [
            _reply("read_file", "Read the test", path="test_calculator.py"),
            _reply("run_tests", "Reproduce the failure"),
            _reply("edit_file", "Add the operands", path="calculator.py", content=_CALCULATOR_PY),
            _reply("run_tests", "Verify the repair"),
        ],
        "balanced_brackets": [
            _reply("read_file", "Read the test", path="test_brackets.py"),
            _reply("run_tests", "Reproduce the failure"),
            _reply("edit_file", "Match each closing bracket", path="brackets.py", content=_BRACKETS_PY),
            _reply("run_tests", "Verify the repair"),
        ],
        "median": [
            _reply("read_file", "Read the test", path="test_statistics_tools.py"),
            _reply("run_tests", "Reproduce the failure"),
            _reply("edit_file", "Average the two middle values", path="statistics_tools.py", content=_STATISTICS_TOOLS_PY),
            _reply("run_tests", "Verify the repair"),
        ],
        "multi_function": [
            _reply("read_file", "Read the test", path="test_text_tools.py"),
            _reply("run_tests", "Reproduce the failure"),
            _reply("edit_file", "Keep the greeting capitalization", path="text_tools.py", content=_TEXT_TOOLS_PY),
            _reply("run_tests", "Verify the repair"),
        ],
        "unique_words": [
            _reply("read_file", "Read the test", path="test_word_tools.py"),
            _reply("run_tests", "Reproduce the failure"),
            _reply("edit_file", "Keep the first-seen order", path="word_tools.py", content=_WORD_TOOLS_PY),
            _reply("run_tests", "Verify the repair"),
        ],
    }
    try:
        return sequences[case_name]
    except KeyError as exc:
        raise ValueError(f"No scripted sequence for {case_name}") from exc


def build_service(
    provider: str,
    trace_listener: Callable[[dict[str, object]], None] | None = None,
) -> RepairService:
    """Create the runner, scripted client, tools, agent, and repair service."""

    if provider != "scripted":
        raise ValueError(f"Unsupported provider: {provider}")
    runner = WorkspaceRunner()

    def make_agent(case_name: str, relative_files: list[str], workspace: str) -> RepairAgent:
        tools = RepairTools(Path(workspace), runner=runner)
        client = ScriptedClient(scripted_replies(case_name))
        return RepairAgent(
            client,
            tools,
            case_name=case_name,
            relative_files=relative_files,
            workspace=workspace,
            trace_listener=trace_listener,
        )

    return RepairService(evals_root=EVALS_ROOT, runner=runner, make_agent=make_agent)
