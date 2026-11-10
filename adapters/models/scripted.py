"""Deterministic answer-card chat client for tests and demonstrations."""

from collections.abc import Mapping, Sequence


class ScriptedClient:
    """Return pre-written replies in order, one for each chat call."""

    def __init__(self, replies: Sequence[str]) -> None:
        self._replies = tuple(replies)
        self._next_reply = 0

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        """Return the next scripted reply, or fail when the cards run out."""
        del messages
        if self._next_reply >= len(self._replies):
            raise RuntimeError("No scripted replies remain.")

        reply = self._replies[self._next_reply]
        self._next_reply += 1
        return reply
