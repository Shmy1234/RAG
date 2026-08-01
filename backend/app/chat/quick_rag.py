import json
from typing import Protocol

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from app.assistant.outputs import AgentAnswer, GroundedAnswer
from app.chat.stages import RetrievalError
from app.config import settings
from app.grounding.evidence import build_evidence_candidates
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever

INSUFFICIENT_EVIDENCE_ANSWER = "The corpus does not contain enough evidence to answer that question."

QUICK_RAG_INSTRUCTIONS = """Answer the question only from the supplied evidence candidates.
Return concise text and select the evidence ids whose exact quotes support every factual sentence.
Never invent facts, figures, dates, calculations, or citations. If the candidates are insufficient,
say the corpus does not contain enough evidence and return no citations. Do not put citation notation
or evidence ids in the answer text.
"""


class QuickAnswerRunner(Protocol):
    async def run(self, prompt: str, *, usage_limits: UsageLimits): ...


_fast_model = OpenAIChatModel(
    settings.OPENAI_FAST_MODEL.removeprefix("openai:"),
    provider=OpenAIProvider(api_key=settings.OPENAI_API_KEY),
)

quick_answer_agent = Agent(
    _fast_model,
    output_type=AgentAnswer,
    instructions=QUICK_RAG_INSTRUCTIONS,
    retries=0,
)


class QuickRagRunner:
    def __init__(self, answer_runner: QuickAnswerRunner = quick_answer_agent) -> None:
        self._answer_runner = answer_runner

    async def run(
        self,
        prompt: str,
        *,
        retriever: DocumentRetriever,
        grounding_validator: GroundingValidator,
    ) -> GroundedAnswer:
        try:
            passages = await retriever.retrieve(prompt, top_k=5, candidate_k=50)
        except Exception as error:
            raise RetrievalError("filing search failed") from error

        candidates = build_evidence_candidates(passages, prompt)
        if not candidates:
            return GroundedAnswer(answer=INSUFFICIENT_EVIDENCE_ANSWER)

        payload = {
            "question": prompt,
            "evidence": [candidate.model_dump(mode="json") for candidate in candidates],
        }
        result = await self._answer_runner.run(
            json.dumps(payload),
            usage_limits=UsageLimits(request_limit=1),
        )
        evidence_index = {candidate.evidence_id: candidate for candidate in candidates}
        return grounding_validator.validate(
            result.output,
            passages,
            evidence_candidates=evidence_index,
        )
