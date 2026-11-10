"""Offline tests for grounded Q&A and the not-covered gate."""

from pathlib import Path

import pytest

from app.config import Settings
from app.llm import LLMResult
from app.models import Transcript
from app.qa import REFUSAL_TEXT, answer_question
from app.transcript_index import TranscriptIndex
from tests.conftest import ScriptedModel

FIXTURE = Path(__file__).parent / "fixtures" / "transcript_sample.json"
SETTINGS = Settings()
JUDGE_ON = Settings(use_judge=True)

QUOTE = (
    "The key idea is gradient descent, which updates the weights "
    "in the direction of the negative gradient."
)
ANSWER = "It updates the weights in the direction of the negative gradient."


@pytest.fixture(scope="module")
def index() -> TranscriptIndex:
    return TranscriptIndex.build(Transcript.from_json_file(FIXTURE))


def model_reply(
    covered: bool, answer: str, quotes: list[str], reason: str = ""
) -> LLMResult:
    return LLMResult(
        data={
            "covered": covered,
            "answer": answer,
            "evidence_quotes": quotes,
            "reason": reason,
        },
        finish_reason="stop",
        usage={"total_tokens": 10},
    )


def test_answer_with_different_inflections_still_grounds(index):
    reply = model_reply(
        True,
        "The weights are updated in the direction of the negative gradient.",
        [QUOTE],
    )
    result = answer_question(
        "What does gradient descent update?", index, ScriptedModel(reply), settings=SETTINGS
    )
    assert result.covered is True
    assert result.primary_timestamp_ms == 6000


def test_covered_question_gets_a_verified_timestamp(index):
    model = ScriptedModel(model_reply(True, ANSWER, [QUOTE]))
    result = answer_question("What does gradient descent update?", index, model, settings=SETTINGS)

    assert result.covered is True
    assert result.primary_timestamp_ms == 6000
    assert result.evidence and all(item.verified for item in result.evidence)
    assert result.model_claimed_covered is True
    assert result.refusal_reason is None


def test_question_about_an_absent_topic_is_refused_despite_a_real_quote(index):
    model = ScriptedModel(
        model_reply(True, "The lecturer recommends the Adam optimizer.", [QUOTE])
    )
    result = answer_question(
        "What does the lecturer say about the Adam optimizer?", index, model, settings=SETTINGS
    )

    assert result.covered is False
    assert result.answer == ""
    assert result.primary_timestamp_ms is None
    assert result.refusal_reason == "quote does not answer the question"
    assert result.model_claimed_covered is True


def test_hallucinated_quote_is_refused_and_counted(index):
    model = ScriptedModel(
        model_reply(True, ANSWER, ["This sentence was never spoken in the lecture."])
    )
    result = answer_question("What does gradient descent update?", index, model, settings=SETTINGS)

    assert result.covered is False
    assert result.refusal_reason == "claimed answer not found in transcript"
    assert result.model_claimed_covered is True


def test_model_cannot_grant_coverage_after_refusing(index):
    model = ScriptedModel(model_reply(False, "", []))
    result = answer_question("What does gradient descent update?", index, model, settings=SETTINGS)

    assert result.covered is False
    assert result.model_claimed_covered is False
    assert result.refusal_reason == "model reported the lecture does not cover this"


def test_question_without_concepts_is_refused(index):
    model = ScriptedModel(model_reply(True, "It updates the weights.", [QUOTE]))
    result = answer_question("What is it?", index, model, settings=SETTINGS)

    assert result.covered is False
    assert result.refusal_reason == "quote does not answer the question"


def test_answer_using_outside_knowledge_is_refused(index):
    model = ScriptedModel(
        model_reply(
            True,
            "Bananas are rich in potassium and grow in tropical climates.",
            [QUOTE],
        )
    )
    result = answer_question("What does gradient descent update?", index, model, settings=SETTINGS)

    assert result.covered is False


def test_paraphrase_drawing_on_nearby_lecture_words_still_grounds(index):
    """A faithful answer may reuse words from the passage, not the quoted phrases."""
    model = ScriptedModel(
        model_reply(
            True,
            "It measures the slope of the loss landscape and takes a step "
            "downhill; the size of that step is the learning rate.",
            [QUOTE],
        )
    )
    result = answer_question(
        "What does gradient descent do?", index, model, settings=SETTINGS
    )

    assert result.covered is True
    assert result.primary_timestamp_ms == 6000


def test_meta_reference_to_the_material_does_not_break_grounding(index):
    """Answers often say "as confirmed earlier in the transcript"; that is not content."""
    model = ScriptedModel(
        model_reply(
            True,
            "Gradient descent updates the weights in the direction of the negative "
            "gradient, as confirmed earlier in the transcript of the recording "
            "according to the dialogue.",
            [QUOTE],
        )
    )
    result = answer_question(
        "What does gradient descent update?", index, model, settings=SETTINGS
    )

    assert result.covered is True
    assert result.primary_timestamp_ms == 6000


def test_judge_can_veto_when_enabled(index):
    seen: dict[str, str] = {}

    def judge(question: str, excerpt: str, answer: str) -> bool:
        seen["excerpt"] = excerpt
        return False

    model = ScriptedModel(model_reply(True, ANSWER, [QUOTE]))
    result = answer_question(
        "What does gradient descent update?", index, model, settings=JUDGE_ON, judge=judge
    )

    assert result.covered is False
    assert "gradient descent" in seen["excerpt"]


def test_judge_approval_keeps_the_answer(index):
    model = ScriptedModel(model_reply(True, ANSWER, [QUOTE]))
    result = answer_question(
        "What does gradient descent update?",
        index,
        model,
        settings=JUDGE_ON,
        judge=lambda question, excerpt, answer: True,
    )
    assert result.covered is True


def test_judge_is_not_called_when_disabled(index):
    def judge(question: str, excerpt: str, answer: str) -> bool:
        raise AssertionError("judge should not run when use_judge is false")

    model = ScriptedModel(model_reply(True, ANSWER, [QUOTE]))
    result = answer_question(
        "What does gradient descent update?", index, model, settings=SETTINGS, judge=judge
    )
    assert result.covered is True


def test_empty_question_refuses_without_calling_the_model(index):
    model = ScriptedModel()
    result = answer_question("   ", index, model, settings=SETTINGS)

    assert result.covered is False
    assert result.refusal_reason == "the question is empty"
    assert model.calls == []


def test_refusal_text_is_exact():
    assert REFUSAL_TEXT == "Not covered in this lecture"
