import re
from typing import Literal, Protocol

from pydantic import BaseModel, model_validator
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from app.config import settings

ChatRoute = Literal["instant", "direct", "quick_rag", "deep_rag"]
ModelChatRoute = Literal["direct", "quick_rag", "deep_rag"]

ROUTING_INSTRUCTIONS = """You route requests for an SEC filing research assistant.

Choose direct only for guidance about how to use this product and its filing-research features.
When choosing direct, provide the concise final answer in the answer field.

Choose quick_rag for a focused company or filing question likely answerable with one corpus search.
Choose deep_rag for comparisons, multi-part synthesis, longitudinal analysis, broad summaries, or
questions likely to require multiple searches or surrounding context.

Never choose direct for company, filing, business, financial, dated, comparative, source,
verification, or citation facts. Ambiguous factual requests must use quick_rag or deep_rag.
RAG routes must leave the answer field empty.
"""

_TRAILING_PUNCTUATION = re.compile(r"[.!?]+$")
_SAFE_DIRECT_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        (
            r"^(?:what can you (?:do|help me (?:do|with))|what do you do|"
            r"how can you help(?: me)?|how do i use (?:this|the) (?:app|workspace)|"
            r"help me use (?:this|the) (?:app|workspace))\??$"
        ),
    )
)
_INSTANT_RESPONSES = {
    "hi": "Hi! How can I help with your filing research?",
    "hello": "Hello! How can I help with your filing research?",
    "hey": "Hey! How can I help with your filing research?",
    "thanks": "You're welcome!",
    "thank you": "You're welcome!",
}


class RouteDecision(BaseModel):
    route: ChatRoute
    answer: str | None = None

    @model_validator(mode="after")
    def require_route_appropriate_answer(self) -> "RouteDecision":
        has_answer = bool(self.answer and self.answer.strip())
        if self.route in {"instant", "direct"} and not has_answer:
            raise ValueError("instant and direct routes require an answer")
        if self.route in {"quick_rag", "deep_rag"} and has_answer:
            raise ValueError("RAG routes must not include an answer")
        return self


class ModelRouteDecision(BaseModel):
    route: ModelChatRoute
    answer: str | None = None

    @model_validator(mode="after")
    def require_route_appropriate_answer(self) -> "ModelRouteDecision":
        has_answer = bool(self.answer and self.answer.strip())
        if self.route == "direct" and not has_answer:
            raise ValueError("direct routes require an answer")
        if self.route in {"quick_rag", "deep_rag"} and has_answer:
            raise ValueError("RAG routes must not include an answer")
        return self


class RouteRunner(Protocol):
    async def run(self, prompt: str, *, usage_limits: UsageLimits): ...


_fast_model = OpenAIChatModel(
    settings.OPENAI_FAST_MODEL.removeprefix("openai:"),
    provider=OpenAIProvider(api_key=settings.OPENAI_API_KEY),
)

route_agent = Agent(
    _fast_model,
    output_type=ModelRouteDecision,
    instructions=ROUTING_INSTRUCTIONS,
    retries=1,
)


def instant_response(prompt: str) -> str | None:
    normalized = " ".join(prompt.split()).casefold()
    normalized = _TRAILING_PUNCTUATION.sub("", normalized).strip()
    return _INSTANT_RESPONSES.get(normalized)


def direct_response_allowed(prompt: str) -> bool:
    normalized = " ".join(prompt.split()).casefold()
    return any(pattern.match(normalized) for pattern in _SAFE_DIRECT_PATTERNS)


class ChatRouter:
    def __init__(self, runner: RouteRunner = route_agent) -> None:
        self._runner = runner

    async def route(self, prompt: str) -> RouteDecision:
        response = instant_response(prompt)
        if response is not None:
            return RouteDecision(route="instant", answer=response)

        result = await self._runner.run(prompt, usage_limits=UsageLimits(request_limit=1))
        decision = result.output
        if decision.route == "direct" and not direct_response_allowed(prompt):
            return RouteDecision(route="quick_rag")
        return RouteDecision(route=decision.route, answer=decision.answer)
