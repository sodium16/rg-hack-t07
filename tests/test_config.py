"""Offline tests for environment loading and readable config failures."""

import pytest

from app import config
from app.config import MissingConfigError, require_azure_env

REQUIRED = {
    "AZURE_SPEECH_KEY": "speech-key",
    "AZURE_SPEECH_REGION": "koreacentral",
    "AZURE_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1",
    "AZURE_FOUNDRY_KEY": "foundry-key",
    "AZURE_FOUNDRY_DEPLOYMENT": "gpt-4.1-mini",
    "AZURE_FOUNDRY_API_VERSION": "2025-04-14",
}


@pytest.fixture()
def env_file(tmp_path, monkeypatch):
    for name in REQUIRED:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / ".env"
    path.write_text("\n".join(f"{key}={value}" for key, value in REQUIRED.items()), encoding="utf-8")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    return path


def test_require_azure_env_loads_the_dotenv_file(env_file):
    assert require_azure_env()["AZURE_FOUNDRY_DEPLOYMENT"] == "gpt-4.1-mini"


def test_missing_variables_are_named_in_the_error(env_file, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    env_file.write_text("AZURE_SPEECH_REGION=koreacentral", encoding="utf-8")
    with pytest.raises(MissingConfigError, match="AZURE_SPEECH_KEY"):
        require_azure_env()


def test_missing_variables_do_not_leak_values(env_file, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "do-not-print-this")
    env_file.write_text("AZURE_SPEECH_REGION=koreacentral", encoding="utf-8")
    with pytest.raises(MissingConfigError) as error:
        require_azure_env()
    assert "do-not-print-this" not in str(error.value)
