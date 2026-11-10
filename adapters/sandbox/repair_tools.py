"""Read, edit, and test files inside one disposable workspace."""

from pathlib import Path

from core.models import TestResult

from adapters.sandbox.runner import WorkspaceRunner


def safe_path(workspace: Path, requested_path: str) -> Path:
    """Resolve a relative workspace path, rejecting paths that escape it."""

    if not requested_path or not requested_path.strip():
        raise ValueError("Path is empty")
    requested = Path(requested_path)
    if requested.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {requested_path}")
    workspace_path = Path(workspace).resolve()
    resolved = (workspace_path / requested).resolve()
    if not resolved.is_relative_to(workspace_path):
        raise ValueError(f"Path is outside the workspace: {requested_path}")
    return resolved


class RepairTools:
    """Workspace file tools that satisfy RepairToolsPort."""

    def __init__(self, workspace: Path, runner: WorkspaceRunner | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.runner = runner if runner is not None else WorkspaceRunner()
        self.changed_files: list[str] = []

    def read_file(self, path: str) -> str:
        """Return the UTF-8 text of one file inside the workspace."""

        target = safe_path(self.workspace, path)
        return target.read_text(encoding="utf-8")

    def edit_file(self, path: str, content: str) -> None:
        """Replace one workspace file and record its relative path once."""

        target = safe_path(self.workspace, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        relative = target.relative_to(self.workspace).as_posix()
        if relative not in self.changed_files:
            self.changed_files.append(relative)

    def run_tests(self) -> TestResult:
        """Ask the Docker-backed runner to test this workspace."""

        return self.runner.run_tests(self.workspace)
