"""Upload validation, duration probing and content hashing.

Everything here runs before an Azure call, so an unsupported, oversized or
too-long file is rejected for free (F1.1). Duration is read with ``mutagen``
rather than ``ffprobe`` so the check works on a machine without ffmpeg.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import mutagen

from app.config import Settings, load_settings

ALLOWED_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".mp4", ".ogg", ".flac", ".webm"})
_BYTES_PER_MB = 1024 * 1024


class AudioValidationError(ValueError):
    """The upload cannot be processed; the message is shown to the student."""


@dataclass(frozen=True)
class AudioInfo:
    path: Path
    size_bytes: int
    duration_ms: int
    sha256: str


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_duration_ms(path: str | Path) -> int:
    """Read the clip's duration without transcribing it."""
    try:
        audio = mutagen.File(str(path))
    except Exception as error:  # mutagen raises several unrelated types
        raise AudioValidationError(
            "That audio file could not be read. Try exporting it as WAV or MP3."
        ) from error
    length = getattr(getattr(audio, "info", None), "length", None)
    if not length:
        raise AudioValidationError(
            "That audio file's duration could not be read. Try exporting it as WAV or MP3."
        )
    return int(round(float(length) * 1000))


def _check_extension(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(extension.lstrip(".") for extension in ALLOWED_EXTENSIONS))
        raise AudioValidationError(
            f"{suffix or 'That file type'} is not supported. Upload one of: {allowed}."
        )


def _check_size(size_bytes: int, config: Settings) -> None:
    if size_bytes <= 0:
        raise AudioValidationError("That file is empty. Upload a recorded lecture clip.")
    limit_bytes = config.max_upload_mb * _BYTES_PER_MB
    if size_bytes > limit_bytes:
        raise AudioValidationError(
            f"That file is {size_bytes / _BYTES_PER_MB:.1f} MB; the limit is "
            f"{config.max_upload_mb} MB. Trim the clip or compress it to MP3."
        )


def _check_duration(duration_ms: int, config: Settings) -> None:
    if duration_ms < config.min_audio_seconds * 1000:
        raise AudioValidationError(
            f"That clip is only {duration_ms / 1000:.0f} seconds; upload at least "
            f"{config.min_audio_seconds} seconds of lecture."
        )
    max_ms = config.max_audio_minutes * 60 * 1000
    if duration_ms > max_ms:
        raise AudioValidationError(
            f"That clip is {duration_ms / 60000:.1f} minutes; the limit is "
            f"{config.max_audio_minutes} minutes. Trim it and try again."
        )


def validate_upload(
    filename: str,
    size_bytes: int,
    duration_ms: int,
    *,
    settings: Settings | None = None,
) -> None:
    """Reject bad uploads with a message that says what to do next."""
    config = settings or load_settings()
    _check_extension(filename)
    _check_size(size_bytes, config)
    _check_duration(duration_ms, config)


def load_audio(path: str | Path, *, settings: Settings | None = None) -> AudioInfo:
    """Validate a local file and return everything the pipeline needs."""
    config = settings or load_settings()
    audio_path = Path(path)
    if not audio_path.is_file():
        raise AudioValidationError(f"Audio file not found: {audio_path.name}")

    size_bytes = audio_path.stat().st_size
    # Extension and size are checked before the file is opened, so a wrong or
    # oversized upload costs nothing; duration can only be checked afterwards.
    _check_extension(audio_path.name)
    _check_size(size_bytes, config)
    duration_ms = probe_duration_ms(audio_path)
    validate_upload(audio_path.name, size_bytes, duration_ms, settings=config)

    return AudioInfo(
        path=audio_path,
        size_bytes=size_bytes,
        duration_ms=duration_ms,
        sha256=sha256_file(audio_path),
    )
