"""Evaluate A1, A2 and A3 against gold data and write the Evidence Sheet numbers.

    python eval/run_eval.py --clip data/samples/clip1.m4a --all
    python eval/run_eval.py --transcript data/cache/<sha>.speech.json \\
        --a1 --a1-script eval/clip1_a1_2min.txt

Gold data lives only here (never in the app). Every number printed is computed
from the transcript and the gold file; nothing is typed in by hand.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_settings  # noqa: E402
from app.llm import FoundryClient  # noqa: E402
from app.models import QAResult, Transcript  # noqa: E402
from app.notes import generate_notes  # noqa: E402
from app.qa import answer_question  # noqa: E402
from app.speech import parse_transcription, transcribe_with_env  # noqa: E402
from app.transcript_index import TranscriptIndex, norm, term_present  # noqa: E402

WER_TARGET = 0.10
TIMESTAMP_TOLERANCE_MS = 5_000
NEAR_MISS_TARGET = 0.90


class EvalError(RuntimeError):
    """A section cannot run; the message says what is missing."""


@dataclass
class TranscriptBundle:
    transcript: Transcript
    index: TranscriptIndex
    source: str


def load_transcript(path: Path) -> Transcript:
    """Accept either a ``Transcript`` JSON or a raw Speech response."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "audio_id" in payload and "phrases" in payload:
        return Transcript.from_dict(payload)
    if "phrases" in payload:
        return parse_transcription(payload, audio_id=path.stem.split(".")[0])
    raise EvalError(f"{path.name} is not a transcript or a Speech response.")


def load_bundle(*, clip: Path | None, transcript_path: Path | None, refresh: bool) -> TranscriptBundle:
    if transcript_path is not None:
        transcript = load_transcript(transcript_path)
        source = f"transcript file {transcript_path.name}"
    elif clip is not None:
        result = transcribe_with_env(clip, refresh=refresh)
        transcript = result.transcript
        source = f"{clip.name} ({'cached' if result.cached else 'fresh Speech call'})"
    else:
        raise EvalError("Pass --clip <audio> or --transcript <json>.")
    return TranscriptBundle(transcript=transcript, index=TranscriptIndex.build(transcript), source=source)


def normalise_text(text: str) -> str:
    """Same normalisation on both sides of WER: lower case, no punctuation."""
    return " ".join(norm(text or "").split())


def wer_stats(reference: str, hypothesis: str) -> dict[str, Any]:
    """WER plus error counts, computed with ``jiwer``."""
    try:
        import jiwer
    except ModuleNotFoundError as error:  # pragma: no cover - depends on env
        raise EvalError(
            "jiwer is not installed. Run: .venv/Scripts/python.exe -m pip install jiwer"
        ) from error

    ref = normalise_text(reference)
    hyp = normalise_text(hypothesis)
    if not ref:
        raise EvalError("The reference text is empty.")
    output = jiwer.process_words(ref, hyp)
    return {
        "wer": round(float(output.wer), 4),
        "substitutions": int(output.substitutions),
        "insertions": int(output.insertions),
        "deletions": int(output.deletions),
        "hits": int(output.hits),
        "reference_words": len(ref.split()),
        "hypothesis_words": len(hyp.split()),
    }


def _windows(gold: dict[str, Any]) -> list[list[int]]:
    windows = gold.get("gold_windows_ms") or []
    return [list(window) for window in windows if len(window) == 2]


def timestamp_error(primary_ms: int | None, windows: Iterable[Iterable[int]]) -> dict[str, Any]:
    """Distance to the nearest gold window; inside a window counts as zero."""
    pairs = [list(window) for window in windows]
    if primary_ms is None:
        return {"within_5s": False, "error_ms": None}
    if not pairs:
        return {"within_5s": False, "error_ms": None}
    best: int | None = None
    for start, end in pairs:
        if start <= primary_ms <= end:
            best = 0
            break
        distance = min(abs(primary_ms - start), abs(primary_ms - end))
        best = distance if best is None else min(best, distance)
    assert best is not None
    return {"within_5s": best <= TIMESTAMP_TOLERANCE_MS, "error_ms": best}


