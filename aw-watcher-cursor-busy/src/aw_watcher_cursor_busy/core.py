from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from aw_core.models import Event

WATCHER_NAME = "aw-watcher-cursor-busy"
EVENT_TYPE = "cursor.busy"
DEFAULT_POLL_INTERVAL = 0.25
DEFAULT_PULSETIME = 1.0
DEFAULT_MIN_DURATION = 0.5


@dataclass(frozen=True)
class BusySample:
    cursor: str
    app: str
    title: str
    pid: int | None

    def to_event_data(self) -> dict[str, object]:
        return {
            "status": "busy",
            "cursor": self.cursor,
            "app": self.app,
            "title": self.title,
            "pid": self.pid,
        }


class ActivityWatchLikeClient(Protocol):
    client_hostname: str

    def create_bucket(self, bucket_id: str, event_type: str, queued: bool = False):
        ...

    def heartbeat(self, bucket_id: str, event: Event, pulsetime: float, queued: bool = False, commit_interval=None):
        ...


class BusyTracker:
    def __init__(self, min_duration: float = DEFAULT_MIN_DURATION):
        self.min_duration = timedelta(seconds=min_duration)
        self._data: dict[str, object] | None = None
        self._started_at: datetime | None = None
        self._emitted = False

    def update(self, sample: BusySample | None, now: datetime) -> list[Event]:
        if sample is None:
            self.reset()
            return []

        data = sample.to_event_data()
        if data != self._data:
            self._data = data
            self._started_at = now
            self._emitted = False
            return []

        if self._started_at is None:
            self._started_at = now
            return []

        if not self._emitted:
            if now - self._started_at < self.min_duration:
                return []
            self._emitted = True
            return [Event(timestamp=self._started_at, data=data)]

        return [Event(timestamp=now, data=data)]

    def reset(self) -> None:
        self._data = None
        self._started_at = None
        self._emitted = False


class CursorBusyWatcher:
    def __init__(
        self,
        client: ActivityWatchLikeClient,
        pulsetime: float = DEFAULT_PULSETIME,
        min_duration: float = DEFAULT_MIN_DURATION,
    ):
        self.client = client
        self.pulsetime = pulsetime
        self.bucket_id = f"{WATCHER_NAME}_{client.client_hostname}"
        self.tracker = BusyTracker(min_duration=min_duration)

    def ensure_bucket(self) -> None:
        self.client.create_bucket(self.bucket_id, event_type=EVENT_TYPE)

    def process_sample(self, sample: BusySample | None, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        events = self.tracker.update(sample, now)
        for event in events:
            self.client.heartbeat(
                self.bucket_id,
                event,
                pulsetime=self.pulsetime,
                queued=True,
                commit_interval=self.pulsetime,
            )
        return len(events)
