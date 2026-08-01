from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.retrieval.retriever import DocumentRetriever
from app.retrieval.schemas import SourcePassage


class GroundingValidator(Protocol):
    def validate(self, answer, passages: Sequence[SourcePassage]):
        """Validate an answer against the current retrieved passages."""


class DocumentAgentDeps:
    def __init__(
        self,
        *,
        user_id: UUID,
        thread_id: UUID,
        retriever: DocumentRetriever,
        grounding_validator: GroundingValidator,
        retrieved_passages: list[SourcePassage] | None = None,
    ) -> None:
        self.user_id = user_id
        self.thread_id = thread_id
        self.retriever = retriever
        self.grounding_validator = grounding_validator
        self.retrieved_passages = retrieved_passages or []
