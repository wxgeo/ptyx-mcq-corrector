"""
Priority-aware background document generation for a PyQt6 app.

Key idea
--------
multiprocessing.Queue is a one-way pipe: once a task is inside it you
cannot reorder or remove it. So we DON'T queue everything into the
mp.Queue up front. Instead:

  * A thread-safe deque ("TaskQueue") lives in the main process and holds
    every task that hasn't started yet: appendleft() for urgent requests,
    append() for background work.
  * A dispatcher thread only pushes ONE task into the real mp.Queue per
    free worker "slot" (tracked with a Semaphore). That means at most
    `num_workers` tasks are ever un-reorderable at a time; everything
    else can still be bumped to the front.
  * Calling `.generate(doc_id, payload, prioritize=True)` from the GUI
    thread just pushes the request to the front of the queue (O(1)) --
    safe to call directly from a Qt slot, no need for a QThread wrapper.
  * Results come back on another thread and are published to Qt via a
    pyqtSignal, which Qt automatically marshals to the GUI thread.

Usage sketch is at the bottom of this file.
"""

from __future__ import annotations

import collections
import multiprocessing as mp
import queue
import threading
from typing import Any, Callable, Dict, Optional, Set, Literal, TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from ptyx_mcq.tools.parse_config.subtypes import DocumentId

if TYPE_CHECKING:
    TaskQueueType = mp.Queue[tuple[DocumentId, dict] | None]
    ResultQueueType = mp.Queue[tuple[Literal["ok", "error"], DocumentId, Any]]


# --------------------------------------------------------------------------
# 1. Thread-safe task queue (lives in the main process)
# --------------------------------------------------------------------------
#
# Just a deque: appendleft() for urgent requests, append() for background
# work. Duplicates are allowed (e.g. a doc requested, then re-requested
# urgently before it started) -- they're cheap to carry around and are
# filtered out at dispatch time (see _dispatch_loop) instead of here.


class TaskQueue:
    def __init__(self) -> None:
        # Tasks to do: document id and the payload (a dict to be passed as argument to the function).
        self._queue: "collections.deque[tuple[DocumentId, Any]]" = collections.deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._closed = False

    def push(self, doc_id: DocumentId, payload: Any, urgent: bool = False) -> None:
        with self._not_empty:
            if urgent:
                self._queue.appendleft((doc_id, payload))
            else:
                self._queue.append((doc_id, payload))
            self._not_empty.notify()

    def pop(self, timeout: Optional[float] = None):
        """Blocks until an item is available or the queue is closed."""
        with self._not_empty:
            while True:
                if self._queue:
                    return self._queue.popleft()
                if self._closed:
                    return None
                if not self._not_empty.wait(timeout):
                    return None

    def close(self) -> None:
        with self._not_empty:
            self._closed = True
            self._not_empty.notify_all()

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)


# --------------------------------------------------------------------------
# 2. Worker process body
# --------------------------------------------------------------------------


def _worker_main(
    task_queue: "TaskQueueType",
    result_queue: "ResultQueueType",
    generate_fn: Callable,
) -> None:
    """
    Runs in a separate OS process. `generate_fn` must be a module-level
    (picklable) callable: payload -> generated_document.
    """
    while True:
        item = task_queue.get()
        if item is None:  # sentinel -> shut this worker down
            break
        doc_id, payload = item
        try:
            result = generate_fn(payload)
            result_queue.put(("ok", doc_id, result))
        except Exception as exc:  # noqa: BLE001 - report, don't crash worker
            result_queue.put(("error", doc_id, repr(exc)))


# --------------------------------------------------------------------------
# 3. The pool itself, exposed as a QObject so it can emit Qt signals
# --------------------------------------------------------------------------


