import asyncio

import pytest

from app.services.multi_agent.messages import PeerResponse
from app.services.multi_agent.peer_guard import PeerGuard


@pytest.mark.asyncio
async def test_inbound_serialized_fifo() -> None:
    guard = PeerGuard()
    order: list[int] = []

    async def handler(n: int) -> PeerResponse:
        order.append(n)
        await asyncio.sleep(0.05)
        return PeerResponse(
            answer=str(n),
            request_id=str(n),
            from_server="srv",
            ok=True,
        )

    async def run(n: int) -> PeerResponse:
        return await guard.run_inbound_exclusive("a", lambda: handler(n))

    await asyncio.gather(run(1), run(2))
    assert order == [1, 2]


@pytest.mark.asyncio
async def test_outbound_queued_while_inbound_active() -> None:
    guard = PeerGuard()
    guard.inbound_active["a"] = True
    ran: list[str] = []

    async def _out() -> str:
        ran.append("done")
        return "peer-answer"

    fut = guard.enqueue_outbound(
        "a",
        to_server="b-server",
        question="what soils?",
        run=_out,
    )
    assert guard.outbound_queue_depth("a") == 1
    assert not ran

    guard.inbound_active.pop("a", None)
    await guard._drain_outbound_queue("a")

    assert await fut == "peer-answer"
    assert ran == ["done"]


@pytest.mark.asyncio
async def test_outbound_serialized_when_in_flight() -> None:
    guard = PeerGuard()
    guard.outbound_in_flight["a"] = True
    order: list[int] = []

    async def run(n: int) -> str:
        async def _job() -> str:
            order.append(n)
            await asyncio.sleep(0.02)
            return str(n)

        if guard.should_queue_outbound("a"):
            fut = guard.enqueue_outbound(
                "a",
                to_server="b",
                question=str(n),
                run=_job,
            )
            return await fut
        return await guard.run_outbound("a", _job)

    guard.outbound_in_flight.pop("a", None)
    t1 = asyncio.create_task(run(1))
    await asyncio.sleep(0.005)
    guard.outbound_in_flight["a"] = True
    t2 = asyncio.create_task(run(2))
    await asyncio.sleep(0.005)
    guard.outbound_in_flight.pop("a", None)
    await guard._drain_outbound_queue("a")
    r1, r2 = await asyncio.gather(t1, t2)
    assert set([r1, r2]) == {"1", "2"}
    assert order == [1, 2]
