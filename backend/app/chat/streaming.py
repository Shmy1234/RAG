import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import structlog

from app.assistant.outputs import GroundedAnswer
from app.chat.routing import ChatRoute
from app.chat.stages import Stage, error_code_for

StageReporter = Callable[[Stage], Awaitable[None]]
AnswerReporter = Callable[[GroundedAnswer], Awaitable[None]]
RouteReporter = Callable[[ChatRoute], Awaitable[None]]
TurnRunner = Callable[[StageReporter, AnswerReporter, RouteReporter], Awaitable[GroundedAnswer]]
logger = structlog.get_logger(__name__)

# A browser that navigates away or closes mid-turn makes Starlette cancel this
# generator. asyncio holds only weak references to tasks, so without a strong
# reference here the orchestration would be collected mid-flight and the answer
# would never be persisted. Turns finish and save whether or not anyone is
# listening.
_running_turns: set[asyncio.Task[GroundedAnswer]] = set()


def _release_turn(task: asyncio.Task[GroundedAnswer]) -> None:
    _running_turns.discard(task)
    # A turn whose reader disconnected is never awaited. Retrieve the outcome so
    # a failure does not resurface as an unretrieved task exception at collection
    # time; connected turns are logged with their stage below, and every failure
    # is recorded against the thread by the orchestrator either way.
    if not task.cancelled():
        task.exception()


@dataclass(frozen=True)
class _Route:
    """Distinguishes a route update from the other queue payloads."""

    route: ChatRoute


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

    queue: asyncio.Queue[Stage | GroundedAnswer | _Route | None] = asyncio.Queue()
    current_stage: Stage | None = None
    answer_was_streamed = False

    async def report_stage(stage: Stage) -> None:
        nonlocal current_stage
        current_stage = stage
        await queue.put(stage)

    async def report_answer(answer: GroundedAnswer) -> None:
        await queue.put(answer)

    async def report_route(route: ChatRoute) -> None:
        await queue.put(_Route(route))

    async def runner() -> GroundedAnswer:
        try:
            return await run_turn(report_stage, report_answer, report_route)
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner())
    _running_turns.add(task)
    task.add_done_callback(_release_turn)
    yield _event({"type": "start", "messageId": "assistant-message"})

    while True:
        update = await queue.get()
        if update is None:
            break
        if isinstance(update, GroundedAnswer):
            answer_was_streamed = True
            async for event in _answer_content_events(update, chunk_size):
                yield event
            continue
        if isinstance(update, _Route):
            yield _event({"type": "data-route", "data": {"route": update.route}})
            continue
        yield _event({"type": "data-status", "data": {"stage": update}})

    try:
        answer = await task
    except Exception as error:  # Fail closed: the stream is already open, so
        # every failure must become a typed code rather than a dropped
        # connection. Covers usage limits, agent errors, and persistence alike;
        # the traceback stays server-side.
        code = error_code_for(error)
        logger.exception("chat_turn_failed", error_code=code, stage=current_stage)
    else:
        if answer_was_streamed:
            yield _event({"type": "finish", "finishReason": "stop"})
        else:
            async for event in _answer_events(answer, chunk_size):
                yield event
        return

    # Only the code crosses the wire — exception text never reaches the browser.
    yield _event({"type": "data-error", "data": {"code": code}})
    yield _event({"type": "finish", "finishReason": "error"})


async def _answer_events(answer: GroundedAnswer, chunk_size: int) -> AsyncIterator[str]:
    async for event in _answer_content_events(answer, chunk_size):
        yield event
    yield _event({"type": "finish", "finishReason": "stop"})


async def _answer_content_events(answer: GroundedAnswer, chunk_size: int) -> AsyncIterator[str]:
    yield _event({"type": "text-start", "id": "text-1"})
    for start in range(0, len(answer.answer), chunk_size):
        chunk = answer.answer[start : start + chunk_size]
        yield _event({"type": "text-delta", "id": "text-1", "delta": chunk})

    citation_data = [citation.model_dump(mode="json") for citation in answer.citations]
    yield _event({"type": "text-end", "id": "text-1"})
    yield _event({"type": "data-citations", "data": citation_data})


def _event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
