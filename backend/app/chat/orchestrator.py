from typing import Protocol
from uuid import UUID

from pydantic_ai.usage import UsageLimits

from app.assistant.agent import agent_usage_limits
from app.assistant.deps import DocumentAgentDeps, StageCallback, ignore_stage
from app.assistant.outputs import GroundedAnswer
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever


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


async def run_chat_turn(
    *,
    user_id: UUID,
    thread_id: UUID,
    user_text: str,
    store: ChatStoreLike,
    agent_runner: AgentRunner,
    retriever: DocumentRetriever,
    grounding_validator: GroundingValidator,
    on_stage: StageCallback | None = None,
) -> GroundedAnswer:
    report_stage = on_stage or ignore_stage
    await store.append_message(thread_id, "user", user_text, {"phase": 6})
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
    answer = result.output if hasattr(result, "output") else result
    await report_stage("validating")
    validated = grounding_validator.validate(
        answer,
        deps.retrieved_passages,
        evidence_candidates=deps.evidence_candidates,
    )
    citation_data = [citation.model_dump(mode="json") for citation in validated.citations]
    await report_stage("saving")
    await store.append_grounded_answer(
        thread_id,
        validated.answer,
        {"phase": 6, "citations": citation_data},
        citation_data,
    )
    return validated