def answer_is_correct(answer: str, must_contain_any: Iterable[str]) -> bool:
    wanted = [normalise_text(item) for item in must_contain_any if item]
    if not wanted:
        return True
    text = normalise_text(answer)
    return any(item in text for item in wanted)


def run_a1(bundle: TranscriptBundle, script: Path, window: tuple[int, int] | None) -> dict[str, Any]:
    if not script.is_file():
        raise EvalError(f"A1 reference text not found: {script}")
    reference = script.read_text(encoding="utf-8")

    phrases = bundle.transcript.phrases
    if window is not None:
        start_ms, end_ms = window[0] * 1000, window[1] * 1000
        phrases = [p for p in phrases if start_ms <= p.start_ms < end_ms]

    hypothesis = " ".join(phrase.text for phrase in phrases)
    stats = wer_stats(reference, hypothesis)
    stats["phrases"] = len(phrases)
    stats["timestamps_monotonic"] = all(
        later.start_ms >= earlier.start_ms for earlier, later in zip(phrases, phrases[1:])
    )
    stats["timestamps_within_audio"] = all(
        phrase.start_ms <= bundle.transcript.duration_ms for phrase in phrases
    )
    stats["passed"] = stats["wer"] <= WER_TARGET and stats["timestamps_monotonic"]
    stats["window_seconds"] = list(window) if window else None
    return stats


def _ask(question: str, bundle: TranscriptBundle, model: FoundryClient) -> QAResult:
    return answer_question(question, bundle.index, model)


