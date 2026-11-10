"""Unit tests for workspace path checks and repair tools."""

from pathlib import Path

import pytest

from adapters.sandbox.repair_tools import RepairTools, safe_path
from core.models import TestResult


class FakeRunner:
    """Stand-in runner that records a request and does not start a process."""

    def __init__(self) -> None:
        self.workspaces: list[Path] = []

    def run_tests(self, workspace: Path) -> TestResult:
        self.workspaces.append(workspace)
        return TestResult(passed=False, output="delegated", returncode=1)


def test_read_file_returns_workspace_text(tmp_path: Path) -> None:
    """A normal relative path can be read from the workspace."""

    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    tools = RepairTools(tmp_path, runner=FakeRunner())

    assert tools.read_file("notes.txt") == "hello"


def test_safe_path_rejects_absolute_and_parent_paths(tmp_path: Path) -> None:
    """Absolute paths and paths that resolve outside the workspace are rejected."""

    absolute = Path(tmp_path.anchor) / "outside.txt"
    with pytest.raises(ValueError):
        safe_path(tmp_path, str(absolute))
    with pytest.raises(ValueError):
        safe_path(tmp_path, "../secret.txt")


def test_read_file_rejects_paths_outside_the_workspace(tmp_path: Path) -> None:
    """Reading through an escaping path fails before any file is opened."""

    tools = RepairTools(tmp_path, runner=FakeRunner())
    absolute = Path(tmp_path.anchor) / "outside.txt"

    with pytest.raises(ValueError):
        tools.read_file(str(absolute))
    with pytest.raises(ValueError):
        tools.read_file("../secret.txt")


def test_edit_file_saves_text_and_records_the_path_once(tmp_path: Path) -> None:
    """An edit is written as UTF-8 and the same relative path is recorded once."""

    tools = RepairTools(tmp_path, runner=FakeRunner())

    tools.edit_file("calculator.py", "first\n")
    tools.edit_file("calculator.py", "second\n")

    assert (tmp_path / "calculator.py").read_text(encoding="utf-8") == "second\n"
    assert tools.changed_files == ["calculator.py"]


def test_edit_file_does_not_write_outside_the_workspace(tmp_path: Path) -> None:
    """A rejected edit does not create a file or record a change."""

    tools = RepairTools(tmp_path, runner=FakeRunner())

    with pytest.raises(ValueError):
        tools.edit_file("../escape.txt", "nope")

    assert tools.changed_files == []
    assert not (tmp_path.parent / "escape.txt").exists()


def test_run_tests_delegates_to_the_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """run_tests asks the runner and does not launch host Python."""

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("host command was launched")

    monkeypatch.setattr("adapters.sandbox.runner.subprocess.run", fail_if_called)
    runner = FakeRunner()
    tools = RepairTools(tmp_path, runner=runner)

    result = tools.run_tests()

    assert result == TestResult(passed=False, output="delegated", returncode=1)
    assert runner.workspaces == [tmp_path.resolve()]
