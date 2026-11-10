"""Safe file tools for a disposable evaluation workspace."""

from pathlib import Path, PureWindowsPath

from adapters.sandbox import runner
from core.models import TestResult


def safe_path(workspace: Path | str, requested_path: Path | str) -> Path:
    """Resolve a workspace-relative path and reject paths outside the workspace."""
    requested = Path(requested_path)
    if requested.is_absolute() or PureWindowsPath(str(requested_path)).is_absolute():
        raise ValueError("absolute paths are not allowed")

    root = Path(workspace).resolve()
    resolved = (root / requested).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path must stay inside the workspace") from exc
    return resolved


class RepairTools:
    """Read, edit, and test files in a disposable workspace."""

    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).resolve()
        self.changed_files: list[str] = []

    def read_file(self, path: str) -> str:
        """Read a UTF-8 file from the workspace."""
        return safe_path(self.workspace, path).read_text(encoding="utf-8")

    def edit_file(self, path: str, content: str) -> None:
        """Write a UTF-8 file and record its relative path once."""
        target = safe_path(self.workspace, path)
        target.write_text(content, encoding="utf-8")
        relative_path = target.relative_to(self.workspace).as_posix()
        if relative_path not in self.changed_files:
            self.changed_files.append(relative_path)

    def run_tests(self) -> TestResult:
        """Delegate test execution to the Docker-backed runner."""
        return runner.run_tests(self.workspace)
