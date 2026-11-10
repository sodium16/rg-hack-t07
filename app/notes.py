"""Revision notes and the five key terms.

The model drafts; this module decides. Every bullet and term must carry a quote
the Verification Engine can locate, key terms must literally appear in the
transcript, and the honest counts go into the Verification Report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import Settings, load_settings
from app.language import content_words, stem
from app.llm import ChatModel
from app.models import (
    KeyTerm,
    KeyTermCounts,
    NoteBullet,
    NoteSection,
    Notes,
    NotesCounts,
    VerificationReport,
)
from app.prompts import (
    SHARED_SYSTEM,
    key_term_retry_prompt,
    notes_prompt,
    timestamped_transcript,
)
from app.transcript_index import TranscriptIndex, contains_term, phrase_window, term_present
from app.verify import locate

REQUIRED_KEY_TERMS = 5


@dataclass
class NotesResult:
    notes: Notes
    key_terms: list[KeyTerm]
    report: VerificationReport
    usage: dict[str, int] = field(default_factory=dict)


def generate_notes(
    index: TranscriptIndex,
    model: ChatModel,
    *,
    settings: Settings | None = None,
) -> NotesResult:
    config = settings or load_settings()
    transcript_text = timestamped_transcript(index.transcript)

    first = model.complete_json(
        SHARED_SYSTEM,
        notes_prompt(transcript_text),
        max_tokens=config.llm_max_tokens,
    )
    payload = first.data
    usage = _sum_usage({}, first.usage)

    notes, generated_bullets = _build_notes(payload.get("notes") or {}, index, config)
    notes = _trim_to_word_cap(notes, config.max_notes_words)

    candidates = list(payload.get("key_term_candidates") or [])
    accepted, rejected = _select_terms(candidates, index, config, accepted_terms=[])

    attempts = 0
    while len(accepted) < REQUIRED_KEY_TERMS and attempts < config.key_term_attempts:
        attempts += 1
        retry = model.complete_json(
            SHARED_SYSTEM,
            key_term_retry_prompt(
                transcript_text,
                rejected,
                [term.term for _, term in accepted],
                REQUIRED_KEY_TERMS - len(accepted),
            ),
            max_tokens=config.llm_max_tokens,
        )
        usage = _sum_usage(usage, retry.usage)
        extra_candidates = list(retry.data.get("key_term_candidates") or [])
        candidates.extend(extra_candidates)
        more, rejected = _select_terms(
            extra_candidates,
            index,
            config,
            accepted_terms=[term.term for _, term in accepted],
        )
        accepted.extend(more)

    ordered = sorted(
        accepted,
        key=lambda pair: (-pair[0], pair[1].evidence[0].start_ms or 0),
    )
    key_terms = [term for _, term in ordered[:REQUIRED_KEY_TERMS]]

    displayed_bullets = sum(len(section.bullets) for section in notes.sections)
    report = VerificationReport(
        notes=NotesCounts(
            generated=generated_bullets,
            verified=displayed_bullets,
            removed=max(generated_bullets - displayed_bullets, 0),
        ),
        key_terms=KeyTermCounts(
            generated=len(candidates),
            verified=len(key_terms),
            removed=max(len(candidates) - len(key_terms), 0),
            regenerated=attempts > 0,
        ),
    )
    return NotesResult(notes=notes, key_terms=key_terms, report=report, usage=usage)


def _build_notes(
    payload: dict, index: TranscriptIndex, config: Settings
) -> tuple[Notes, int]:
    title = str(payload.get("title") or "Revision notes").strip()
    overview = str(payload.get("overview") or "").strip()
    sections: list[NoteSection] = []
    generated = 0

    for raw_section in payload.get("sections") or []:
        heading = str(raw_section.get("heading") or "").strip()
        bullets: list[NoteBullet] = []
        for raw_bullet in raw_section.get("bullets") or []:
            text = str(raw_bullet.get("text") or "").strip()
            if not text:
                continue
            generated += 1
            quotes = [
                str(quote).strip()
                for quote in raw_bullet.get("evidence_quotes") or []
                if str(quote).strip()
            ]
            verified = [
                evidence
                for evidence in (locate(quote, index, settings=config) for quote in quotes)
                if evidence.verified
            ]
            if verified:
                bullets.append(NoteBullet(text=text, evidence=verified))
        if heading and len(bullets) >= 2:
            sections.append(NoteSection(heading=heading, bullets=bullets))

    return Notes(title=title, overview=overview, sections=sections), generated


def _trim_to_word_cap(notes: Notes, cap: int) -> Notes:
    """Keep the notes to one page by dropping whole bullets, never mid-sentence."""
    while notes.word_count > cap:
        trimmable = [section for section in notes.sections if len(section.bullets) > 2]
        if not trimmable:
            break
        longest = max(trimmable, key=lambda section: len(section.bullets))
        longest.bullets.pop()

    while notes.word_count > cap and len(notes.sections) > 1:
        notes.sections.pop()
    return notes


def _select_terms(
    candidates: list[dict],
    index: TranscriptIndex,
    config: Settings,
    *,
    accepted_terms: list[str],
) -> tuple[list[tuple[int, KeyTerm]], dict[str, str]]:
    accepted: list[tuple[int, KeyTerm]] = []
    rejected: dict[str, str] = {}
    seen = {term.lower() for term in accepted_terms}

    for candidate in candidates:
        term_text = str(candidate.get("term") or "").strip()
        definition = str(candidate.get("definition") or "").strip()
        quote = str(candidate.get("evidence_quote") or "").strip()
        if not term_text or not definition or not quote:
            continue
        if term_text.lower() in seen:
            continue

        reason = _rejection_reason(term_text, definition, quote, index, config)
        if reason:
            rejected[term_text] = reason
            continue

        evidence = locate(quote, index, settings=config)
        accepted.append(
            (
                int(candidate.get("importance") or 0),
                KeyTerm(
                    term=term_text,
                    definition=definition,
                    evidence=[evidence],
                    term_found_in_transcript=True,
                    verified=True,
                ),
            )
        )
        seen.add(term_text.lower())

    return accepted, rejected


def _rejection_reason(
    term: str,
    definition: str,
    quote: str,
    index: TranscriptIndex,
    config: Settings,
) -> str | None:
    if not term_present(index, term):
        return "term does not appear in the transcript"
    evidence = locate(quote, index, settings=config)
    if not evidence.verified:
        return "evidence quote was not found in the transcript"
    window = phrase_window(index, evidence.phrase_ids)
    if not contains_term(window, term):
        return "evidence quote does not mention the term"
    if not _definition_grounded(definition, index, evidence.phrase_ids, config):
        return "definition is not built from the lecture's own words"
    return None


def _definition_grounded(
    definition: str, index: TranscriptIndex, phrase_ids: list[int], config: Settings
) -> bool:
    words = content_words(definition)
    if not words:
        return False
    context = {stem(token.text) for token in phrase_window(index, phrase_ids)}
    return len(words & context) / len(words) >= config.definition_overlap_min


def _sum_usage(total: dict[str, int], usage: dict) -> dict[str, int]:
    merged = dict(total)
    for key, value in (usage or {}).items():
        if isinstance(value, int):
            merged[key] = merged.get(key, 0) + value
    return merged
