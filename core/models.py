"""Data containers used by the repair agent."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestResult:
    """Result of running the project's tests."""

    passed: bool
    output: str
    returncode: int


@dataclass
class ModelAction:
    """A tool call requested by the model."""

    tool: str
    arguments: dict[str, object]
    summary: str | None = None


@dataclass
class RepairResult:
    """Outcome and trace of a repair attempt."""

    passed: bool
    trace: list[dict[str, object]] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    workspace: Path = Path(".")
    test_result: TestResult | None = None
