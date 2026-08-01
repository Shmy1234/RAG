import pytest
from pydantic import ValidationError

from app.config import Settings

VALID_SETTINGS = {
    "SUPABASE_URL": "https://project.supabase.co",
    "SUPABASE_ANON_KEY": "anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "DATABASE_URL": "postgresql://postgres:password@db.project.supabase.co:5432/postgres",
    "OPENAI_API_KEY": "test-openai-key",
}


def test_settings_reject_missing_required_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in VALID_SETTINGS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_parse_allowed_origins() -> None:
    settings = Settings(
        **VALID_SETTINGS,
        ALLOWED_ORIGINS="http://localhost:5173, https://app.example.com",
        _env_file=None,
    )

    assert settings.allowed_origin_list == [
        "http://localhost:5173",
        "https://app.example.com",
    ]


def test_settings_database_url_uses_psycopg_three_driver() -> None:
    settings = Settings(**VALID_SETTINGS, _env_file=None)

    assert settings.sqlalchemy_database_url == (
        "postgresql+psycopg://postgres:password@db.project.supabase.co:5432/postgres"
    )
