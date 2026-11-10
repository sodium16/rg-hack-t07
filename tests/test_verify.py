"""Offline tests for the Verification Engine (04 §2, §5, §8)."""

from pathlib import Path

import pytest

from app.config import Settings
from app.models import Transcript
from app.transcript_index import TranscriptIndex
from app.verify import decide_covered, locate, seek_ms

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_sample.json"

# Documented defaults: threshold 0.88, 5..40 tokens, 1000 ms lead-in.
SETTINGS = Settings()

QUOTE = (
    "The key idea is gradient descent, which updates the weights "
    "in the direction of the negative gradient."
)


@pytest.fixture(scope="module")
def index() -> TranscriptIndex:
    return TranscriptIndex.build(Transcript.from_json_file(FIXTURE))


def test_exact_quote_scores_one_and_returns_start(index):
    evidence = locate(QUOTE, index, settings=SETTINGS)
    assert evidence.verified
    assert evidence.match_score == 1.0
    assert evidence.start_ms == 6000
    assert evidence.end_ms == 14500
    assert evidence.phrase_ids == [2]
    assert "weights" in evidence.quote_matched


def test_case_and_punctuation_differences_still_verify(index):
    evidence = locate(QUOTE.lower().replace(",", ""), index, settings=SETTINGS)
    assert evidence.verified
    assert evidence.match_score == 1.0
    assert evidence.start_ms == 6000


def test_one_changed_word_still_verifies(index):
    evidence = locate(QUOTE.replace("weights", "parameters"), index, settings=SETTINGS)
    assert evidence.verified
    assert evidence.match_score >= SETTINGS.match_threshold


def test_three_changed_words_fail(index):
    evidence = locate("The form of this jump was a study pace.", index, settings=SETTINGS)
    assert not evidence.verified
    assert evidence.start_ms is None
    assert evidence.match_score < SETTINGS.match_threshold


def test_quote_spanning_two_phrases_returns_both_ids(index):
    quote = "a position on that landscape at every step we measure the slope"
    evidence = locate(quote, index, settings=SETTINGS)
    assert evidence.verified
    assert evidence.phrase_ids == [3, 4]
    assert evidence.start_ms is not None and evidence.start_ms < 22000
    assert evidence.end_ms is not None and evidence.end_ms > 22000


def test_hallucinated_quote_fails_with_no_timestamp(index):
    quote = "The lecturer recommends using the Adam optimizer with a fixed schedule."
    evidence = locate(quote, index, settings=SETTINGS)
    assert not evidence.verified
    assert evidence.start_ms is None
    assert evidence.phrase_ids == []


def test_quote_shorter_than_five_tokens_is_rejected(index):
    evidence = locate("negative gradient", index, settings=SETTINGS)
    assert not evidence.verified
    assert evidence.start_ms is None


def test_repeated_sentence_prefers_earliest_by_default(index):
    evidence = locate(QUOTE, index, settings=SETTINGS)
    assert evidence.verified
    assert evidence.start_ms == 6000


def test_repeated_sentence_hint_selects_later_occurrence(index):
    evidence = locate(QUOTE, index, hint_ms=48000, settings=SETTINGS)
    assert evidence.verified
    assert evidence.start_ms == 44000
    assert evidence.phrase_ids == [7]


def test_seek_ms_applies_the_documented_lead_in(index):
    evidence = locate(QUOTE, index, settings=SETTINGS)
    assert seek_ms(evidence, settings=SETTINGS) == 5000


def test_not_covered_decision_table():
    assert decide_covered(
        quote_verified=True, gate_passes=True, model_claimed_covered=True
    ).covered
    assert decide_covered(
        quote_verified=True, gate_passes=True, model_claimed_covered=None
    ).covered

    gate_failure = decide_covered(
        quote_verified=True, gate_passes=False, model_claimed_covered=True
    )
    assert not gate_failure.covered
    assert gate_failure.reason == "quote does not answer the question"

    hallucination = decide_covered(
        quote_verified=False, gate_passes=True, model_claimed_covered=True
    )
    assert not hallucination.covered
    assert hallucination.reason == "claimed answer not found in transcript"

    veto = decide_covered(
        quote_verified=True, gate_passes=True, model_claimed_covered=False
    )
    assert not veto.covered
