"""Select one supplied project and return its repair result.

This module checks the requested path and asks an injected runner for a
disposable copy. It does not parse a command line or start Docker.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from core.models import RepairResult
from core.repair_agent import RepairAgent

KNOWN_PROJECTS = frozenset(
    {
        "arithmetic",
        "balanced_brackets",
        "median",
        "multi_function",
        "unique_words",
    }
)

_SKIPPED_PARTS = frozenset({"__pycache__", ".pytest_cache"})

AgentFactory = Callable[[str, list[str], str], RepairAgent]


class ProjectCopier(Protocol):
    """Copy one project directory into a disposable workspace."""

    def copy_project(self, source: Path) -> Path:
        """Return the new workspace directory."""


class RepairService:
    """Run one repair for a project selected from evals/."""

    def __init__(self, evals_root: Path, runner: ProjectCopier, make_agent: AgentFactory) -> None:
        self.evals_root = Path(evals_root)
        self.runner = runner
        self.make_agent = make_agent

    def repair(self, project: str) -> RepairResult:
        """Copy the selected project, repair that copy, and return the result."""

        source = self._selected_project(project)
        workspace = self.runner.copy_project(source)
        relative_files = _relative_files(workspace)
        agent = self.make_agent(source.name, relative_files, str(workspace))
        return agent.repair()

    def _selected_project(self, project: str) -> Path:
        if not project or not project.strip():
            raise ValueError("Project path is empty")
        requested = Path(project)
        if requested.is_absolute():
            raise ValueError("Absolute project paths are not allowed")
        evals_root = self.evals_root.resolve()
        candidate = (evals_root.parent / requested).resolve()
        if candidate == evals_root or not candidate.is_relative_to(evals_root):
            raise ValueError("Project path is outside evals/")
        if candidate.parent != evals_root or candidate.name not in KNOWN_PROJECTS or not candidate.is_dir():
            raise ValueError(f"Unknown project: {project}")
        return candidate


def _relative_files(workspace: Path) -> list[str]:
    files: list[str] = []
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace)
        if any(part in _SKIPPED_PARTS for part in relative.parts):
            continue
        files.append(relative.as_posix())
    return sorted(files)
