"""
Per-session conversation memory.

This is what lets the bot hold a coherent two-way conversation: each browser
session gets its own short rolling history, so a follow-up like "what about for
self-employed people?" is understood in context.

Kept in process memory for simplicity. For production or multiple backend
replicas, swap the dict for Redis (the public API below stays the same).
"""
import time
from collections import defaultdict, deque
from threading import Lock


class SessionMemory:
    def __init__(self, max_turns: int = 8, ttl_seconds: int = 3600):
        # maxlen = max_turns * 2 because each turn is a user + assistant message
        self._store: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_turns * 2)
        )
        self._last_seen: dict[str, float] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds

    def add(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            self._store[session_id].append({"role": role, "content": content})
            self._last_seen[session_id] = time.time()

    def get(self, session_id: str) -> list[dict]:
        with self._lock:
            self._evict_expired()
            return list(self._store.get(session_id, []))

    def _evict_expired(self) -> None:
        now = time.time()
        dead = [s for s, t in self._last_seen.items() if now - t > self._ttl]
        for s in dead:
            self._store.pop(s, None)
            self._last_seen.pop(s, None)
