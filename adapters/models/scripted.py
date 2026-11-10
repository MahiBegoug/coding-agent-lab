"""A prepared sequence of replies that stands in for a model."""


class ScriptedClient:
    """Return the next pre-written reply each time chat is called.

    This is an answer-card stack, not a live model. It does not call a model,
    Docker, or the Internet.
    """

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self._index = 0

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Return the next prepared reply for this conversation."""

        del messages
        if self._index >= len(self._replies):
            raise RuntimeError("ScriptedClient has no replies remaining.")
        reply = self._replies[self._index]
        self._index += 1
        return reply
