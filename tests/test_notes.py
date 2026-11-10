"""Offline tests for notes and key-term verification."""

from pathlib import Path

import pytest

from app.config import Settings
from app.llm import LLMResult
from app.models import Transcript
from app.notes import generate_notes
from app.transcript_index import TranscriptIndex, term_present
from tests.conftest import ScriptedModel

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_sample.json"
SETTINGS = Settings()

QUOTE = (
    "The key idea is gradient descent, which updates the weights "
    "in the direction of the negative gradient."
)


@pytest.fixture(scope="module")
def index() -> TranscriptIndex:
    return TranscriptIndex.build(Transcript.from_json_file(FIXTURE))


def model_result(data: dict) -> LLMResult:
    return LLMResult(data=data, finish_reason="stop", usage={"total_tokens": 10})


def section(heading: str, bullets: list[dict]) -> dict:
    return {"heading": heading, "bullets": bullets}


def bullet(text: str, quotes: list[str]) -> dict:
    return {"text": text, "evidence_quotes": quotes}


def candidate(term: str, definition: str, quote: str, importance: int) -> dict:
    return {
        "term": term,
        "definition": definition,
        "evidence_quote": quote,
        "importance": importance,
    }


BASE_SECTIONS = [
    section(
        "What gradient descent does",
        [
            bullet("It updates the weights toward the negative gradient.", [QUOTE]),
            bullet(
                "The learning rate sets the step size.",
                ["The size of that step is the learning rate."],
            ),
            bullet("This claim was never spoken.", ["A sentence that is not in the lecture."]),
        ],
    ),
    section(
        "Intuition",
        [
            bullet(
                "The loss behaves like a landscape.",
                ["Think of the loss as a landscape and the weights as a position on that landscape."],
            ),
            bullet(
                "Backpropagation reuses intermediate values.",
                ["Backpropagation makes this cheap because it reuses intermediate values."],
            ),
        ],
    ),
]

BASE_CANDIDATES = [
    candidate(
        "gradient descent",
        "updates the weights in the direction of the negative gradient",
        QUOTE,
        9,
    ),
    candidate(
        "learning rate",
        "the size of the step we take",
        "The size of that step is the learning rate.",
        8,
    ),
    candidate(
        "neural network",
        "a model that learns from data",
        "Today we will look at how a neural network learns from data.",
        7,
    ),
    candidate(
        "backpropagation",
        "reuses intermediate values to make training cheap",
        "Backpropagation makes this cheap because it reuses intermediate values.",
        6,
    ),
    candidate(
        "adam optimizer",
        "an optimizer the lecturer recommends",
        "The lecturer recommends using the Adam optimizer with a fixed schedule.",
        5,
    ),
    candidate(
        "loss landscape",
        "the shape of the loss surface",
        "Think of the loss as a landscape and the weights as a position on that landscape.",
        4,
    ),
]


def test_verified_content_only_and_five_terms(index):
    retry = {
        "key_term_candidates": [
            candidate(
                "negative gradient",
                "the direction in which the weights are updated",
                "which updates the weights in the direction of the negative gradient",
                5,
            )
        ]
    }
    model = ScriptedModel(
        model_result(
            {
                "notes": {
                    "title": "Gradient descent",
                    "overview": "How training updates the weights.",
                    "sections": BASE_SECTIONS,
                },
                "key_term_candidates": BASE_CANDIDATES,
            }
        ),
        model_result(retry),
    )

    result = generate_notes(index, model, settings=SETTINGS)

    # The fabricated bullet is absent; every shown bullet carries evidence.
    displayed = [b for s in result.notes.sections for b in s.bullets]
    assert len(displayed) == 4
    assert all(bullet_item.evidence and bullet_item.evidence[0].verified for bullet_item in displayed)
    assert result.notes.word_count <= SETTINGS.max_notes_words

    assert len(result.key_terms) == 5
    assert all(term_present(index, term.term) for term in result.key_terms)
    assert {term.term for term in result.key_terms} == {
        "gradient descent",
        "learning rate",
        "neural network",
        "backpropagation",
        "negative gradient",
    }

    assert result.report.notes.generated == 5
    assert result.report.notes.verified == 4
    assert result.report.notes.removed == 1
    assert result.report.key_terms.verified == 5
    assert result.report.key_terms.regenerated is True

    retry_prompt = model.calls[1]["user"]
    assert "adam optimizer" in retry_prompt
    assert "gradient descent" in retry_prompt


def test_off_lecture_definition_is_rejected(index):
    candidates = list(BASE_CANDIDATES[:4]) + [
        candidate(
            "landscape",
            "a cooking technique using tomatoes and pasta",
            "Think of the loss as a landscape and the weights as a position on that landscape.",
            10,
        )
    ]
    # Five accepted names would include the bad definition, so it must be
    # rejected and the retry supplies a genuine fifth term.
    retry = {
        "key_term_candidates": [
            candidate(
                "negative gradient",
                "the direction in which the weights are updated",
                "which updates the weights in the direction of the negative gradient",
                3,
            )
        ]
    }
    model = ScriptedModel(
        model_result(
            {
                "notes": {"title": "t", "overview": "o", "sections": BASE_SECTIONS},
                "key_term_candidates": candidates,
            }
        ),
        model_result(retry),
    )

    result = generate_notes(index, model, settings=SETTINGS)

    assert "definition is not built from the lecture's own words" in model.calls[1]["user"]
    assert all("cooking" not in term.definition for term in result.key_terms)
    assert len(result.key_terms) == 5


def test_regeneration_is_bounded(index):
    three_terms = BASE_CANDIDATES[:3]
    model = ScriptedModel(
        model_result(
            {"notes": {"title": "t", "overview": "o", "sections": BASE_SECTIONS},
             "key_term_candidates": three_terms}
        ),
        model_result({"key_term_candidates": []}),
        model_result({"key_term_candidates": []}),
    )

    result = generate_notes(index, model, settings=SETTINGS)

    assert len(result.key_terms) == 3
    assert len(model.calls) == 1 + SETTINGS.key_term_attempts
    assert result.report.key_terms.regenerated is True


def test_notes_are_trimmed_to_the_word_cap(index):
    long_text = " ".join(["word"] * 120)
    sections = [
        section(f"Section {number}", [bullet(long_text, [QUOTE]) for _ in range(3)])
        for number in range(3)
    ]
    model = ScriptedModel(
        model_result(
            {"notes": {"title": "t", "overview": "o", "sections": sections},
             "key_term_candidates": BASE_CANDIDATES}
        ),
        model_result(
            {
                "key_term_candidates": [
                    candidate(
                        "negative gradient",
                        "the direction in which the weights are updated",
                        "which updates the weights in the direction of the negative gradient",
                        3,
                    )
                ]
            }
        ),
    )

    result = generate_notes(index, model, settings=SETTINGS)

    assert result.notes.word_count <= SETTINGS.max_notes_words
    assert all(len(section_item.bullets) >= 2 for section_item in result.notes.sections)
