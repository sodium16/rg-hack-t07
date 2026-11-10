"""Offline tests for the eval metrics that produce the Evidence Sheet numbers."""

import pytest

from eval.run_eval import (
    answer_is_correct,
    normalise_text,
    timestamp_error,
    wer_stats,
)


def test_normalisation_is_identical_on_both_sides():
    assert normalise_text("Gradient descent, updates the WEIGHTS!") == "gradient descent updates the weights"


def test_empty_reference_is_rejected():
    with pytest.raises(Exception):
        wer_stats("", "something")


def test_wer_counts_substitution():
    stats = wer_stats("the weights are updated", "the weights are changed")
    assert stats["wer"] > 0
    assert stats["substitutions"] == 1
    assert stats["reference_words"] == 4


def test_identical_text_scores_zero():
    stats = wer_stats("the weights are updated", "The weights are updated.")
    assert stats["wer"] == 0.0


def test_timestamp_inside_a_window_is_zero_error():
    result = timestamp_error(8_000, [[6_000, 9_000]])
    assert result == {"within_5s": True, "error_ms": 0}


def test_timestamp_outside_a_window_reports_distance():
    result = timestamp_error(20_000, [[6_000, 9_000]])
    assert result["within_5s"] is False
    assert result["error_ms"] == 11_000


def test_timestamp_within_tolerance_counts_as_near():
    result = timestamp_error(12_000, [[6_000, 9_000]])
    assert result == {"within_5s": True, "error_ms": 3_000}


def test_missing_timestamp_never_passes():
    assert timestamp_error(None, [[6_000, 9_000]]) == {"within_5s": False, "error_ms": None}


def test_answer_correctness_checks_any_required_term():
    assert answer_is_correct("It moves the weights downhill.", ["weights", "bias"])
    assert not answer_is_correct("It moves the bias.", ["weights", "gradient"])


def test_answer_without_requirements_is_accepted():
    assert answer_is_correct("anything at all", [])
