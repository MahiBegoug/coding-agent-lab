"""Repair-loop tests using a scripted client and fake tools."""

import json

import pytest

from adapters.models.scripted import ScriptedClient
from core.models import RepairResult, TestResult
from core.repair_agent import RepairAgent


class FakeTools:
    """Record tool calls and return prepared test results."""

    def __init__(self, test_results: list[TestResult] | None = None, files: dict[str, str] | None = None) -> None:
        self.test_results = list(test_results or [])
        self.files = dict(files or {"test_calculator.py": "def test_adds():\n    assert False\n"})
        self.reads: list[str] = []
        self.edits: list[tuple[str, str]] = []

    def read_file(self, path: str) -> str:
        self.reads.append(path)
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def edit_file(self, path: str, content: str) -> None:
        self.edits.append((path, content))
        self.files[path] = content

    def run_tests(self) -> TestResult:
        if not self.test_results:
            raise RuntimeError("no prepared test result")
        return self.test_results.pop(0)


class GuardTools:
    """Fail the test if the agent calls a tool."""

    def read_file(self, path: str) -> str:
        raise AssertionError(f"read_file was called for {path}")

    def edit_file(self, path: str, content: str) -> None:
        raise AssertionError(f"edit_file was called for {path}")

    def run_tests(self) -> TestResult:
        raise AssertionError("run_tests was called")


def _agent(replies: list[str], tools: FakeTools | GuardTools, **kwargs: object) -> RepairAgent:
    return RepairAgent(
        ScriptedClient(replies),
        tools,
        case_name=str(kwargs.pop("case_name", "arithmetic")),
        relative_files=list(kwargs.pop("relative_files", ["calculator.py", "test_calculator.py"])),
        workspace=str(kwargs.pop("workspace", "workspace")),
        decision_budget=int(kwargs.pop("decision_budget", 8)),
    )


def test_successful_repair_follows_the_evidence_order() -> None:
    """A read, a failing test, an edit, and a passing test finish as a repair."""

    tools = FakeTools(
        test_results=[
            TestResult(passed=False, output="failed", returncode=1),
            TestResult(passed=True, output="passed", returncode=0),
        ]
    )
    replies = [
        json.dumps({"tool": "read_file", "path": "test_calculator.py", "summary": "Read the test"}),
        json.dumps({"tool": "run_tests", "summary": "Reproduce the failure"}),
        json.dumps(
            {
                "tool": "edit_file",
                "path": "calculator.py",
                "content": "return left + right\n",
                "summary": "Fix addition",
            }
        ),
        json.dumps({"tool": "run_tests", "summary": "Verify the repair"}),
    ]

    result = _agent(replies, tools).repair()

    assert result.passed is True
    assert result.workspace == "workspace"
    assert result.changed_files == ["calculator.py"]
    assert result.test_result == TestResult(passed=True, output="passed", returncode=0)
    assert tools.reads == ["test_calculator.py"]
    assert tools.edits == [("calculator.py", "return left + right\n")]
    events = [event["event"] for event in result.trace]
    assert events[0] == "repair_started"
    assert "model_response" in events
    assert "tool_result" in events
    assert events[-1] == "repair_finished"
    assert any(event.get("summary") == "Read the test" for event in result.trace)
    assert result.trace[-1]["reason"] == "tests passed"


@pytest.mark.parametrize(
    "reply",
    [
        "please fix the bug",
        '```json\n{"tool":"run_tests"}\n```',
        '["run_tests"]',
        '{"tool":"read_file","path":"a.py","path":"b.py"}',
        '{"tool":"run_tests","path":"calculator.py"}',
        '{"tool":"edit_file","path":"calculator.py"}',
        '{"tool":"shell","command":"ls"}',
        '{"tool":"read_file"}',
    ],
)
def test_invalid_reply_calls_no_tool(reply: str) -> None:
    """Prose, fences, arrays, duplicate keys, and illegal fields stop the loop."""

    result = _agent([reply], GuardTools()).repair()

    assert isinstance(result, RepairResult)
    assert result.passed is False
    assert result.changed_files == []
    assert result.trace[-1]["event"] == "repair_finished"
    assert result.trace[-1]["passed"] is False


def test_edit_before_a_failing_test_is_rejected() -> None:
    """A successful read is not enough evidence to allow an edit."""

    tools = FakeTools()
    replies = [
        json.dumps({"tool": "read_file", "path": "test_calculator.py", "summary": "Read the test"}),
        json.dumps(
            {"tool": "edit_file", "path": "calculator.py", "content": "changed", "summary": "Edit too early"}
        ),
    ]

    result = _agent(replies, tools, decision_budget=2).repair()

    assert result.passed is False
    assert tools.reads == ["test_calculator.py"]
    assert tools.edits == []
    assert any(event.get("detail") == "policy error: an edit requires one successful read_file and one failing run_tests" for event in result.trace)
    assert result.trace[-1]["reason"] == "decision budget reached"


def test_decision_budget_stops_the_loop() -> None:
    """Eight decisions without a finished repair return a failed result."""

    tools = FakeTools(files={"test_calculator.py": "test text"})
    replies = [
        json.dumps({"tool": "read_file", "path": "test_calculator.py", "summary": "Read again"})
        for _ in range(8)
    ]

    result = _agent(replies, tools).repair()

    assert result.passed is False
    assert tools.reads == ["test_calculator.py"] * 8
    assert tools.edits == []
    assert result.trace[-1]["reason"] == "decision budget reached"


def test_passing_baseline_is_not_a_repair() -> None:
    """A test that already passes means there is no reproducible bug."""

    tools = FakeTools(test_results=[TestResult(passed=True, output="ok", returncode=0)])
    replies = [json.dumps({"tool": "run_tests", "summary": "Reproduce the failure"})]

    result = _agent(replies, tools).repair()

    assert result.passed is False
    assert result.test_result is not None
    assert result.test_result.passed is True
    assert tools.edits == []
    assert result.trace[-1]["reason"] == "no reproducible bug"


def test_client_error_returns_a_repair_result() -> None:
    """An exhausted scripted client still produces a failed RepairResult."""

    result = _agent([], FakeTools()).repair()

    assert isinstance(result, RepairResult)
    assert result.passed is False
    assert result.test_result is None
    assert result.trace[0]["event"] == "repair_started"
    assert result.trace[-1]["event"] == "repair_finished"
    assert result.trace[-1]["passed"] is False
    assert "client error" in str(result.trace[-1]["reason"])
    assert "no replies remaining" in str(result.trace[-1]["reason"])
