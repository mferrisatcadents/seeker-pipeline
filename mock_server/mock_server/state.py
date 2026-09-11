"""
In-memory state shared between the mock endpoints and the dashboard:

- `RequestLogStore`: a bounded ring buffer of recent requests, so the
  dashboard's live log has something to poll without a database.
- `DelayOverrides`: lets the dashboard change a route's delay at runtime
  without editing routes.yaml or restarting the server — the manifest value
  is just the *starting* delay.

Both are locked because Flask's dev server can be threaded and a request
handler + a dashboard poll can race.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, asdict


@dataclass
class RequestLogEntry:
    timestamp: str
    method: str
    path: str
    status: int
    duration_ms: int
    vendor: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class RequestLogStore:
    def __init__(self, max_entries: int = 200):
        self._entries: deque[RequestLogEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def record(self, entry: RequestLogEntry) -> None:
        with self._lock:
            self._entries.appendleft(entry)

    def recent(self) -> list[dict]:
        with self._lock:
            return [e.to_dict() for e in self._entries]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class DelayOverrides:
    def __init__(self):
        self._overrides: dict[str, int] = {}
        self._lock = threading.Lock()

    def set(self, path: str, delay_ms: int) -> None:
        with self._lock:
            self._overrides[path] = max(0, int(delay_ms))

    def get(self, path: str, default_ms: int) -> int:
        with self._lock:
            return self._overrides.get(path, default_ms)

    def as_dict(self) -> dict[str, int]:
        with self._lock:
            return dict(self._overrides)


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
