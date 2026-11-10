"""Environment-backed settings and the project's thresholds.

Every tunable value lives here rather than in a literal at the call site
(04_VERIFICATION_ENGINE.md §9). Values are read from the environment with safe
defaults so that the offline tests never need Azure credentials; credential
presence is checked only by ``require_azure_env()``, which the Speech and LLM
clients call.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_AZURE_VARS = (
    "AZURE_SPEECH_KEY",
    "AZURE_SPEECH_REGION",
    "AZURE_FOUNDRY_ENDPOINT",
    "AZURE_FOUNDRY_KEY",
    "AZURE_FOUNDRY_DEPLOYMENT",
    "AZURE_FOUNDRY_API_VERSION",
)


class MissingConfigError(RuntimeError):
    """A required setting is missing or malformed.

    The message is written for a human running the app, never a stack trace.
    """


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise MissingConfigError(
            f"{name} must be a number, got {raw!r}. See .env.example."
        ) from error


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise MissingConfigError(
            f"{name} must be a whole number, got {raw!r}. See .env.example."
        ) from error


@dataclass(frozen=True)
class Settings:
    """Thresholds and caps shared by the pipeline.

    Defaults are the documented values. Anything the team tunes during the
    eval must end up in the Evidence Sheet, so change them here and nowhere
    else.
    """

    match_threshold: float = 0.88
    min_quote_tokens: int = 5
    max_quote_tokens: int = 40
    seek_lead_in_ms: int = 1000
    low_confidence_threshold: float = 0.80
    max_audio_minutes: int = 10
    max_upload_mb: int = 50
    min_audio_seconds: int = 20
    speech_locale: str = "en-US"
    max_notes_words: int = 400
    llm_max_tokens: int = 1600
    key_term_attempts: int = 2
    definition_overlap_min: float = 0.50
    answer_grounding_min: float = 0.60
    use_judge: bool = False


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Read settings once from the environment (loading .env if present)."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return Settings(
        match_threshold=_env_float("MATCH_THRESHOLD", 0.88),
        min_quote_tokens=5,
        max_quote_tokens=40,
        seek_lead_in_ms=1000,
        low_confidence_threshold=0.80,
        max_audio_minutes=_env_int("MAX_AUDIO_MINUTES", 10),
        max_upload_mb=50,
        min_audio_seconds=20,
        speech_locale=_env_str("AZURE_SPEECH_LOCALE", "en-US"),
        max_notes_words=400,
        llm_max_tokens=1600,
        key_term_attempts=2,
        definition_overlap_min=0.50,
        answer_grounding_min=0.60,
        use_judge=_env_str("USE_JUDGE", "false").lower() in {"1", "true", "yes"},
    )


def require_azure_env() -> dict[str, str]:
    """Return the Azure settings, or fail with a readable message.

    Called by the Speech and LLM clients only, so offline work (the
    verification engine and its tests) runs without any credentials.
    """
    # Clients may be built before anything else touches the settings cache.
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    missing = [name for name in REQUIRED_AZURE_VARS if not os.environ.get(name, "").strip()]
    if missing:
        raise MissingConfigError(
            "Missing environment variable(s): "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill the values locally."
        )
    return {name: os.environ[name].strip() for name in REQUIRED_AZURE_VARS}
