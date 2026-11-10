"""Grounded Q&A and the literal not-covered decision.

The model proposes an answer and quotes; the gate decides. Coverage requires a
verified quote *and* a relevance check, so a related-but-unasked topic cannot
slip through, and a model can refuse but never grant coverage.
"""

from __future__ import annotations

from typing import Callable

from app.config import Settings, load_settings
from app.language import content_words, stem
from app.llm import ChatModel
from app.models import Evidence, QAResult
from app.prompts import SHARED_SYSTEM, judge_prompt, qa_prompt, timestamped_transcript
from app.transcript_index import TranscriptIndex, phrase_window
from app.verify import decide_covered, locate

# Judges may grep for this exact string (F6.3).
REFUSAL_TEXT = "Not covered in this lecture"

Judge = Callable[[str, str, str], bool]


def answer_question(
    question: str,
    index: TranscriptIndex,
    model: ChatModel,
    *,
    settings: Settings | None = None,
    judge: Judge | None = None,
) -> QAResult:
    """Ask the model, then verify and gate its answer."""
    config = settings or load_settings()
    cleaned = (question or "").strip()
    if not cleaned:
        return QAResult(
            question=cleaned,
            covered=False,
            answer="",
            evidence=[],
            primary_timestamp_ms=None,
            refusal_reason="the question is empty",
            model_claimed_covered=None,
        )

    result = model.complete_json(
        SHARED_SYSTEM,
        qa_prompt(timestamped_transcript(index.transcript), cleaned),
        max_tokens=800,
    )
    payload = result.data

    claimed = payload.get("covered")
    model_claimed = None if claimed is None else bool(claimed)
    answer = str(payload.get("answer") or "").strip()
    quotes = [
        str(quote).strip()
        for quote in payload.get("evidence_quotes") or []
        if str(quote).strip()
    ]
    evidence = [locate(quote, index, settings=config) for quote in quotes]
    verified = [item for item in evidence if item.verified]

    gate_passes = _relevance_gate(
        cleaned, answer, verified, index, config, judge
    )
    coverage = decide_covered(
        quote_verified=bool(verified),
        gate_passes=gate_passes,
        model_claimed_covered=model_claimed,
    )

    if not coverage.covered:
        return QAResult(
            question=cleaned,
            covered=False,
            answer="",
            evidence=verified,
            primary_timestamp_ms=None,
            refusal_reason=coverage.reason,
            model_claimed_covered=model_claimed,
            usage=_usage(result.usage),
        )

    primary = _primary(verified)
    return QAResult(
        question=cleaned,
        covered=True,
        answer=answer,
        evidence=verified,
        primary_timestamp_ms=primary.start_ms if primary else None,
        refusal_reason=None,
        model_claimed_covered=model_claimed,
        usage=_usage(result.usage),
    )


def _usage(raw: dict) -> dict[str, int]:
    """Token counts for the report, without trusting non-integer fields."""
    return {
        name: value
        for name, value in (raw or {}).items()
        if isinstance(value, int) and not isinstance(value, bool)
    }


def _primary(verified: list[Evidence]) -> Evidence | None:
    """Best-scoring quote; earliest wins a tie."""
    if not verified:
        return None
    return min(verified, key=lambda item: (-item.match_score, item.start_ms or 0))


def _relevance_gate(
    question: str,
    answer: str,
    verified: list[Evidence],
    index: TranscriptIndex,
    config: Settings,
    judge: Judge | None,
) -> bool:
    """Cheap deterministic checks first, then the optional judge call."""
    if not verified:
        return False

    concepts = content_words(question)
    if not concepts:
        return False

    transcript_words = content_words(index.norm_text)
    if not (concepts & transcript_words):
        # The question's central term never occurs: cheap, strong refusal.
        return False

    window = phrase_window(
        index,
        [phrase_id for item in verified for phrase_id in item.phrase_ids],
    )
    window_words = {stem(token.text) for token in window}
    if not (concepts & window_words):
        return False

    # Ground the answer against the supporting passage (±20 s, the same excerpt
    # the judge sees), not just the two quoted sentences: a faithful answer
    # often reuses words the lecturer said a few seconds earlier.
    context_words = content_words(_excerpt(index, verified))
    answer_words = content_words(answer)
    if not answer_words:
        return False
    if len(answer_words & context_words) / len(answer_words) < config.answer_grounding_min:
        return False

    if judge is not None and config.use_judge:
        if not judge(question, _excerpt(index, verified), answer):
            return False
    return True


def _excerpt(
    index: TranscriptIndex, evidence: list[Evidence], padding_ms: int = 20_000
) -> str:
    starts = [item.start_ms for item in evidence if item.start_ms is not None]
    ends = [item.end_ms for item in evidence if item.end_ms is not None]
    if not starts:
        return ""
    low = min(starts) - padding_ms
    high = max(ends or starts) + padding_ms
    return " ".join(
        phrase.text
        for phrase in index.transcript.phrases
        if phrase.end_ms >= low and phrase.start_ms <= high
    )
