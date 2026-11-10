"""Offline tests for upload validation and audio metadata."""

import wave

import pytest

from app.audio import (
    AudioValidationError,
    load_audio,
    sha256_file,
    validate_upload,
)
from app.config import Settings

SETTINGS = Settings()


def make_wav(path, seconds: int = 2, rate: int = 16000):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * rate * seconds)
    return path


@pytest.mark.parametrize("filename", ["lecture.txt", "lecture.pdf", "lecture"])
def test_rejects_unsupported_extension(filename):
    with pytest.raises(AudioValidationError, match="not supported"):
        validate_upload(filename, 1000, 60_000, settings=SETTINGS)


def test_rejects_oversized_file():
    with pytest.raises(AudioValidationError, match="limit is 50 MB"):
        validate_upload("lecture.mp3", 51 * 1024 * 1024, 60_000, settings=SETTINGS)


def test_rejects_too_long_file():
    with pytest.raises(AudioValidationError, match="limit is 10 minutes"):
        validate_upload("lecture.mp3", 1000, 11 * 60 * 1000, settings=SETTINGS)


def test_rejects_too_short_file():
    with pytest.raises(AudioValidationError, match="at least 20 seconds"):
        validate_upload("lecture.mp3", 1000, 5_000, settings=SETTINGS)


def test_accepts_a_valid_upload():
    validate_upload("lecture.m4a", 5_000_000, 5 * 60 * 1000, settings=SETTINGS)


def test_load_audio_probes_duration_and_hash(tmp_path):
    path = make_wav(tmp_path / "clip.wav", seconds=2)
    info = load_audio(path, settings=Settings(min_audio_seconds=1))
    assert 1900 <= info.duration_ms <= 2100
    assert len(info.sha256) == 64
    assert info.size_bytes == path.stat().st_size


def test_hash_is_content_based(tmp_path):
    first = make_wav(tmp_path / "a.wav", seconds=1)
    second = make_wav(tmp_path / "b.wav", seconds=1)
    assert sha256_file(first) == sha256_file(second)
    second.write_bytes(first.read_bytes() + b"\x00\x00")
    assert sha256_file(first) != sha256_file(second)


def test_rejects_unsupported_extension_before_probing(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("not audio")
    with pytest.raises(AudioValidationError, match="not supported"):
        load_audio(path, settings=SETTINGS)
