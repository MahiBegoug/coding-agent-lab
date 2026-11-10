"""Create disposable evaluation workspaces and run their tests in Docker."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from core.models import TestResult


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_IMAGE_NAME = "coding-agent-lab-runner"


def create_workspace(case: str) -> Path:
    """Copy one evaluation case into a new workspace under the user's home."""
    case_path = Path(case)
    if case_path.is_absolute() or len(case_path.parts) != 1 or case_path.parts[0] in {".", ".."}:
        raise ValueError("case must name one directory directly under evals")

    evals_dir = (_PROJECT_ROOT / "evals").resolve()
    source = (evals_dir / case_path).resolve(strict=True)
    if source.parent != evals_dir or not source.is_dir():
        raise ValueError("case must name an evaluation directory directly under evals")

    home = Path.home().resolve()
    cache_dir = home / ".cache" / "coding-agent-lab"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = cache_dir.resolve()
    try:
        cache_dir.relative_to(home)
    except ValueError as exc:
        raise ValueError("workspace cache must be located under the user's home directory") from exc

    workspace = Path(tempfile.mkdtemp(prefix=f"{source.name}-", dir=cache_dir))
    shutil.copytree(source, workspace, dirs_exist_ok=True)
    return workspace


def run_tests(workspace: Path | str) -> TestResult:
    """Run pytest in a network-isolated, read-only Docker container."""
    workspace_path = Path(workspace).resolve(strict=True)
    if not workspace_path.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {workspace_path}")

    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--mount",
        f"type=bind,source={workspace_path},target=/workspace,readonly",
        "--workdir",
        "/workspace",
        _IMAGE_NAME,
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    output = completed.stdout
    if completed.stderr:
        output = f"{output}\n{completed.stderr}" if output else completed.stderr
    return TestResult(
        passed=completed.returncode == 0,
        output=output,
        returncode=completed.returncode,
    )
