"""Live end-to-end check on one real clip. Never runs in the offline suite.

    .venv/Scripts/python.exe -m pytest -m integration -q

It transcribes, generates notes and key terms, asks one covered question and one
unrelated question, and asserts the trust layer's guarantees. Set ``SMOKE_CLIP``
to point at the team clip; it defaults to the synthetic smoke file.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import MissingConfigError, load_settings, require_azure_env
from app.llm import FoundryClient
from app.notes import generate_notes
from app.qa import answer_question
from app.speech import transcribe_with_env
from app.transcript_index import TranscriptIndex

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent
CLIP = Path(os.environ.get("SMOKE_CLIP", ROOT / "data" / "samples" / "clip1.mp3"))
QUESTION = os.environ.get("SMOKE_QUESTION", "What does the learning rate control?")
UNRELATED = "Who won the 2022 World Cup?"


@pytest.fixture(scope="module")
def live():
    load_settings()
    try:
        require_azure_env()
    except MissingConfigError as error:
        pytest.skip(str(error))
    if not CLIP.is_file():
        pytest.skip(f"no clip at {CLIP}; set SMOKE_CLIP")

    speech = transcribe_with_env(CLIP)
    index = TranscriptIndex.build(speech.transcript)
    return speech, index, FoundryClient.from_env()


def test_transcript_has_timestamps(live):
    speech, index, _ = live
    phrases = index.transcript.phrases
    assert phrases, "Speech returned no phrases"
    assert all(phrase.start_ms <= phrase.end_ms for phrase in phrases)
    assert all(
        later.start_ms >= earlier.start_ms for earlier, later in zip(phrases, phrases[1:])
    )


def test_notes_and_five_verified_key_terms(live):
    _, index, model = live
    result = generate_notes(index, model)

    assert result.notes.sections, "no notes sections survived verification"
    for section in result.notes.sections:
        for bullet in section.bullets:
            assert bullet.evidence, "a shown bullet has no verified evidence"

    assert len(result.key_terms) == 5
    for term in result.key_terms:
        assert term.term_found_in_transcript
        assert term.evidence and term.evidence[0].verified
        assert term.evidence[0].start_ms is not None


def test_covered_question_gets_a_timestamp(live):
    _, index, model = live
    result = answer_question(QUESTION, index, model)

    assert result.covered is True, f"refused: {result.refusal_reason}"
    assert result.primary_timestamp_ms is not None
    assert result.evidence and all(item.verified for item in result.evidence)


def test_unrelated_question_is_refused(live):
    _, index, model = live
    result = answer_question(UNRELATED, index, model)

    assert result.covered is False
    assert result.answer == ""
    assert result.primary_timestamp_ms is None
    assert result.refusal_reason
