"""Per-conversation tool-call budget, enforced by the Coordinator in code.

`InMemoryToolBudget` lives in the runtime process. AgentCore Runtime keeps each session in its own
microVM, so the count holds for the life of a session. Track A step A5 replaces it with a store
backed by AgentCore Memory; the graph only depends on the `ToolBudget` protocol.
"""

from collections import OrderedDict
from typing import Protocol

DEFAULT_MAX_SESSIONS = 10_000


class ToolBudget(Protocol):
    async def used(self, session_id: str) -> int: ...

    async def add(self, session_id: str, calls: int) -> None: ...


class InMemoryToolBudget:
    """Counts tool calls per session. Forgets the least recently used session past the cap."""

    def __init__(self, max_sessions: int = DEFAULT_MAX_SESSIONS) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be at least 1")
        self._max_sessions = max_sessions
        self._counts: OrderedDict[str, int] = OrderedDict()

    async def used(self, session_id: str) -> int:
        return self._counts.get(session_id, 0)

    async def add(self, session_id: str, calls: int) -> None:
        if calls < 0:
            raise ValueError("calls must not be negative")
        # No awaits in here, so concurrent turns on one event loop can't interleave.
        self._counts[session_id] = self._counts.get(session_id, 0) + calls
        self._counts.move_to_end(session_id)
        while len(self._counts) > self._max_sessions:
            self._counts.popitem(last=False)
