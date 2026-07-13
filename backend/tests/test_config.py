from backend.auditor.config import Settings


def test_settings_load_uppercase_environment_without_exposing_secrets(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:private@db/auditor")
    monkeypatch.setenv("OLLAMA_INSTRUCTION_MODEL", "configured-model")

    settings = Settings(_env_file=None)

    assert settings.psycopg_url == "postgresql://user:private@db/auditor"
    assert settings.ollama_instruction_model == "configured-model"
    assert "private" not in repr(settings)
