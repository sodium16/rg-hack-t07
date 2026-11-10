"""The Verification Engine.

Turns a model's quote into millisecond offsets by locating it in the transcript
index (``04_VERIFICATION_ENGINE.md``), and decides coverage from verified
evidence rather than from the model's opinion. Pure and offline: no Azure call,
no clock, so every rule is unit-testable.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

from app.config import Settings, load_settings
from app.models import Evidence, Transcript
from app.transcript_index import Token, TranscriptIndex, norm

_EPSILON = 1e-9
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class _Span:
    """Inclusive token range, with the score that produced it."""

    first: int
    last: int
    score: float


@dataclass(frozen=True)
class Coverage:
    """Final coverage decision, with a reason when the answer is refused."""

    covered: bool
    reason: str | None = None


def locate(
    quote: str,
    index: TranscriptIndex,
    hint_ms: int | None = None,
    *,
    settings: Settings | None = None,
) -> Evidence:
    """Locate a verbatim-ish quote and return its Evidence.

    Order is exact token match, then a fuzzy sliding window, then failure. A
    failed quote carries no timestamp at all. ``hint_ms`` only breaks ties
    between identical occurrences (lecturers repeat themselves).
    """
    config = settings or load_settings()
    claimed = quote or ""
    quote_tokens = norm(claimed).split()

    if len(quote_tokens) < config.min_quote_tokens:
        # Too short to be a meaningful moment; such quotes match anywhere.
        return _failed(claimed, 0.0)

    if len(quote_tokens) > config.max_quote_tokens:
        return _locate_long(claimed, index, hint_ms, config)

    exact = _exact_spans(index.tokens, quote_tokens)
    if exact:
        return _verified(claimed, index.tokens, _choose(exact, index.tokens, hint_ms), 1.0)

    score, span = _best_window(
        index.tokens, " ".join(quote_tokens), len(quote_tokens), hint_ms
    )
    if span is not None and score >= config.match_threshold:
        return _verified(claimed, index.tokens, span, score)
    return _failed(claimed, score)


def seek_ms(evidence: Evidence, *, settings: Settings | None = None) -> int | None:
    """Where the audio player should jump: start minus a short lead-in."""
    if evidence.start_ms is None:
        return None
    config = settings or load_settings()
    return max(0, evidence.start_ms - config.seek_lead_in_ms)


def decide_covered(
    *,
    quote_verified: bool,
    gate_passes: bool,
    model_claimed_covered: bool | None,
) -> Coverage:
    """The decision table from 04 §5, in one place.

    A model may veto coverage, but it can never grant it: without a verified
    quote and a passing relevance gate the answer is not covered.
    """
    if model_claimed_covered is False:
        return Coverage(False, "model reported the lecture does not cover this")
    if not quote_verified:
        return Coverage(False, "claimed answer not found in transcript")
    if not gate_passes:
        return Coverage(False, "quote does not answer the question")
    return Coverage(True)


def _locate_long(
    claimed: str,
    index: TranscriptIndex,
    hint_ms: int | None,
    config: Settings,
) -> Evidence:
    """Split an over-long quote into locatable pieces and keep the best one."""
    best_verified: Evidence | None = None
    best_any: Evidence | None = None
    for part in _split_quote(claimed, config.max_quote_tokens):
        found = locate(part, index, hint_ms, settings=config)
        if found.verified and (best_verified is None or found.match_score > best_verified.match_score):
            best_verified = found
        if best_any is None or found.match_score > best_any.match_score:
            best_any = found

    best = best_verified or best_any
    if best is None:
        return _failed(claimed, 0.0)
    return dataclasses.replace(best, quote_claimed=claimed)


def _split_quote(quote: str, max_tokens: int) -> list[str]:
    parts: list[str] = []
    for sentence in _SENTENCE_BREAK.split(quote.strip()):
        raw_words = sentence.split()
        if not raw_words:
            continue
        if len(norm(sentence).split()) <= max_tokens:
            parts.append(sentence)
            continue
        for start in range(0, len(raw_words), max_tokens):
            parts.append(" ".join(raw_words[start : start + max_tokens]))

    # A chunk can still normalise to more tokens (hyphenated words split in
    # two). Truncating the normalised form guarantees recursion terminates.
    guarded: list[str] = []
    for part in parts:
        pieces = norm(part).split()
        guarded.append(" ".join(pieces[:max_tokens]) if len(pieces) > max_tokens else part)
    return guarded


def _exact_spans(tokens: tuple[Token, ...], needle: list[str]) -> list[_Span]:
    width = len(needle)
    return [
        _Span(start, start + width - 1, 1.0)
        for start in range(len(tokens) - width + 1)
        if all(tokens[start + offset].text == needle[offset] for offset in range(width))
    ]


def _best_window(
    tokens: tuple[Token, ...],
    quote_text: str,
    width: int,
    hint_ms: int | None,
) -> tuple[float, _Span | None]:
    """Slide windows of width n-2 … n+2 and keep the best-scoring span."""
    lengths = sorted(
        {max(1, width - 2), max(1, width - 1), width, width + 1, width + 2}
    )
    best_score = -1.0
    best_spans: list[_Span] = []

    for length in lengths:
        if length > len(tokens):
            continue
        for start in range(len(tokens) - length + 1):
            window = " ".join(token.text for token in tokens[start : start + length])
            score = fuzz.ratio(quote_text, window) / 100.0
            if score > best_score + _EPSILON:
                best_score = score
                best_spans = [_Span(start, start + length - 1, score)]
            elif abs(score - best_score) <= _EPSILON:
                best_spans.append(_Span(start, start + length - 1, score))

    if not best_spans:
        return 0.0, None
    return best_score, _choose(best_spans, tokens, hint_ms)


def _choose(
    spans: list[_Span], tokens: tuple[Token, ...], hint_ms: int | None
) -> _Span:
    """Earliest occurrence by default; nearest to the hint when one is given."""
    if hint_ms is None:
        return min(spans, key=lambda span: span.first)
    return min(spans, key=lambda span: abs(tokens[span.first].start_ms - hint_ms))


def _phrase_ids(tokens: list[Token]) -> list[int]:
    ids: list[int] = []
    for token in tokens:
        if not ids or ids[-1] != token.phrase_id:
            ids.append(token.phrase_id)
    return ids


def _join_raw(tokens: list[Token]) -> str:
    """Reconstruct the transcript's own spelling, without duplicated words."""
    parts: list[str] = []
    for token in tokens:
        if not parts or parts[-1] != token.raw:
            parts.append(token.raw)
    return " ".join(parts)


