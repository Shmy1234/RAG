from typing import Literal

from app.grounding.validator import GroundingError

Stage = Literal["routing", "searching", "analyzing", "validating", "saving"]

ErrorCode = Literal["retrieval_failed", "grounding_failed", "processing_failed"]

STAGE_ORDER: tuple[Stage, ...] = ("routing", "searching", "analyzing", "validating", "saving")


class RetrievalError(Exception):
    """Raised when the filing corpus could not be searched for a turn."""


def error_code_for(error: BaseException) -> ErrorCode:
    """Single mapping from a failed turn to the code the client sees.

    Both the persisted failure row and the streamed error part read from here so
    a reloaded thread shows the same failure the live stream did.
    """
    if isinstance(error, RetrievalError):
        return "retrieval_failed"
    if isinstance(error, GroundingError):
        return "grounding_failed"
    return "processing_failed"
