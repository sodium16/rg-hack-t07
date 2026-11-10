"""Azure AI Speech fast transcription → the project's ``Transcript``.

Fast transcription is synchronous, so a 10-minute clip is one POST with the
audio and a JSON ``definition``. The raw response is cached under the audio's
SHA-256, which makes repeat demo runs free — and the cache is only ever read by
the parser, never trusted as a verification shortcut.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from app import net
from app.audio import sha256_file
from app.config import PROJECT_ROOT, Settings, load_settings, require_azure_env
from app.models import Transcript, TranscriptPhrase, Word

# Current GA for fast transcription. The v3.x APIs were retired 31 Mar 2026.
SPEECH_API_VERSION = "2025-10-15"

DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "cache"

_CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


class SpeechError(RuntimeError):
    """Transcription failed; the message is safe to show the student."""


class SpeechAuthError(SpeechError):
    """The Speech key or region is wrong."""


class SpeechAudioError(SpeechError):
    """Speech could not read the uploaded audio."""


@dataclass(frozen=True)
class SpeechResult:
    transcript: Transcript
    cached: bool
    audio_sha256: str


def endpoint_for(region: str) -> str:
    return (
        f"https://{region}.api.cognitive.microsoft.com"
        f"/speechtotext/transcriptions:transcribe?api-version={SPEECH_API_VERSION}"
    )


def build_definition(locale: str, phrase_list: Iterable[str] = ()) -> str:
    """The ``definition`` form field.

    Phrase lists are supported from ``2025-10-15``; sending domain terms makes
    the transcript spell them correctly, which the key-term check then verifies
    honestly against the transcript itself.
    """
    definition: dict[str, Any] = {"locales": [locale]}
    phrases = [phrase for phrase in phrase_list if phrase.strip()]
    if phrases:
        definition["phraseList"] = {"phrases": phrases}
    return json.dumps(definition)


def _milliseconds(item: dict[str, Any], name: str) -> int:
    value = item.get(f"{name}Milliseconds", item.get(name, 0))
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_transcription(
    payload: dict[str, Any], *, audio_id: str, locale: str = "en-US"
) -> Transcript:
    """Map the Speech response onto the frozen ``Transcript`` contract."""
    raw_phrases = payload.get("phrases") or []
    if not raw_phrases:
        raise SpeechError(
            "No speech was recognised in this clip. Check the audio is audible "
            "and that the lecture is in the expected language."
        )

    phrases: list[TranscriptPhrase] = []
    resolved_locale = str(raw_phrases[0].get("locale") or locale)
    for index, item in enumerate(raw_phrases, start=1):
        start_ms = _milliseconds(item, "offset")
        end_ms = start_ms + _milliseconds(item, "duration")
        words = [
            Word(
                text=str(word.get("text") or ""),
                start_ms=_milliseconds(word, "offset"),
                end_ms=_milliseconds(word, "offset") + _milliseconds(word, "duration"),
            )
            for word in item.get("words") or []
            if str(word.get("text") or "").strip()
        ]
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        confidence = item.get("confidence")
        phrases.append(
            TranscriptPhrase(
                id=index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                confidence=None if confidence is None else float(confidence),
                words=words,
            )
        )

    if not phrases:
        raise SpeechError("No speech was recognised in this clip.")

    duration_ms = _milliseconds(payload, "duration") or phrases[-1].end_ms
    return Transcript(
        audio_id=audio_id,
        duration_ms=duration_ms,
        locale=resolved_locale,
        phrases=phrases,
    )


def _map_status(error: net.HttpStatusError) -> SpeechError:
    if error.status_code in {401, 403}:
        return SpeechAuthError(
            "Speech rejected the credentials. Check AZURE_SPEECH_KEY and "
            "AZURE_SPEECH_REGION belong to the same Speech resource."
        )
    if error.status_code == 404:
        return SpeechError(
            "The fast transcription endpoint was not found. The region may not "
            "support it, or the API version is wrong; use a supported region "
            "with api-version=2025-10-15."
        )
    if error.status_code in {400, 413, 415, 422}:
        return SpeechAudioError(
            "Speech could not read that audio. Export it as 16 kHz mono WAV or "
            "MP3 and try again."
        )
    if error.status_code == 429:
        return SpeechError(
            "Speech is busy right now (rate limit). Wait a few seconds and try again."
        )
    return SpeechError(f"Speech failed (HTTP {error.status_code}). Try again shortly.")


def transcribe_file(
    path: str | Path,
    *,
    key: str,
    region: str,
    locale: str = "en-US",
    phrase_list: Iterable[str] = (),
    cache_dir: str | Path | None = None,
    refresh: bool = False,
    session: Any | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    timeout: float = 120.0,
    policy: net.RetryPolicy = net.RetryPolicy(),
) -> SpeechResult:
    """Transcribe one file, using the SHA-256 cache unless ``refresh``.

    Errors are typed, never raw HTTP exceptions, and never include the key.
    """
    audio_path = Path(path)
    audio_sha = sha256_file(audio_path)
    cache_path = Path(cache_dir or DEFAULT_CACHE_DIR) / f"{audio_sha}.speech.json"

    if cache_path.is_file() and not refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return SpeechResult(
            transcript=parse_transcription(payload, audio_id=audio_sha, locale=locale),
            cached=True,
            audio_sha256=audio_sha,
        )

    content_type = _CONTENT_TYPES.get(audio_path.suffix.lower(), "application/octet-stream")
    try:
        response = net.post(
            endpoint_for(region),
            headers={"Ocp-Apim-Subscription-Key": key},
            files={"audio": (audio_path.name, audio_path.read_bytes(), content_type)},
            data={"definition": build_definition(locale, phrase_list)},
            timeout=timeout,
            policy=policy,
            sleeper=sleeper,
            session=session,
        )
    except net.HttpStatusError as error:
        raise _map_status(error) from error
    except net.HttpError as error:
        raise SpeechError(str(error)) from error

    try:
        payload = response.json()
    except ValueError as error:
        raise SpeechError("Speech returned a response that was not JSON.") from error

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(cache_path)

    return SpeechResult(
        transcript=parse_transcription(payload, audio_id=audio_sha, locale=locale),
        cached=False,
        audio_sha256=audio_sha,
    )


def transcribe_with_env(
    path: str | Path,
    *,
    phrase_list: Iterable[str] = (),
    refresh: bool = False,
) -> SpeechResult:
    """Convenience wrapper for the app: reads credentials from the environment."""
    values = require_azure_env()
    settings: Settings = load_settings()
    return transcribe_file(
        path,
        key=values["AZURE_SPEECH_KEY"],
        region=values["AZURE_SPEECH_REGION"],
        locale=settings.speech_locale,
        phrase_list=phrase_list,
        refresh=refresh,
    )
