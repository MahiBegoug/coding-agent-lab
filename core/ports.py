"""Contracts for help the repair loop may request.

A Protocol names the methods another part of the program must provide. It
does not choose an implementation, start Docker, or call a model.
"""

from typing import Protocol

from core.models import TestResult


class ChatClient(Protocol):
    """Something that can answer one turn of a conversation."""

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Return the next reply for the given conversation."""


class RepairToolsPort(Protocol):
    """Safe read, edit, and test operations on one workspace.

    The name ends in Port because a later concrete class, RepairTools,
    satisfies this contract.
    """

    def read_file(self, path: str) -> str:
        """Return the UTF-8 text of one file inside the workspace."""

    def edit_file(self, path: str, content: str) -> None:
        """Replace one workspace file with the given UTF-8 text."""

    def run_tests(self) -> TestResult:
        """Run the workspace tests and return the structured result."""


class TraceRecorder(Protocol):
    """Optional recorder for public repair events."""

    def record(self, event: str, payload: dict[str, object]) -> None:
        """Store one public event and its small payload."""