def run_a2(gold: dict[str, Any], bundle: TranscriptBundle, model: FoundryClient) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in gold.get("covered") or []:
        result = _ask(item["question"], bundle, model)
        window = _windows(item)
        timing = timestamp_error(result.primary_timestamp_ms, window)
        rows.append(
            {
                "id": item.get("id"),
                "question": item["question"],
                "covered": result.covered,
                "answer": result.answer,
                "primary_timestamp_ms": result.primary_timestamp_ms,
                "gold_windows_ms": window,
                "within_5s": timing["within_5s"],
                "error_ms": timing["error_ms"],
                "answer_correct": answer_is_correct(
                    result.answer, item.get("must_contain_any") or []
                ),
                "refusal_reason": result.refusal_reason,
            }
        )

    answered = [row for row in rows if row["covered"]]
    within = [row for row in answered if row["within_5s"]]
    errors = [row["error_ms"] for row in within]
    summary = {
        "questions": len(rows),
        "answered": len(answered),
        "within_5s": len(within),
        "within_5s_rate": round(len(within) / len(rows), 4) if rows else 0.0,
        "median_error_ms": sorted(errors)[len(errors) // 2] if errors else None,
        "max_error_ms": max(errors) if errors else None,
        "correct_answers": sum(1 for row in answered if row["answer_correct"]),
        "model_claimed_covered_but_refused": sum(
            1 for row in rows if not row["covered"] and row["refusal_reason"] == "quote does not answer the question"
        ),
    }
    summary["passed"] = bool(rows) and summary["within_5s_rate"] >= 0.90
    return {"rows": rows, "summary": summary}


def run_a3_notcovered(gold: dict[str, Any], bundle: TranscriptBundle, model: FoundryClient) -> dict[str, Any]:
    categories = ("not_covered_unrelated", "not_covered_near_miss", "leading_false_premise")
    rows: list[dict[str, Any]] = []
    per_category: dict[str, dict[str, Any]] = {}

    for category in categories:
        items = gold.get(category) or []
        refused = 0
        for item in items:
            result = _ask(item["question"], bundle, model)
            refused += int(not result.covered)
            rows.append(
                {
                    "id": item.get("id"),
                    "category": category,
                    "question": item["question"],
                    "covered": result.covered,
                    "answer": result.answer,
                    "refusal_reason": result.refusal_reason,
                }
            )
        per_category[category] = {
            "questions": len(items),
            "refused": refused,
            "rate": round(refused / len(items), 4) if items else 0.0,
            "passed": (refused == len(items)) if category != "not_covered_near_miss" else (
                bool(items) and refused / len(items) >= NEAR_MISS_TARGET
            ),
        }

    passed = all(entry["passed"] for entry in per_category.values() if entry["questions"])
    return {"rows": rows, "by_category": per_category, "passed": passed}


def run_a3_keyterms(bundle: TranscriptBundle, model: FoundryClient) -> dict[str, Any]:
    notes = generate_notes(bundle.index, model)
    rows = []
    for term in notes.key_terms:
        present = term_present(bundle.index, term.term)
        rows.append(
            {
                "term": term.term,
                "present_in_transcript": present,
                "timestamp_ms": term.evidence[0].start_ms if term.evidence else None,
                "definition": term.definition,
            }
        )
    summary = {
        "terms": len(rows),
        "all_present": all(row["present_in_transcript"] for row in rows),
        "notes_verified": notes.report.notes.verified,
        "notes_generated": notes.report.notes.generated,
        "terms_dropped": notes.report.key_terms.removed,
        "regenerated": notes.report.key_terms.regenerated,
        "usage": notes.usage,
    }
    summary["passed"] = summary["terms"] == 5 and summary["all_present"]
    return {"terms": rows, "summary": summary}


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _verdict(passed: bool | None) -> str:
    if passed is None:
        return "not run"
    return "PASS" if passed else "FAIL"


def write_summary(results_dir: Path, results: dict[str, dict[str, Any]], source: str) -> Path:
    lines = ["# Evaluation summary", "", f"Transcript source: {source}", ""]
    lines.append("| Test | Metric | Result | Verdict |")
    lines.append("|---|---|---|---|")

    a1 = results.get("a1")
    if a1:
        lines.append(
            f"| A1 | WER | {a1['wer'] * 100:.2f}% (S{a1['substitutions']} "
            f"I{a1['insertions']} D{a1['deletions']}) | {_verdict(a1['passed'])} |"
        )
        lines.append(
            f"| A1 | timestamps monotonic | {a1['timestamps_monotonic']} | "
            f"{_verdict(a1['timestamps_monotonic'])} |"
        )

    a2 = results.get("a2")
    if a2:
        summary = a2["summary"]
        lines.append(
            f"| A2 | within {TIMESTAMP_TOLERANCE_MS // 1000}s | "
            f"{summary['within_5s']}/{summary['questions']} "
            f"({summary['within_5s_rate'] * 100:.1f}%) | {_verdict(summary['passed'])} |"
        )
        lines.append(
            f"| A2 | correct answers | {summary['correct_answers']}/{summary['answered']} | "
            f"{_verdict(summary['correct_answers'] == summary['answered'] and bool(summary['answered']))} |"
        )

    a3 = results.get("a3_notcovered")
    if a3:
        for category, entry in a3["by_category"].items():
            lines.append(
                f"| A3 | {category} | {entry['refused']}/{entry['questions']} refused | "
                f"{_verdict(entry['passed'])} |"
            )

    terms = results.get("a3_keyterms")
    if terms:
        summary = terms["summary"]
        lines.append(
            f"| A3 | key terms present | {summary['terms']}/5 | {_verdict(summary['passed'])} |"
        )

    lines += [
        "",
        "Targets: A1 WER <= 10%; A2 >= 90% of covered questions within "
        f"+/-{TIMESTAMP_TOLERANCE_MS // 1000}s; A3 100% unrelated refused, "
        f">= {int(NEAR_MISS_TARGET * 100)}% near-miss refused, 100% key terms present.",
        "",
        "Report misses honestly in the Evidence Sheet and say what changed.",
    ]

    path = results_dir / "summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--clip", type=Path, help="audio file to transcribe (cached by SHA-256)")
    parser.add_argument("--transcript", type=Path, help="transcript or Speech JSON to evaluate instead")
    parser.add_argument("--gold", type=Path, default=PROJECT_ROOT / "eval" / "qa_gold.json")
    parser.add_argument("--a1-script", type=Path, default=PROJECT_ROOT / "eval" / "clip1_a1_2min.txt")
    parser.add_argument(
        "--a1-range",
        nargs=2,
        type=int,
        metavar=("START_S", "END_S"),
        help="evaluate only this span of the clip for A1",
    )
    parser.add_argument("--a1", action="store_true", help="run the WER test")
    parser.add_argument("--a2", action="store_true", help="run the covered-question timestamp test")
    parser.add_argument("--a3", action="store_true", help="run the not-covered and key-term tests")
    parser.add_argument("--all", action="store_true", help="run every section")
    parser.add_argument("--refresh", action="store_true", help="ignore the Speech cache")
    parser.add_argument(
        "--results-dir", type=Path, default=PROJECT_ROOT / "eval" / "results"
    )
    args = parser.parse_args(argv)

    run_all = args.all or not (args.a1 or args.a2 or args.a3)
    config = load_settings()

    try:
        bundle = load_bundle(clip=args.clip, transcript_path=args.transcript, refresh=args.refresh)
    except EvalError as error:
        print(f"error: {error}")
        return 2

    print(f"transcript: {bundle.source}")
    print(
        f"  {len(bundle.transcript.phrases)} phrases, "
        f"{bundle.transcript.duration_ms / 1000:.1f} s"
    )

    results: dict[str, dict[str, Any]] = {}
    failures: list[str] = []

    if run_all or args.a1:
        try:
            results["a1"] = run_a1(
                bundle, args.a1_script, tuple(args.a1_range) if args.a1_range else None
            )
        except EvalError as error:
            print(f"A1 error: {error}")
            failures.append("A1")

    needs_model = run_all or args.a2 or args.a3
    if needs_model:
        gold_path: Path = args.gold
        if not gold_path.is_file():
            print(f"error: gold file not found: {gold_path}")
            return 2
        gold = json.loads(gold_path.read_text(encoding="utf-8"))

        try:
            model = FoundryClient.from_env()
        except Exception as error:  # MissingConfigError and friends
            print(f"error: model client unavailable: {error}")
            return 2

        if run_all or args.a2:
            print("A2: asking covered questions…")
            results["a2"] = run_a2(gold, bundle, model)
        if run_all or args.a3:
            print("A3: asking unmatched questions…")
            results["a3_notcovered"] = run_a3_notcovered(gold, bundle, model)
            print("A3: checking key terms…")
            results["a3_keyterms"] = run_a3_keyterms(bundle, model)

    files = {
        "a1": "a1_wer.json",
        "a2": "a2_timestamps.json",
        "a3_notcovered": "a3_notcovered.json",
        "a3_keyterms": "a3_keyterms.json",
    }
    for key, name in files.items():
        if key in results:
            _write(args.results_dir / name, results[key])

    summary_path = write_summary(args.results_dir, results, bundle.source)

    for key, payload in results.items():
        if key == "a1":
            print(f"A1 WER: {payload['wer'] * 100:.2f}%  ({_verdict(payload['passed'])})")
        elif key == "a2":
            summary = payload["summary"]
            print(
                f"A2 within {TIMESTAMP_TOLERANCE_MS // 1000}s: "
                f"{summary['within_5s']}/{summary['questions']}  ({_verdict(summary['passed'])})"
            )
        elif key == "a3_notcovered":
            for category, entry in payload["by_category"].items():
                print(
                    f"A3 {category}: {entry['refused']}/{entry['questions']} refused"
                    f"  ({_verdict(entry['passed'])})"
                )
        elif key == "a3_keyterms":
            summary = payload["summary"]
            print(f"A3 key terms: {summary['terms']}/5 present  ({_verdict(summary['passed'])})")

    print(f"\nwrote {summary_path}")
    print(f"thresholds: match={config.match_threshold} grounding={config.answer_grounding_min}")

    failed = failures + [
        key
        for key, payload in results.items()
        if not (payload.get("passed") if key != "a2" else payload["summary"]["passed"])
    ]
    return 0 if results and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
