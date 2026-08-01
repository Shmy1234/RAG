from pathlib import Path
from uuid import UUID

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import UsageLimits

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import AgentAnswer
from app.chat.stages import RetrievalError
from app.config import settings
from app.grounding.evidence import EvidenceCandidate
from app.grounding.validator import GroundingError

_instructions = Path(__file__).with_name("instructions.md").read_text()

_chat_model = OpenAIChatModel(
    settings.OPENAI_CHAT_MODEL.removeprefix("openai:"),
    provider=OpenAIProvider(api_key=settings.OPENAI_API_KEY),
)

document_agent = Agent(
    _chat_model,
    deps_type=DocumentAgentDeps,
    output_type=AgentAnswer,
    instructions=_instructions,
    retries=1,
)


def agent_usage_limits() -> UsageLimits:
    return UsageLimits(request_limit=4, tool_calls_limit=6)


def prepare_retrieval_tool(
    ctx: RunContext[DocumentAgentDeps],
    tool_definition: ToolDefinition,
) -> ToolDefinition | None:
    if not ctx.deps.retrieval_completed:
        return tool_definition
    return None


@document_agent.tool(prepare=prepare_retrieval_tool)
async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    top_k: int = 5,
) -> list[EvidenceCandidate] | str:
    if top_k < 1:
        raise ValueError("top_k must be greater than zero")
    effective_top_k = min(top_k, 10)
    cache_key = (" ".join(query.split()).casefold(), effective_top_k)
    candidates = ctx.deps.search_cache.get(cache_key)
    if candidates is None:
        try:
            passages = await ctx.deps.retriever.retrieve(
                query,
                top_k=effective_top_k,
                candidate_k=50,
                filters=ctx.deps.retrieval_filters,
            )
        except Exception as error:
            # Embeddings and pgvector are external boundaries; surface a typed
            # failure so the stream can report retrieval rather than processing.
            raise RetrievalError("filing search failed") from error
        ctx.deps.add_passages(passages)
        candidates = ctx.deps.register_passage_evidence(passages, query)
        ctx.deps.search_cache[cache_key] = candidates
    ctx.deps.retrieval_completed = True
    await ctx.deps.on_stage("analyzing")
    if not candidates:
        return "No matching filing passages were found. Stop searching and report insufficient evidence."
    return candidates


@document_agent.tool(prepare=prepare_retrieval_tool)
async def read_chunk(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: UUID,
) -> list[EvidenceCandidate] | str:
    chunk = await ctx.deps.retriever.read_chunk(chunk_id)
    if chunk is None:
        return "No chunk was found for that id."
    candidates = ctx.deps.register_chunk_evidence([chunk])
    return candidates or "The chunk did not contain evidence matching the current question."


@document_agent.tool(prepare=prepare_retrieval_tool)
async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: UUID,
    window: int = 1,
) -> list[EvidenceCandidate] | str:
    if window < 0 or window > 3:
        raise ValueError("window must be between 0 and 3")
    result = await ctx.deps.retriever.read_surrounding_chunks(chunk_id, window=window)
    if result is None:
        return "No chunk was found for that id."
    center = await ctx.deps.retriever.read_chunk(chunk_id)
    chunks = result["previous_chunks"] + result["next_chunks"]
    if center is not None:
        chunks.insert(0, center)
    candidates = ctx.deps.register_chunk_evidence(chunks)
    return candidates or "The surrounding chunks did not contain evidence matching the current question."


@document_agent.output_validator
def validate_grounded_output(ctx: RunContext[DocumentAgentDeps], output: AgentAnswer) -> AgentAnswer:
    try:
        ctx.deps.grounding_validator.validate(
            output,
            ctx.deps.retrieved_passages,
            evidence_candidates=ctx.deps.evidence_candidates,
        )
    except GroundingError as error:
        raise ModelRetry(str(error)) from error
    return output
