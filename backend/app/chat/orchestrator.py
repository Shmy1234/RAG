from typing import Protocol
from uuid import UUID

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.schemas import SourcePassage


class ChatStoreLike(Protocol):
    async def append_message(
        self,
        thread_id: UUID,
        role: str,
        content: str,
        message_data: dict[str, object],
    ) -> dict[str, object]: ...

    async def append_citations(
        self,
        message_id: str,
        citations: list[dict[str, object]],
    ) -> None: ...


class AgentRunner(Protocol):
    async def run(self, prompt: str, *, deps: DocumentAgentDeps): ...


async def run_chat_turn(
    *,
    user_id: UUID,
    thread_id: UUID,
    user_text: str,
    store: ChatStoreLike,
    agent_runner: AgentRunner,
    retriever: DocumentRetriever,
    grounding_validator: GroundingValidator,
) -> GroundedAnswer:
    await store.append_message(thread_id, "user", user_text, {"phase": 6})
    passages: list[SourcePassage] = await retriever.retrieve(user_text, top_k=5, candidate_k=50)
    deps = DocumentAgentDeps(
        user_id=user_id,
        thread_id=thread_id,
        retriever=retriever,
        grounding_validator=grounding_validator,
        retrieved_passages=passages,
    )
    result = await agent_runner.run(user_text, deps=deps)
    answer = result.output if hasattr(result, "output") else result
    validated = grounding_validator.validate(answer, deps.retrieved_passages)
    citation_data = [citation.model_dump(mode="json") for citation in validated.citations]
    assistant_message = await store.append_message(
        thread_id,
        "assistant",
        validated.answer,
        {"phase": 6, "citations": citation_data},
    )
    await store.append_citations(str(assistant_message["id"]), citation_data)
    return validated
