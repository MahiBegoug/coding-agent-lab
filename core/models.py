"""Shared result shapes for the repair workflow.

These containers name the information that moves between the model, the
tools, and the final repair outcome. They do not call a model or run tests.
"""

from dataclasses import dataclass, field


@dataclass
class TestResult:
    """Outcome of one sandboxed test run."""

    passed: bool
    output: str
    returncode: int

    __test__ = False


@dataclass
class ModelAction:
    """One accepted model request for a single permitted tool."""

    tool: str
    arguments: dict[str, object]
    summary: str | None = None


@dataclass
class RepairResult:
    """Final outcome of one repair attempt."""

    passed: bool
    trace: list[dict[str, object]] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    workspace: str = ""
    test_result: TestResult | None = None
