from unittest.mock import Mock, patch

from app.database.supabase import create_service_role_client, create_user_client


def test_create_service_role_client_uses_service_role_key() -> None:
    client = Mock()

    with patch("app.database.supabase.create_client", return_value=client) as factory:
        result = create_service_role_client()

    factory.assert_called_once_with(
        "https://project.supabase.co",
        "service-role-key",
    )
    assert result is client


def test_create_user_client_scopes_postgrest_to_access_token() -> None:
    client = Mock()

    with patch("app.database.supabase.create_client", return_value=client) as factory:
        result = create_user_client("user-access-token")

    factory.assert_called_once_with(
        "https://project.supabase.co",
        "anon-key",
    )
    client.postgrest.auth.assert_called_once_with("user-access-token")
    assert result is client
