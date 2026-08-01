from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.auth.dependencies import AuthenticatedUser, get_current_user


@pytest.mark.anyio
async def test_missing_authorization_header_returns_401() -> None:
    with pytest.raises(HTTPException) as error:
        await get_current_user(None)

    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_invalid_supabase_token_returns_401() -> None:
    response = AsyncMock(status_code=401)
    client = AsyncMock()
    client.get.return_value = response

    with patch("app.auth.dependencies.httpx.AsyncClient") as client_type:
        client_type.return_value.__aenter__.return_value = client

        with pytest.raises(HTTPException) as error:
            await get_current_user("Bearer expired-token")

    assert error.value.status_code == 401
    client.get.assert_awaited_once()


@pytest.mark.anyio
async def test_valid_supabase_token_returns_current_user() -> None:
    response = AsyncMock(
        status_code=200,
        json=lambda: {
            "id": "d6f0a9c4-2a6e-4ed0-96ba-8c2603f8b9bb",
            "email": "analyst@example.com",
            "user_metadata": {"name": "Analyst"},
        },
    )
    client = AsyncMock()
    client.get.return_value = response

    with patch("app.auth.dependencies.httpx.AsyncClient") as client_type:
        client_type.return_value.__aenter__.return_value = client
        user = await get_current_user("Bearer valid-token")

    assert user == AuthenticatedUser(
        id="d6f0a9c4-2a6e-4ed0-96ba-8c2603f8b9bb",
        email="analyst@example.com",
        user_metadata={"name": "Analyst"},
    )
