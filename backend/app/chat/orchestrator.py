from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Protocol
from uuid import UUID

import structlog
from pydantic_ai.usage import UsageLimits

from app.assistant.agent import agent_usage_limits
from app.assistant.deps import DocumentAgentDeps, StageCallback, ignore_stage
from app.assistant.outputs import GroundedAnswer
from app.chat.routing import RouteDecision
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever

logger = structlog.get_logger(__name__)
AnswerCallback = Callable[[GroundedAnswer], Awaitable[None]]


class ChatStoreLike(Protocol):
    async def append_message(
        self,
        thread_id: UUID,
        role: str,
        content: str,
        message_data: dict[str, object],
    ) -> dict[str, object]: ...

    async def append_grounded_answer(
        self,
        thread_id: UUID,
        content: str,
        message_data: dict[str, object],
        citations: list[dict[str, object]],
    ) -> dict[str, object]: ...


class AgentRunner(Protocol):
    async def run(
        self,
        prompt: str,
        *,
        deps: DocumentAgentDeps,
        usage_limits: UsageLimits,
    ): ...


class RouterLike(Protocol):
    async def route(self, prompt: str) -> RouteDecision: ...


class QuickRagRunnerLike(Protocol):
    async def run(
        self,
        prompt: str,
        *,
        retriever: DocumentRetriever,
        grounding_validator: GroundingValidator,
        on_stage: StageCallback,
    ) -> GroundedAnswer: ...


async def run_chat_turn(
    *,
    user_id: UUID,
    thread_id: UUID,
    user_text: str,
    store: ChatStoreLike,
    router: RouterLike,
    quick_rag_runner: QuickRagRunnerLike,
    agent_runner: AgentRunner,
    retriever: DocumentRetriever,
    grounding_validator: GroundingValidator,
    on_stage: StageCallback | None = None,
    on_answer_ready: AnswerCallback | None = None,
    clock: Callable[[], float] = monotonic,
) -> GroundedAnswer:
    report_stage = on_stage or ignore_stage
    await store.append_message(thread_id, "user", user_text, {"phase": 8})

    await report_stage("routing")
    routing_started = clock()
    decision = await router.route(user_text)
    routing_ms = _elapsed_ms(routing_started, clock())

    execution_started = clock()
    answer = await _execute_route(
        decision=decision,
        user_id=user_id,
        thread_id=thread_id,
        user_text=user_text,
        quick_rag_runner=quick_rag_runner,
        agent_runner=agent_runner,
        retriever=retriever,
        grounding_validator=grounding_validator,
        report_stage=report_stage,
    )
    execution_ms = _elapsed_ms(execution_started, clock())

    if decision.route == "instant" and on_answer_ready is not None:
        await on_answer_ready(answer)

    citation_data = [citation.model_dump(mode="json") for citation in answer.citations]
    message_data: dict[str, object] = {
        "phase": 8,
        "route": decision.route,
        "routing_ms": routing_ms,
        "execution_ms": execution_ms,
        "citations": citation_data,
    }
    await report_stage("saving")
    await store.append_grounded_answer(
        thread_id,
        answer.answer,
        message_data,
        citation_data,
    )
    logger.info(
        "chat_turn_completed",
        route=decision.route,
        routing_ms=routing_ms,
        execution_ms=execution_ms,
    )
    return answer


async def _execute_route(
    *,
    decision: RouteDecision,
    user_id: UUID,
    thread_id: UUID,
    user_text: str,
    quick_rag_runner: QuickRagRunnerLike,
    agent_runner: AgentRunner,
    retriever: DocumentRetriever,
    grounding_validator: GroundingValidator,
    report_stage: StageCallback,
) -> GroundedAnswer:
    if decision.route in {"instant", "direct"}:
        if decision.answer is None:
            raise ValueError("non-RAG route is missing its answer")
        return GroundedAnswer(answer=decision.answer)

    if decision.route == "quick_rag":
        return await quick_rag_runner.run(
            user_text,
            retriever=retriever,
            grounding_validator=grounding_validator,
            on_stage=report_stage,
        )

    deps = DocumentAgentDeps(
        user_id=user_id,
        thread_id=thread_id,
        retriever=retriever,
        grounding_validator=grounding_validator,
        on_stage=report_stage,
    )
    await report_stage("searching")
    result = await agent_runner.run(
        user_text,
        deps=deps,
        usage_limits=agent_usage_limits(),
    )
    raw_answer = result.output if hasattr(result, "output") else result
    await report_stage("validating")
    return grounding_validator.validate(
        raw_answer,
        deps.retrieved_passages,
        evidence_candidates=deps.evidence_candidates,
    )


def _elapsed_ms(started: float, finished: float) -> int:
    return max(0, round((finished - started) * 1000))
