"""In-process pub/sub for pushing event changes to browsers (Server-Sent Events).

Events are created from worker threads (detection) and request threads, while subscribers live on
the asyncio loop, so publishing hands messages over with call_soon_threadsafe.
"""

import asyncio
import json
import threading

MAX_QUEUE = 100  # a stalled browser drops old messages rather than growing memory


class AlertBroadcaster:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()

    def subscribe(self) -> tuple[asyncio.AbstractEventLoop, asyncio.Queue]:
        sub = (asyncio.get_running_loop(), asyncio.Queue(maxsize=MAX_QUEUE))
        with self._lock:
            self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub) -> None:
        with self._lock:
            self._subscribers.discard(sub)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(self, kind: str, payload: dict | None = None) -> None:
        """Send {"type": kind, ...payload} to every connected browser. Safe from any thread."""
        message = json.dumps({"type": kind, **(payload or {})}, default=str)
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(_offer, queue, message)
            except RuntimeError:  # loop already closed (browser gone during shutdown)
                self.unsubscribe((loop, queue))


def _offer(queue: asyncio.Queue, message: str) -> None:
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(message)


alerts = AlertBroadcaster()
