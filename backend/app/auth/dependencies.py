from uuid import UUID

import httpx
from fastapi import Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    email: str | None = None
    user_metadata: dict[str, object] = Field(default_factory=dict)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise _unauthorized()

    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise _unauthorized()
    return token.strip()


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    """Verify a Supabase JWT and return the authenticated user."""
    token = _bearer_token(authorization)
    headers = {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{settings.SUPABASE_URL}/auth/v1/user", headers=headers)

    if response.status_code != status.HTTP_200_OK:
        raise _unauthorized()

    try:
        return AuthenticatedUser.model_validate(response.json())
    except (TypeError, ValueError):
        raise _unauthorized() from None