def _verified(claimed: str, tokens: tuple[Token, ...], span: _Span, score: float) -> Evidence:
    matched = list(tokens[span.first : span.last + 1])
    return Evidence(
        quote_claimed=claimed,
        quote_matched=_join_raw(matched),
        start_ms=matched[0].start_ms,
        end_ms=matched[-1].end_ms,
        phrase_ids=_phrase_ids(matched),
        match_score=round(score, 4),
        verified=True,
    )


def _failed(claimed: str, score: float) -> Evidence:
    return Evidence(
        quote_claimed=claimed,
        quote_matched=None,
        start_ms=None,
        end_ms=None,
        phrase_ids=[],
        match_score=round(max(score, 0.0), 4),
        verified=False,
    )


def main(argv: list[str] | None = None) -> int:
    """Print the Evidence for one quote, so the algorithm is inspectable."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("quote", help="the quote a model claims is in the transcript")
    parser.add_argument(
        "--transcript",
        default="tests/fixtures/transcript_sample.json",
        help="fixture or cached transcript JSON",
    )
    parser.add_argument("--hint-ms", type=int, default=None)
    args = parser.parse_args(argv)

    index = TranscriptIndex.build(Transcript.from_json_file(Path(args.transcript)))
    evidence = locate(args.quote, index, args.hint_ms)
    print(json.dumps(dataclasses.asdict(evidence), indent=2))
    target = seek_ms(evidence)
    print(f"seek to: {target if target is not None else 'n/a'} ms")
    return 0 if evidence.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
