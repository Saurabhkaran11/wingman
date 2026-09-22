"""One event stream per brief run, consumed by both the CLI and the web UI.

The agent's plugins (memory store, audit hook, steering policy) used to print
straight to stdout. They now emit structured events here instead, and each
front end decides what to do with them:

  CLI  -> add_callback(print_line)   prints as the run happens
  Web  -> subscribe()                a queue drained by a Server-Sent Events route

Only one brief runs at a time. Wingman is a single-user tool, and one run at a
time keeps the "which run is this event for?" question from existing at all.
"""

import threading
import time
import uuid
from collections import OrderedDict
from queue import Queue
from typing import Any, Callable

# Kinds a listener may receive. Keep this list in sync with the web UI's styling.
KINDS = ("step", "memory", "tool", "steering", "warn", "result", "error")

MAX_RUNS_KEPT = 20  # bounded so a long-lived server cannot grow without limit
_DONE = object()    # sentinel pushed to every queue when a run ends


class RunBusy(RuntimeError):
    """Raised when a brief is requested while another is still running."""


class Run:
    """One brief run: its events, its subscribers, and its outcome."""

    def __init__(self, run_id: str, title: str):
        self.id = run_id
        self.title = title
        self.started_at = time.time()
        self.finished_at: float | None = None
        self.state = "running"          # running | done | error
        self.result: dict[str, Any] = {}
        self.error: str | None = None
        self.events: list[dict] = []
        self._queues: list[Queue] = []
        self._callbacks: list[Callable[[dict], None]] = []
        self._lock = threading.Lock()

    # -- producing ---------------------------------------------------------

    def emit(self, kind: str, text: str, detail: str = "") -> dict:
        """Record one event and hand it to every listener.

        Example: run.emit("tool", "web_search", "1840 ms")
          -> {"seq": 3, "kind": "tool", "text": "web_search", "detail": "1840 ms", ...}
        """
        event = {
            "seq": len(self.events),
            "at": round(time.time() - self.started_at, 2),
            "kind": kind,
            "text": text,
            "detail": detail,
        }
        with self._lock:
            self.events.append(event)
            queues, callbacks = list(self._queues), list(self._callbacks)
        for queue in queues:
            queue.put(event)
        for callback in callbacks:
            # A broken listener must never take the run down with it.
            try:
                callback(event)
            except Exception:
                pass
        return event

    def finish(self, result: dict | None = None, error: str | None = None) -> None:
        """Close the run. Every subscriber's queue gets the end sentinel."""
        self.state = "error" if error else "done"
        self.error = error
        self.result = result or {}
        self.finished_at = time.time()
        if error:
            self.emit("error", error)
        with self._lock:
            queues = list(self._queues)
        for queue in queues:
            queue.put(_DONE)

    # -- consuming ---------------------------------------------------------

    def add_callback(self, callback: Callable[[dict], None]) -> None:
        """Call `callback` synchronously for each event. Used by the CLI."""
        with self._lock:
            self._callbacks.append(callback)

    def subscribe(self) -> Queue:
        """A queue seeded with the events so far, then fed live ones.

        Seeding with history means a browser that connects late, or reconnects,
        still sees the whole run rather than joining mid-way.
        """
        queue: Queue = Queue()
        with self._lock:
            for event in self.events:
                queue.put(event)
            if self.state != "running":
                queue.put(_DONE)
            else:
                self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: Queue) -> None:
        with self._lock:
            if queue in self._queues:
                self._queues.remove(queue)

    def summary(self) -> dict:
        """JSON-safe description of the run, for the web API."""
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state,
            "error": self.error,
            "result": self.result,
            "seconds": round((self.finished_at or time.time()) - self.started_at, 1),
            "events": self.events,
        }


# -- the registry ----------------------------------------------------------

_runs: "OrderedDict[str, Run]" = OrderedDict()
_active: Run | None = None
_registry_lock = threading.Lock()


def start(title: str) -> Run:
    """Begin a run, or raise RunBusy if one is already going.

    Example: start("Coffee with Priya Shah (Cognee)") -> Run(id="9f3c1a2b")
    """
    global _active
    with _registry_lock:
        if _active is not None and _active.state == "running":
            raise RunBusy(f"a brief is already running: {_active.title}")
        run = Run(uuid.uuid4().hex[:12], title)
        _active = run
        _runs[run.id] = run
        while len(_runs) > MAX_RUNS_KEPT:
            _runs.popitem(last=False)
        return run


def end(run: Run, result: dict | None = None, error: str | None = None) -> None:
    """Finish a run and release the slot, even when the run failed."""
    global _active
    run.finish(result=result, error=error)
    with _registry_lock:
        if _active is run:
            _active = None


def active() -> Run | None:
    with _registry_lock:
        return _active if _active is not None and _active.state == "running" else None


def get(run_id: str) -> Run | None:
    with _registry_lock:
        return _runs.get(run_id)


def emit(kind: str, text: str, detail: str = "") -> None:
    """Emit to whichever run is active. A no-op when nothing is running.

    This is what the plugins call, so they never have to carry a run around.
    """
    run = active()
    if run is not None:
        run.emit(kind, text, detail)


def is_done(event: Any) -> bool:
    """True for the end-of-run sentinel taken off a subscribed queue."""
    return event is _DONE
