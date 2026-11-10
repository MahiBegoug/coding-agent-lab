"""Focused tests for safe workspace tools."""

from pathlib import Path

import pytest

from adapters.sandbox import runner
from adapters.sandbox.repair_tools import RepairTools, safe_path
from core.models import TestResult as StructuredTestResult


def test_read_file_from_workspace(tmp_path: Path) -> None:
    """Read a normal file using UTF-8."""
    (tmp_path / "example.txt").write_text("hello", encoding="utf-8")
    tools = RepairTools(tmp_path)

    assert tools.read_file("example.txt") == "hello"


@pytest.mark.parametrize("requested_path", ["/etc/passwd", "../outside.txt"])
def test_safe_path_rejects_paths_outside_workspace(
    tmp_path: Path, requested_path: str
) -> None:
    """Reject absolute paths and parent-directory traversal."""
    with pytest.raises(ValueError):
        safe_path(tmp_path, requested_path)


def test_edit_file_saves_content_and_records_path_once(tmp_path: Path) -> None:
    """Save an edit and keep one changed-file entry per relative path."""
    tools = RepairTools(tmp_path)

    tools.edit_file("example.txt", "first")
    tools.edit_file("example.txt", "second")

    assert (tmp_path / "example.txt").read_text(encoding="utf-8") == "second"
    assert tools.changed_files == ["example.txt"]


def test_run_tests_delegates_to_docker_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Delegate test execution without launching host Python or pytest."""
    expected = StructuredTestResult(passed=True, output="1 passed", returncode=0)
    calls: list[Path] = []

    def fake_run_tests(workspace: Path) -> StructuredTestResult:
        calls.append(workspace)
        return expected

    monkeypatch.setattr(runner, "run_tests", fake_run_tests)
    tools = RepairTools(tmp_path)

    assert tools.run_tests() is expected
    assert calls == [tmp_path.resolve()]
