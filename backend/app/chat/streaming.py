import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

from app.assistant.outputs import GroundedAnswer
from app.chat.stages import ErrorCode, RetrievalError, Stage
from app.grounding.validator import GroundingError

TurnRunner = Callable[[Callable[[Stage], Awaitable[None]]], Awaitable[GroundedAnswer]]


async def stream_grounded_answer(
    answer: GroundedAnswer,
    *,
    chunk_size: int = 80,
) -> AsyncIterator[str]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")

    yield _event({"type": "start", "messageId": "assistant-message"})
    async for event in _answer_events(answer, chunk_size):
        yield event


async def stream_chat_turn(
    run_turn: TurnRunner,
    *,
    chunk_size: int = 80,
) -> AsyncIterator[str]:
    """Run one turn inside the response stream so status reflects real progress.

    Orchestration runs as a task that pushes stage identifiers onto a queue; this
    generator drains the queue as they arrive, so a status event is only emitted
    once its work has actually started.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")

    queue: asyncio.Queue[Stage | None] = asyncio.Queue()

    async def runner() -> GroundedAnswer:
        try:
            return await run_turn(queue.put)
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())
    yield _event({"type": "start", "messageId": "assistant-message"})

    while True:
        stage = await queue.get()
        if stage is None:
            break
        yield _event({"type": "data-status", "data": {"stage": stage}})

    code: ErrorCode
    try:
        answer = await task
    except RetrievalError:
        code = "retrieval_failed"
    except GroundingError:
        code = "grounding_failed"
    except Exception:  # noqa: BLE001 - fail closed: the stream is already open, so
        # every remaining failure must become a typed code rather than a dropped
        # connection. Covers usage limits, agent errors, and persistence alike;
        # the traceback stays server-side.
        code = "processing_failed"
    else:
        async for event in _answer_events(answer, chunk_size):
            yield event
        return

    # Only the code crosses the wire — exception text never reaches the browser.
    yield _event({"type": "data-error", "data": {"code": code}})
    yield _event({"type": "finish", "finishReason": "error"})


async def _answer_events(answer: GroundedAnswer, chunk_size: int) -> AsyncIterator[str]:
    yield _event({"type": "text-start", "id": "text-1"})
    for start in range(0, len(answer.answer), chunk_size):
        chunk = answer.answer[start : start + chunk_size]
        yield _event({"type": "text-delta", "id": "text-1", "delta": chunk})

    citation_data = [citation.model_dump(mode="json") for citation in answer.citations]
    yield _event({"type": "text-end", "id": "text-1"})
    yield _event({"type": "data-citations", "data": citation_data})
    yield _event({"type": "finish", "finishReason": "stop"})


def _event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
