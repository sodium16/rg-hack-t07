"""Offline tests for the fast-transcription client."""

import json

import pytest

from app.speech import (
    SpeechAuthError,
    SpeechError,
    build_definition,
    parse_transcription,
    transcribe_file,
)
from tests.conftest import FakeResponse, FakeSession


def test_parse_transcription_maps_the_contract(speech_payload):
    transcript = parse_transcription(speech_payload, audio_id="abc")

    assert transcript.duration_ms == 12000
    assert transcript.locale == "en-US"
    assert [phrase.id for phrase in transcript.phrases] == [1, 2]

    first = transcript.phrases[0]
    assert first.start_ms == 0
    assert first.end_ms == 4000
    assert first.confidence == 0.94
    assert first.words[0].text == "Gradient"
    assert first.words[0].start_ms == 0
    assert first.words[0].end_ms == 500
    assert transcript.phrases[1].words == []


def test_definition_includes_locale_and_phrase_list():
    definition = json.loads(build_definition("en-US", ["gradient descent", "backpropagation"]))
    assert definition == {
        "locales": ["en-US"],
        "phraseList": {"phrases": ["gradient descent", "backpropagation"]},
    }


def test_definition_omits_empty_phrase_list():
    assert json.loads(build_definition("en-US", [])) == {"locales": ["en-US"]}


def test_transcribe_file_posts_multipart_and_caches(tmp_path, speech_payload):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"fake-audio-bytes")
    session = FakeSession([FakeResponse(200, speech_payload)])

    result = transcribe_file(
        audio,
        key="test-key",
        region="centralindia",
        locale="en-US",
        phrase_list=["gradient descent"],
        cache_dir=tmp_path / "cache",
        session=session,
        sleeper=lambda _: None,
    )

    assert result.cached is False
    call = session.calls[0]
    assert "api-version=2025-10-15" in call["url"]
    assert "centralindia" in call["url"]
    assert call["files"]["audio"][0] == "clip.wav"
    assert json.loads(call["data"]["definition"])["phraseList"]["phrases"] == ["gradient descent"]
    assert (tmp_path / "cache" / f"{result.audio_sha256}.speech.json").is_file()

    class NoCalls:
        def post(self, *args, **kwargs):
            raise AssertionError("cache miss: the client called Azure again")

    cached = transcribe_file(
        audio,
        key="test-key",
        region="centralindia",
        cache_dir=tmp_path / "cache",
        session=NoCalls(),
        sleeper=lambda _: None,
    )
    assert cached.cached is True
    assert cached.transcript.duration_ms == 12000


def test_auth_failure_is_typed_and_does_not_leak_the_key(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"x")
    session = FakeSession([FakeResponse(401, text='{"error":"unauthorized"}')])

    with pytest.raises(SpeechAuthError) as error:
        transcribe_file(
            audio,
            key="super-secret-key",
            region="r",
            cache_dir=tmp_path / "c",
            session=session,
            sleeper=lambda _: None,
        )
    assert "AZURE_SPEECH_KEY" in str(error.value)
    assert "super-secret-key" not in str(error.value)


def test_retries_on_service_unavailable(tmp_path, speech_payload):
    audio = tmp_path / "clip.wav"
    audio.write_bytes(b"x")
    session = FakeSession([FakeResponse(503, text="busy"), FakeResponse(200, speech_payload)])

    result = transcribe_file(
        audio,
        key="k",
        region="r",
        cache_dir=tmp_path / "c",
        session=session,
        sleeper=lambda _: None,
    )
    assert result.transcript.phrases[0].text.startswith("Gradient")
    assert len(session.calls) == 2


def test_empty_phrases_raise(speech_payload):
    payload = dict(speech_payload)
    payload["phrases"] = []
    with pytest.raises(SpeechError, match="No speech"):
        parse_transcription(payload, audio_id="abc")
