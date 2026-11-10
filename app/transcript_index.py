"""Normalisation and the token index over a transcript.

This is step 1 of ``04_VERIFICATION_ENGINE.md``: flatten the phrases into a
single stream of normalised tokens, each carrying millisecond offsets, so a
model's quote can be located without ever trusting a timestamp the model
produced.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.models import Transcript, TranscriptPhrase

# Characters NFKC does not fold for us.
_QUOTE_FOLD = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
}
_DASH_CHARS = frozenset("\u2010\u2011\u2012\u2013\u2014\u2015\u2212")

_WHITESPACE = re.compile(r"\s+")


def norm(text: str) -> str:
    """Normalise text identically on both sides of a match.

    NFKC, lowercase, curly quotes folded, dashes and punctuation become
    spaces, hyphens become spaces, but apostrophes inside words and decimal
    points inside numbers survive so "lecture's" and "3.14" stay one token.
    Applied to transcripts and to model quotes alike (04 §1).
    """
    if not text:
        return ""
    folded = unicodedata.normalize("NFKC", text).lower()
    folded = "".join(_QUOTE_FOLD.get(char, char) for char in folded)

    characters: list[str] = []
    for position, char in enumerate(folded):
        previous = folded[position - 1] if position else ""
        following = folded[position + 1] if position + 1 < len(folded) else ""
        if char in _DASH_CHARS or char == "-":
            characters.append(" ")
        elif char == "'":
            characters.append("'" if previous.isalnum() and following.isalnum() else " ")
        elif char == ".":
            characters.append("." if previous.isdigit() and following.isdigit() else " ")
        elif char.isalnum():
            characters.append(char)
        else:
            characters.append(" ")
    return _WHITESPACE.sub(" ", "".join(characters)).strip()


@dataclass(frozen=True)
class Token:
    """One searchable unit, with the surface text kept for display."""

    text: str  # normalised
    raw: str  # as it appears in the transcript
    start_ms: int
    end_ms: int
    phrase_id: int


def _tokens_for_phrase(phrase: TranscriptPhrase) -> list[Token]:
    if phrase.words:
        tokens = [
            Token(
                text=norm(word.text),
                raw=word.text,
                start_ms=word.start_ms,
                end_ms=word.end_ms,
                phrase_id=phrase.id,
            )
            for word in phrase.words
            if norm(word.text)
        ]
        if tokens:
            return tokens
    return _interpolate(phrase)


def _interpolate(phrase: TranscriptPhrase) -> list[Token]:
    """Spread the phrase duration across tokens by character length.

    Used when Speech returns no word offsets (04 §1). Word offsets are
    preferred because they are exact; this is the documented fallback.
    """
    pairs: list[tuple[str, str]] = []
    for raw_word in phrase.text.split():
        for piece in norm(raw_word).split():
            pairs.append((piece, raw_word))
    if not pairs:
        return []

    duration_ms = max(phrase.end_ms - phrase.start_ms, 0)
    total_characters = sum(len(piece) for piece, _ in pairs) or 1

    boundaries = [0]
    cumulative = 0
    for piece, _ in pairs:
        cumulative += len(piece)
        boundaries.append(cumulative)

    tokens = [
        Token(
            text=piece,
            raw=raw_word,
            start_ms=phrase.start_ms + round(duration_ms * boundaries[index] / total_characters),
            end_ms=phrase.start_ms + round(duration_ms * boundaries[index + 1] / total_characters),
            phrase_id=phrase.id,
        )
        for index, (piece, raw_word) in enumerate(pairs)
    ]
    # Floating-point rounding must never leave the phrase short of its end.
    last = tokens[-1]
    tokens[-1] = Token(last.text, last.raw, last.start_ms, phrase.end_ms, last.phrase_id)
    return tokens


@dataclass(frozen=True)
class TranscriptIndex:
    """Searchable view of one transcript: phrases kept, tokens flattened."""

    transcript: Transcript
    tokens: tuple[Token, ...]

    @classmethod
    def build(cls, transcript: Transcript) -> "TranscriptIndex":
        tokens: list[Token] = []
        for phrase in sorted(transcript.phrases, key=lambda item: (item.start_ms, item.id)):
            tokens.extend(_tokens_for_phrase(phrase))
        return cls(transcript=transcript, tokens=tuple(tokens))

    @property
    def norm_text(self) -> str:
        """The normalised transcript, used for key-term presence checks."""
        return " ".join(token.text for token in self.tokens)


def _token_run_positions(tokens: tuple[Token, ...], needle: list[str]) -> list[int]:
    """Start indices where ``needle`` appears as a contiguous token run."""
    if not needle:
        return []
    width = len(needle)
    return [
        start
        for start in range(len(tokens) - width + 1)
        if all(tokens[start + offset].text == needle[offset] for offset in range(width))
    ]


def _last_token_variants(word: str) -> set[str]:
    variants = {word}
    if word.endswith("ies") and len(word) > 3:
        variants.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 2:
        variants.add(word[:-2])
    if word.endswith("s") and len(word) > 1:
        variants.add(word[:-1])
    else:
        variants.add(word + "s")
        variants.add(word + "es")
    return variants


def term_variants(term: str) -> set[str]:
    """Accept the plural and hyphen/no-space variants 04 §4 requires."""
    base = norm(term)
    if not base:
        return set()
    words = base.split()
    variants = {base}
    for alternative in _last_token_variants(words[-1]):
        variants.add(" ".join(words[:-1] + [alternative]))
    variants.add("".join(words))
    return {variant for variant in variants if variant}


def contains_term(tokens: tuple[Token, ...], term: str) -> bool:
    """True when the term appears in this token stream (any variant)."""
    for variant in term_variants(term):
        parts = variant.split()
        if _token_run_positions(tokens, parts):
            return True
        if len(parts) > 1:
            compact = "".join(parts)
            if any(token.text == compact for token in tokens):
                return True
    return False


def term_present(index: TranscriptIndex, term: str) -> bool:
    """True when the term literally appears in the transcript.

    This is the A3 key-term assertion: no term is shown unless this passes.
    """
    return contains_term(index.tokens, term)


def phrase_window(
    index: TranscriptIndex, phrase_ids: list[int], radius: int = 1
) -> tuple[Token, ...]:
    """Tokens of the given phrases plus ``radius`` neighbours on each side."""
    wanted: set[int] = set()
    for phrase_id in phrase_ids:
        wanted.update(range(phrase_id - radius, phrase_id + radius + 1))
    return tuple(token for token in index.tokens if token.phrase_id in wanted)
