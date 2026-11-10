"""Run the whole pipeline on one audio file from the terminal.

    python -m app.pipeline data/samples/lecture.m4a
    python -m app.pipeline data/samples/lecture.m4a -q "What is gradient descent?"

Every timestamp printed here was computed by the Verification Engine from the
transcript; none of them came from the model. Anything that fails to verify is
dropped and counted in the report at the end.
"""

from __future__ import annotations

import argparse

from app.audio import AudioValidationError, load_audio
from app.config import MissingConfigError, load_settings
from app.llm import FoundryClient, LLMError
from app.models import QACounts, VerificationReport
from app.notes import generate_notes
from app.qa import REFUSAL_TEXT, answer_question
from app.speech import SpeechError, transcribe_with_env
from app.transcript_index import TranscriptIndex


def _stamp(ms: int | None) -> str:
    """Milliseconds as ``m:ss.mmm``; ``--:--`` when there is no timestamp."""
    if ms is None:
        return "--:--"
    minutes, rest = divmod(int(ms), 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def _print_transcript(index: TranscriptIndex) -> None:
    for phrase in index.transcript.phrases:
        print(f"  [{_stamp(phrase.start_ms)}] {phrase.text}")


def _print_notes(result) -> None:
    notes = result.notes
    print(f"\n== NOTES: {notes.title} ==")
    if notes.overview:
        print(notes.overview)
    for section in notes.sections:
        print(f"\n{section.heading}")
        for bullet in section.bullets:
            first = bullet.evidence[0].start_ms if bullet.evidence else None
            print(f"  - {bullet.text}  [{_stamp(first)}]")

    print(f"\n== KEY TERMS ({len(result.key_terms)}/{5}) ==")
    for term in result.key_terms:
        first = term.evidence[0].start_ms if term.evidence else None
        print(f"  * {term.term} [{_stamp(first)}]: {term.definition}")

    report: VerificationReport = result.report
    print(
        f"\nVerification: notes {report.notes.verified}/{report.notes.generated} kept"
        f" ({report.notes.removed} dropped),"
        f" key terms {report.key_terms.verified}/{report.key_terms.generated} kept"
        f" ({report.key_terms.removed} dropped"
        f"{', regenerated' if report.key_terms.regenerated else ''})"
    )


def _ask(questions: list[str], index: TranscriptIndex, model: FoundryClient) -> QACounts:
    counts = QACounts()
    for question in questions:
        counts.asked += 1
        result = answer_question(question, index, model)
        print(f"\nQ: {question}")
        if result.covered:
            counts.answered += 1
            print(f"A: {result.answer}")
            print(f"   timestamp {_stamp(result.primary_timestamp_ms)}")
            for item in result.evidence:
                print(f"   [{_stamp(item.start_ms)}] {item.quote_matched or item.quote_claimed}")
        else:
            counts.refused += 1
            print(f"A: {REFUSAL_TEXT}")
            print(f"   reason: {result.refusal_reason}")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "audio", help="audio file: mp3, wav, m4a, mp4, ogg, flac or webm"
    )
    parser.add_argument(
        "-q",
        "--question",
        action="append",
        default=[],
        help="question to answer; repeat the flag for more than one",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="ignore the Speech cache and call Azure again"
    )
    parser.add_argument(
        "--no-notes", action="store_true", help="skip the notes and key-term stage"
    )
    args = parser.parse_args(argv)

    config = load_settings()

    try:
        info = load_audio(args.audio, settings=config)
    except AudioValidationError as error:
        print(f"Upload problem: {error}")
        return 2

    size_mb = info.size_bytes / (1024 * 1024)
    print(f"Audio: {info.path.name} ({size_mb:.1f} MB, {info.duration_ms / 1000:.1f} s)")
    print(f"SHA-256: {info.sha256}")

    try:
        speech = transcribe_with_env(info.path, refresh=args.refresh)
    except (MissingConfigError, SpeechError) as error:
        print(f"Transcription failed: {error}")
        return 1

    index = TranscriptIndex.build(speech.transcript)
    source = "cache" if speech.cached else "new Speech call"
    print(
        f"Transcript: {len(speech.transcript.phrases)} phrases,"
        f" {len(index.tokens)} words, {_stamp(speech.transcript.duration_ms)} ({source})"
    )
    _print_transcript(index)

    model: FoundryClient | None = None
    try:
        model = FoundryClient.from_env()
        if not args.no_notes:
            _print_notes(generate_notes(index, model, settings=config))
        if args.question:
            counts = _ask(args.question, index, model)
            print(
                f"\nQ&A: asked {counts.asked}, answered {counts.answered},"
                f" refused {counts.refused}"
            )
    except (MissingConfigError, LLMError) as error:
        print(f"\nModel stage failed: {error}")
        if not args.question and args.no_notes:
            return 1
        # A partial result (transcript only) beats a blank page.
        print("The transcript above is still valid; only the model stage was skipped.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
