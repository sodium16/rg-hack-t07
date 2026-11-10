"""Data contracts shared by the pipeline.

These mirror ``02_ARCHITECTURE.md``. Fields are stable: extend them, never
rename or repurpose one, because the verification report, the eval and the UI
all read the same objects. ``Evidence`` is produced only by the Verification
Engine, so any timestamp on it was computed from the transcript, not taken from
a model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Word:
    """One word with its offsets, when Speech returns word-level timestamps."""

    text: str
    start_ms: int
    end_ms: int


@dataclass
class TranscriptPhrase:
    """One phrase from Azure AI Speech, in the project's contract."""

    id: int
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None
    words: list[Word] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TranscriptPhrase":
        confidence = payload.get("confidence")
        return cls(
            id=int(payload["id"]),
            start_ms=int(payload["start_ms"]),
            end_ms=int(payload["end_ms"]),
            text=str(payload["text"]),
            confidence=None if confidence is None else float(confidence),
            words=[
                Word(
                    text=str(item["text"]),
                    start_ms=int(item["start_ms"]),
                    end_ms=int(item["end_ms"]),
                )
                for item in payload.get("words") or []
            ],
        )


@dataclass
class Transcript:
    """A whole transcription, ordered by start time."""

    audio_id: str
    duration_ms: int
    locale: str
    phrases: list[TranscriptPhrase]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Transcript":
        phrases = [TranscriptPhrase.from_dict(item) for item in payload.get("phrases") or []]
        phrases.sort(key=lambda phrase: (phrase.start_ms, phrase.id))
        return cls(
            audio_id=str(payload["audio_id"]),
            duration_ms=int(payload["duration_ms"]),
            locale=str(payload.get("locale", "en-US")),
            phrases=phrases,
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "Transcript":
        with Path(path).open(encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))


@dataclass(frozen=True)
class Evidence:
    """The Verification Engine's judgement on one quote.

    ``quote_claimed`` is what the model said; ``quote_matched`` is the text as
    it actually appears in the transcript. ``start_ms``/``end_ms`` are None
    whenever the quote did not verify — there is no timestamp without evidence.
    """

    quote_claimed: str
    quote_matched: str | None
    start_ms: int | None
    end_ms: int | None
    phrase_ids: list[int]
    match_score: float
    verified: bool


@dataclass
class NoteBullet:
    """One revision point. ``evidence`` is never empty for a shown bullet."""

    text: str
    evidence: list[Evidence]
    verified: bool = True


@dataclass
class NoteSection:
    heading: str
    bullets: list[NoteBullet]


@dataclass
class Notes:
    title: str
    overview: str
    sections: list[NoteSection]

    @property
    def word_count(self) -> int:
        parts = [self.title, self.overview]
        for section in self.sections:
            parts.append(section.heading)
            parts.extend(bullet.text for bullet in section.bullets)
        return sum(len(part.split()) for part in parts)


@dataclass
class KeyTerm:
    """A term the lecturer actually used, with the lecture's own definition."""

    term: str
    definition: str
    evidence: list[Evidence]
    term_found_in_transcript: bool
    verified: bool


@dataclass
class QAResult:
    """The final answer shape. ``covered`` is post-verification, never the model's claim."""

    question: str
    covered: bool
    answer: str
    evidence: list[Evidence]
    primary_timestamp_ms: int | None
    refusal_reason: str | None
    model_claimed_covered: bool | None
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class NotesCounts:
    generated: int = 0
    verified: int = 0
    removed: int = 0


@dataclass
class KeyTermCounts:
    generated: int = 0
    verified: int = 0
    removed: int = 0
    regenerated: bool = False


@dataclass
class QACounts:
    asked: int = 0
    answered: int = 0
    refused: int = 0


@dataclass
class VerificationReport:
    """Every number here is derived from the objects above, never typed in."""

    notes: NotesCounts = field(default_factory=NotesCounts)
    key_terms: KeyTermCounts = field(default_factory=KeyTermCounts)
    qa: QACounts = field(default_factory=QACounts)
