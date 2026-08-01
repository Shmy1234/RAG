import pytest
from pydantic import ValidationError

from app.config import Settings

VALID_SETTINGS = {
    "SUPABASE_URL": "https://project.supabase.co",
    "SUPABASE_ANON_KEY": "anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
    "DATABASE_URL": "postgresql://postgres:password@db.project.supabase.co:5432/postgres",
    "OPENAI_API_KEY": "test-openai-key",
    "OPENAI_CHAT_MODEL": "openai:gpt-5-mini",
}


def test_settings_reject_missing_required_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in VALID_SETTINGS:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_blank_required_configuration() -> None:
    invalid_settings = VALID_SETTINGS | {"OPENAI_API_KEY": "   "}

    with pytest.raises(ValidationError):
        Settings(**invalid_settings, _env_file=None)


def test_settings_requires_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_CHAT_MODEL")
    settings_without_chat_model = {
        name: value for name, value in VALID_SETTINGS.items() if name != "OPENAI_CHAT_MODEL"
    }

    with pytest.raises(ValidationError, match="OPENAI_CHAT_MODEL"):
        Settings(**settings_without_chat_model, _env_file=None)


def test_settings_rejects_blank_chat_model() -> None:
    invalid_settings = VALID_SETTINGS | {"OPENAI_CHAT_MODEL": "   "}

    with pytest.raises(ValidationError, match="must not be empty"):
        Settings(**invalid_settings, _env_file=None)


def test_settings_rejects_non_openai_chat_model() -> None:
    invalid_settings = VALID_SETTINGS | {"OPENAI_CHAT_MODEL": "anthropic:claude"}

    with pytest.raises(ValidationError, match="must start with 'openai:'"):
        Settings(**invalid_settings, _env_file=None)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SUPABASE_URL", "project.supabase.co"),
        ("DATABASE_URL", "https://db.project.supabase.co/postgres"),
    ],
)
def test_settings_reject_invalid_urls(name: str, value: str) -> None:
    invalid_settings = VALID_SETTINGS | {name: value}

    with pytest.raises(ValidationError):
        Settings(**invalid_settings, _env_file=None)


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
