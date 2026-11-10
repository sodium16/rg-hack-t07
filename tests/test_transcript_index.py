"""Offline tests for normalisation and the transcript index (04 §1, §4)."""

from pathlib import Path

import pytest

from app.models import Transcript
from app.transcript_index import TranscriptIndex, norm, term_present

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_sample.json"


@pytest.fixture(scope="module")
def index() -> TranscriptIndex:
    return TranscriptIndex.build(Transcript.from_json_file(FIXTURE))


def test_norm_folds_case_punctuation_and_dashes():
    assert norm("Gradient—descent,  Well-known!") == "gradient descent well known"


def test_norm_keeps_intra_word_apostrophe_and_decimal():
    assert norm("The lecture's main point is 3.14 exactly.") == "the lecture's main point is 3.14 exactly"


def test_tokens_use_word_offsets_when_present(index):
    tokens = [token for token in index.tokens if token.phrase_id == 2]
    assert len(tokens) == 17
    assert tokens[0].start_ms == 6000
    assert tokens[-1].end_ms == 14500


def test_tokens_interpolate_when_word_offsets_missing(index):
    tokens = [token for token in index.tokens if token.phrase_id == 4]
    assert len(tokens) == 13
    assert tokens[0].start_ms == 22000
    assert tokens[-1].end_ms == 30000
    starts = [token.start_ms for token in tokens]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)


def test_norm_text_has_single_spaces(index):
    assert "  " not in index.norm_text
    assert not index.norm_text.startswith(" ")
    assert not index.norm_text.endswith(" ")


def test_term_present_accepts_plural_variant(index):
    assert term_present(index, "neural networks")


def test_term_present_accepts_hyphen_compact_variant(index):
    assert term_present(index, "back-propagation")


def test_term_present_rejects_absent_term(index):
    assert not term_present(index, "adam optimizer")


def test_term_present_positive_control(index):
    assert term_present(index, "learning rate")