class DocumentGeneratorPool(QObject):
    """
    Public API, safe to call from the GUI thread:

        pool.generate(doc_id, payload)                    # queue in the background
        pool.generate(doc_id, payload, prioritize=True)    # jump the queue

    Results arrive via the `document_ready` / `document_failed` signals.
    """

    document_ready = pyqtSignal(int, object)  # DocumentId, function result
    document_failed = pyqtSignal(int, str)  # DocumentId, stringified error

    def __init__(self, generate_fn: Callable, num_workers: Optional[int] = None, parent=None):
        super().__init__(parent)
        self._num_workers = num_workers or max(1, (mp.cpu_count() or 2) - 1)

        # This is the supply chain.
        # It lives in the main process, but will be accessed from several threads, so it has to be thread-safe.
        self._pending = TaskQueue()
        # This is the line of production, used to send data to the workers living in other processes.
        # mp.Queue is fine here: at any moment it holds at most
        # `num_workers` un-started tasks (enforced by the semaphore below),
        # so we never need to reorder *it* -- only the heap in front of it.
        self._task_queue: "TaskQueueType" = mp.Queue()
        # Of course, it's nice to have some information back too.
        self._result_queue: "ResultQueueType" = mp.Queue()

        self._cache: Dict[DocumentId, Any] = {}
        self._active: Set[DocumentId] = set()  # doc_ids currently assigned to a worker
        self._state_lock = threading.Lock()

        # The number of currently available workers.
        # Use a Semaphore: if no worker is currently free, you must wait.
        # Bound it, to be sure to not release accidentally more workers that available!
        self._slot_semaphore = threading.BoundedSemaphore(self._num_workers)

        self._workers = [
            mp.Process(
                target=_worker_main,
                args=(self._task_queue, self._result_queue, generate_fn),
                daemon=True,
            )
            for _ in range(self._num_workers)
        ]
        for w in self._workers:
            w.start()

        self._stopping = False
        self._dispatcher_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._dispatcher_thread.start()
        self._listener_thread.start()

    # -- public API --------------------------------------------------------

    def generate(self, doc_id: DocumentId, payload: Any, prioritize: bool = False) -> None:
        """
        Request a document. Cheap and non-blocking; safe from the GUI
        thread. Call with prioritize=True when the user just asked for
        this doc_id right now, to jump it to the front of the queue.
        """
        with self._state_lock:
            if doc_id in self._cache:
                self.document_ready.emit(doc_id, self._cache[doc_id])
                return

        # No dedup here: if this doc_id is already queued or being
        # generated, this just adds a harmless extra entry -- it'll be
        # skipped in _dispatch_loop once the real one is found to be
        # cached or already active.
        self._pending.push(doc_id, payload, urgent=prioritize)

    def shutdown(self) -> None:
        """
        Close all pending tasks, then end the treads.
        """
        self._stopping = True
        self._pending.close()
        for _ in self._workers:
            self._task_queue.put(None)
        for w in self._workers:
            w.join(timeout=5)

    # -- internal threads ---------------------------------------------------

    def _dispatch_loop(self) -> None:
        while not self._stopping:
            self._slot_semaphore.acquire()
            item = self._pending.pop()
            if item is None:  # queue closed during shutdown
                self._slot_semaphore.release()
                return
            doc_id, payload = item
            with self._state_lock:
                if doc_id in self._cache or doc_id in self._active:
                    # Stale duplicate (already done, or another copy of
                    # this doc_id is already running on a worker): don't
                    # waste a worker on it, just release the slot back.
                    self._slot_semaphore.release()
                    continue
                self._active.add(doc_id)
            self._task_queue.put((doc_id, payload))

    def _listen_loop(self) -> None:
        while not self._stopping:
            try:
                status, doc_id, value = self._result_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            self._slot_semaphore.release()
            with self._state_lock:
                self._active.discard(doc_id)
                if status == "ok":
                    self._cache[doc_id] = value
            if status == "ok":
                self.document_ready.emit(doc_id, value)
            else:
                self.document_failed.emit(doc_id, str(value))

    def reset_cache(self) -> None:
        """To be able to regenerate documents."""
        self._cache.clear()
