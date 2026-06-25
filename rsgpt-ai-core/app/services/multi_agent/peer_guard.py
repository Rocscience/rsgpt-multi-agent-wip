"""Peer messaging: serialize inbound answers and queue outbound questions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from app.services.multi_agent.messages import PeerQuery, PeerResponse

# Peer answers must not chain into further peer calls (enforced in specialist LLM phase).
MAX_PEER_DEPTH = 0


@dataclass
class _OutboundJob:
    """Outbound peer RPC waiting for this specialist to be free."""

    to_server: str
    question: str
    future: asyncio.Future[str]
    run: Callable[[], Awaitable[str]]


@dataclass
class PeerGuard:
    """
    Per-specialist peer messaging.

    **Inbound** (another agent asks us): handled one at a time via ``asyncio.Lock``.
    Additional ``PeerQuery`` messages wait in the lock queue and are answered FIFO.

    **Outbound** (we ask another agent): if we are answering an inbound query or already
    waiting on an outbound RPC, the new question is appended to ``outbound_queues`` and
    processed after the current inbound/outbound work finishes.
    """

    inbound_active: dict[str, bool] = field(default_factory=dict)
    outbound_in_flight: dict[str, bool] = field(default_factory=dict)
    _inbound_locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    _outbound_queues: dict[str, list[_OutboundJob]] = field(default_factory=dict)
    _outbound_drain_locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    def _inbound_lock(self, server_id: str) -> asyncio.Lock:
        if server_id not in self._inbound_locks:
            self._inbound_locks[server_id] = asyncio.Lock()
        return self._inbound_locks[server_id]

    def _outbound_drain_lock(self, server_id: str) -> asyncio.Lock:
        if server_id not in self._outbound_drain_locks:
            self._outbound_drain_locks[server_id] = asyncio.Lock()
        return self._outbound_drain_locks[server_id]

    async def run_inbound_exclusive(
        self,
        server_id: str,
        handler: Callable[[], Awaitable[PeerResponse]],
        *,
        on_wait: Callable[[], None] | None = None,
    ) -> PeerResponse:
        """Run one inbound peer handler; concurrent callers wait on the lock (FIFO)."""
        lock = self._inbound_lock(server_id)
        if lock.locked() and on_wait:
            on_wait()
        async with lock:
            self.inbound_active[server_id] = True
            try:
                return await handler()
            finally:
                self.inbound_active.pop(server_id, None)
                await self._drain_outbound_queue(server_id)

    def should_queue_outbound(self, server_id: str) -> bool:
        return bool(
            self.inbound_active.get(server_id) or self.outbound_in_flight.get(server_id)
        )

    def enqueue_outbound(
        self,
        server_id: str,
        *,
        to_server: str,
        question: str,
        run: Callable[[], Awaitable[str]],
    ) -> asyncio.Future[str]:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        self._outbound_queues.setdefault(server_id, []).append(
            _OutboundJob(to_server=to_server, question=question, future=fut, run=run)
        )
        return fut

    async def run_outbound(
        self,
        server_id: str,
        run: Callable[[], Awaitable[str]],
        *,
        queue_if_busy: bool = True,
    ) -> str:
        """
        Execute an outbound peer RPC, or queue it if this specialist is busy.

        Returns the peer's answer text (same as before for ``request_peer`` callers).
        """
        if queue_if_busy and self.should_queue_outbound(server_id):
            fut = self.enqueue_outbound(
                server_id, to_server="", question="", run=run
            )
            # to_server/question filled by caller via activity on enqueue path in specialist
            return await fut

        self.outbound_in_flight[server_id] = True
        try:
            return await run()
        finally:
            self.outbound_in_flight.pop(server_id, None)
            await self._drain_outbound_queue(server_id)

    async def _drain_outbound_queue(self, server_id: str) -> None:
        """Process queued outbound peer questions one at a time."""
        async with self._outbound_drain_lock(server_id):
            while True:
                queue = self._outbound_queues.get(server_id)
                if not queue:
                    return
                if self.outbound_in_flight.get(server_id) or self.inbound_active.get(server_id):
                    return
                job = queue.pop(0)
                if not queue:
                    self._outbound_queues.pop(server_id, None)

                self.outbound_in_flight[server_id] = True
                try:
                    result = await job.run()
                    if not job.future.done():
                        job.future.set_result(result)
                except Exception as e:
                    if not job.future.done():
                        job.future.set_exception(e)
                finally:
                    self.outbound_in_flight.pop(server_id, None)

    def outbound_queue_depth(self, server_id: str) -> int:
        return len(self._outbound_queues.get(server_id, ()))
