"""Thread-safe latest-state mailboxes; producers never perform socket I/O."""
from dataclasses import dataclass, field
from threading import Lock
import time


@dataclass(eq=False)
class Subscriber:
    pending: list = field(default_factory=list)
    replaced: int = 0


class ConnectionManager:
    def __init__(self):
        self.lock = Lock()
        self.rooms = {}
        self.sequence = 0

    def connect(self, session_id, cap=4):
        with self.lock:
            room = self.rooms.setdefault(session_id, set())
            if len(room) >= cap:
                raise ValueError('Subscriber capacity reached')
            subscriber = Subscriber()
            room.add(subscriber)
            return subscriber

    def disconnect(self, session_id, subscriber):
        with self.lock:
            room = self.rooms.get(session_id, set())
            room.discard(subscriber)
            subscriber.pending.clear()
            if not room:
                self.rooms.pop(session_id, None)

    def publish(self, session_id, events):
        with self.lock:
            for event in events:
                # Microseconds fit exactly in JavaScript integers. Gaps are intentional.
                self.sequence = max(self.sequence + 1, time.time_ns() // 1000)
                event.sequence = self.sequence
            for subscriber in self.rooms.get(session_id, ()):
                subscriber.replaced += bool(subscriber.pending)
                subscriber.pending = events

    def take(self, subscriber):
        with self.lock:
            events, subscriber.pending = subscriber.pending, []
            return events


manager = ConnectionManager()
