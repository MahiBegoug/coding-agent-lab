"""Copy one evaluation project and test that copy inside Docker.

The host may start the container. Project code and pytest run only in the
container, with networking disabled and the workspace mounted read-only.
"""

import shutil
import subprocess
import uuid
from pathlib import Path

from core.models import TestResult

IMAGE_NAME = "coding-agent-lab-runner"
CONTAINER_WORKDIR = "/workspace"


class WorkspaceRunner:
    """Create a disposable workspace and run its tests in Docker."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "coding-agent-lab")

    def copy_project(self, source: Path) -> Path:
        """Copy a project directory into a new folder under the home cache."""

        source_path = Path(source).resolve()
        if not source_path.is_dir():
            raise FileNotFoundError(f"Project directory does not exist: {source_path}")
        destination = self.cache_dir / f"{source_path.name}-{uuid.uuid4().hex}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_path, destination)
        return destination

    def run_tests(self, workspace: Path) -> TestResult:
        """Run pytest in a short-lived container and return its result."""

        workspace_path = Path(workspace).resolve()
        if not workspace_path.is_dir():
            raise FileNotFoundError(f"Workspace does not exist: {workspace_path}")
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            f"type=bind,source={workspace_path},target={CONTAINER_WORKDIR},readonly",
            "--workdir",
            CONTAINER_WORKDIR,
            IMAGE_NAME,
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = f"{completed.stdout}{completed.stderr}"
        return TestResult(
            passed=completed.returncode == 0,
            output=output,
            returncode=completed.returncode,
        )
