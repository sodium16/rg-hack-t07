"""Streamlit UI: upload a lecture, read verified notes, click any timestamp.

Run with:
    .venv/Scripts/python.exe -m streamlit run main.py

Nothing on screen is a model claim: every bullet, term and answer carries a
timestamp the Verification Engine computed from the transcript, and anything
that failed verification was dropped before it reached this page.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict
from pathlib import Path

import streamlit as st

from app.audio import ALLOWED_EXTENSIONS, AudioValidationError, load_audio
from app.config import MissingConfigError, load_settings
from app.llm import FoundryClient, LLMError
from app.models import QAResult
from app.notes import NotesResult, generate_notes
from app.qa import REFUSAL_TEXT, answer_question
from app.safety import mask, scan_all, scan_pii
from app.speech import SpeechError, transcribe_with_env
from app.transcript_index import TranscriptIndex

ROOT = Path(__file__).resolve().parent
SAMPLE_DIRS = (ROOT / "data" / "samples", ROOT / "data" / "smoke")
UPLOAD_DIR = ROOT / "data" / "uploads"

_MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}

_CSS = """
<style>
:root {
  --ink: #111827; --muted: #6b7280; --line: #e5e7eb;
  --brand: #4f46e5; --brand-soft: #eef2ff;
}
.block-container { max-width: 1080px; padding-top: 2.1rem; padding-bottom: 3.2rem; }
.hero { padding: .2rem 0 1.1rem; border-bottom: 1px solid var(--line); margin-bottom: 1.3rem; }
.hero .eyebrow {
  font-size: .72rem; letter-spacing: .14em; text-transform: uppercase;
  color: var(--brand); font-weight: 700;
}
.hero h1 { font-size: 2.15rem; margin: .35rem 0 .3rem; letter-spacing: -.02em; color: var(--ink); }
.hero .lede { color: var(--muted); font-size: 1.02rem; margin: 0 0 .85rem; }
.hero .pills span {
  display: inline-block; background: var(--brand-soft); color: #3730a3;
  border-radius: 999px; padding: .24rem .68rem; font-size: .76rem;
  margin: 0 .35rem .3rem 0; font-weight: 600;
}
.definition { color: #1f2937; margin: .1rem 0 .35rem; }
.quote {
  border-left: 3px solid var(--brand); margin: .15rem 0 .25rem;
  padding: .1rem 0 .1rem .7rem; color: var(--muted); font-style: italic;
}
.phrase { color: var(--ink); }
.warn { color: #b45309; font-size: .78rem; font-weight: 600; }
.q-line {
  font-size: .74rem; text-transform: uppercase; letter-spacing: .08em;
  color: var(--muted); font-weight: 700; margin-bottom: .3rem;
}
.empty {
  border: 1px dashed #c7d2fe; background: #f8faff; border-radius: 14px;
  padding: 1.3rem 1.5rem; color: #374151;
}
.empty strong { color: var(--ink); }
[class*="st-key-chip"] { display: flex; justify-content: flex-end; }
[class*="st-key-chip"] button {
  border-radius: 999px !important; font-variant-numeric: tabular-nums;
  padding: .05rem .6rem !important; min-height: 1.9rem; font-size: .82rem;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: 14px; box-shadow: 0 1px 2px rgba(17, 24, 39, .05);
}
[data-testid="stMetricValue"] { font-size: 1.45rem; }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
section[data-testid="stSidebar"] { background: #fbfbfd; border-right: 1px solid var(--line); }
h2, h3 { letter-spacing: -.01em; }
</style>
"""


def stamp(ms: int | None) -> str:
    """Milliseconds as ``m:ss``; ``--:--`` when there is no timestamp."""
    if ms is None:
        return "--:--"
    minutes, rest = divmod(int(ms), 60_000)
    return f"{minutes}:{rest // 1000:02d}"


def chip(ms: int | None, key: str, *, lead_in_ms: int = 1000) -> None:
    """A timestamp pill that seeks the audio player and plays from there."""
    if ms is None:
        st.caption("no timestamp")
        return
    with st.container(key=f"chip-{key}"):
        if st.button(f"▶ {stamp(ms)}", key=f"chip-button-{key}", help="Play from here"):
            st.session_state["seek_s"] = max(0.0, (ms - lead_in_ms) / 1000)


def _flush_seek() -> None:
    """Send one seek command to the page's audio element, then clear it."""
    seconds = st.session_state.get("seek_s")
    if seconds is None:
        return
    st.session_state["seek_s"] = None
    st.html(
        f"""
        <script>
        (function() {{
          var target = {seconds};
          var tries = 0;
          function attempt() {{
            var audio = document.querySelector('audio');
            if (audio) {{
              audio.currentTime = target;
              var played = audio.play();
              if (played && played.catch) played.catch(function () {{}});
              return;
            }}
            if (tries++ < 40) setTimeout(attempt, 100);
          }}
          attempt();
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _hero() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">AI-103 · P11 · Trust Layer</div>
          <h1>Lecture to Revision Notes</h1>
          <p class="lede">Every sentence traces to a second in the lecture — or it isn't shown.</p>
          <div class="pills">
            <span>⏱ timestamps computed in code</span>
            <span>✓ unverified claims dropped</span>
            <span>⚖ “not covered” decided by code</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sample_paths() -> list[Path]:
    found: list[Path] = []
    for directory in SAMPLE_DIRS:
        if directory.is_dir():
            found.extend(
                path
                for path in sorted(directory.iterdir())
                if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
            )
    return found


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).name)
    return cleaned or "lecture"


def _save_upload(name: str, payload: bytes) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / _safe_name(name)
    target.write_bytes(payload)
    return target


@st.cache_resource(show_spinner=False)
def _model() -> FoundryClient:
    return FoundryClient.from_env()


def _process(path: Path) -> dict:
    """Transcribe once per audio file per session; notes are never re-billed."""
    info = load_audio(path)
    cache = st.session_state.setdefault("processed", {})
    if info.sha256 in cache:
        return cache[info.sha256]

    with st.spinner("Transcribing with Azure Speech…"):
        speech = transcribe_with_env(path)
    index = TranscriptIndex.build(speech.transcript)
    with st.spinner("Writing notes, then verifying every claim…"):
        notes = generate_notes(index, _model())

    entry = {"info": info, "speech": speech, "index": index, "notes": notes}
    cache[info.sha256] = entry
    return entry


def _answer(sha: str, index: TranscriptIndex, question: str) -> QAResult:
    with st.spinner("Checking the lecture…"):
        result = answer_question(question, index, _model())
    st.session_state.setdefault(f"qa_{sha[:8]}", []).append(result)
    return result


def _uses_unclear_audio(evidence, index: TranscriptIndex, config) -> bool:
    """True when a verified quote rests on a phrase Speech was unsure about."""
    confidence = {phrase.id: phrase.confidence for phrase in index.transcript.phrases}
    for item in evidence:
        for phrase_id in item.phrase_ids:
            value = confidence.get(phrase_id)
            if value is not None and value < config.low_confidence_threshold:
                return True
    return False


def _render_answer(result: QAResult, key: str, index: TranscriptIndex, config) -> None:
    with st.container(border=True):
        st.markdown(
            f"<div class='q-line'>Q · {html.escape(result.question)}</div>",
            unsafe_allow_html=True,
        )
        if not result.covered:
            st.warning(REFUSAL_TEXT)
            st.caption(result.refusal_reason or "no verified evidence")
            return
        st.markdown(result.answer)
        if _uses_unclear_audio(result.evidence, index, config):
            st.caption("⚠ part of this answer rests on unclear audio")
        left, right = st.columns([8.5, 1.5], vertical_alignment="center")
        with left:
            st.caption("Said at")
        with right:
            chip(result.primary_timestamp_ms, key=f"{key}-primary")
        for item in result.evidence:
            if item.start_ms == result.primary_timestamp_ms:
                continue
            quote = item.quote_matched or item.quote_claimed
            st.markdown(
                f"<blockquote class='quote'>also at {stamp(item.start_ms)} — "
                f"“{html.escape(quote)}”</blockquote>",
                unsafe_allow_html=True,
            )


def _render_notes(notes: NotesResult, sha: str, index: TranscriptIndex, config) -> None:
    page = notes.notes
    with st.container(border=True):
        st.subheader(page.title)
        if page.overview:
            st.markdown(
                f"<div class='definition'>{html.escape(page.overview)}</div>",
                unsafe_allow_html=True,
            )
        for section_index, section in enumerate(page.sections):
            st.markdown(f"**{section.heading}**")
            for bullet_index, bullet in enumerate(section.bullets):
                left, right = st.columns([8.5, 1.5], vertical_alignment="center")
                with left:
                    st.markdown(
                        f"<div class='phrase'>• {html.escape(bullet.text)}</div>",
                        unsafe_allow_html=True,
                    )
                    if bullet.evidence and _uses_unclear_audio(bullet.evidence, index, config):
                        st.caption("⚠ based on unclear audio")
                with right:
                    chip(
                        bullet.evidence[0].start_ms if bullet.evidence else None,
                        key=f"note-{sha[:8]}-{section_index}-{bullet_index}",
                    )
        st.caption(f"{page.word_count} words · one page · every bullet verified")


def _render_terms(notes: NotesResult, sha: str) -> None:
    st.subheader("Five key terms, defined in the lecturer's own words")
    for position, term in enumerate(notes.key_terms):
        evidence = term.evidence[0] if term.evidence else None
        with st.container(border=True):
            left, right = st.columns([8.5, 1.5], vertical_alignment="center")
            with left:
                st.markdown(f"**{term.term}**")
                st.markdown(
                    f"<div class='definition'>{html.escape(term.definition)}</div>",
                    unsafe_allow_html=True,
                )
                if evidence is not None:
                    quote = evidence.quote_matched or evidence.quote_claimed
                    st.markdown(
                        f"<blockquote class='quote'>“{html.escape(quote)}”</blockquote>",
                        unsafe_allow_html=True,
                    )
            with right:
                chip(evidence.start_ms if evidence else None, key=f"term-{sha[:8]}-{position}")

    if len(notes.key_terms) != 5:
        st.warning(
            f"Only {len(notes.key_terms)} of 5 key terms could be verified on this clip."
        )


def _render_transcript(index: TranscriptIndex, config) -> None:
    st.subheader("Timestamped transcript")
    mask_pii = st.toggle(
        "Mask personal details (emails, phone numbers, ID-shaped strings)",
        value=False,
        key="mask-pii",
    )
    rows = index.transcript.phrases
    page_size = 40
    pages = max(1, (len(rows) + page_size - 1) // page_size)
    page_number = 1
    if pages > 1:
        page_number = st.number_input(
            "Page", min_value=1, max_value=pages, value=1, step=1, key="transcript-page"
        )
    start = (int(page_number) - 1) * page_size
    with st.container(border=True):
        for phrase in rows[start : start + page_size]:
            left, right = st.columns([8.5, 1.5], vertical_alignment="center")
            with left:
                unclear = (
                    phrase.confidence is not None
                    and phrase.confidence < config.low_confidence_threshold
                )
                marker = "<div class='warn'>⚠ unclear audio</div>" if unclear else ""
                text = phrase.text
                if mask_pii:
                    text = mask(text, scan_pii(text))
                st.markdown(
                    f"<div class='phrase'>{html.escape(text)}</div>{marker}",
                    unsafe_allow_html=True,
                )
            with right:
                chip(phrase.start_ms, key=f"phrase-{phrase.id}")

    text = "\n".join(f"[{stamp(phrase.start_ms)}] {phrase.text}" for phrase in rows)
    st.download_button(
        "Download transcript (.txt)",
        data=text,
        file_name="transcript.txt",
        mime="text/plain",
    )


def _render_report(entry: dict, config) -> None:
    notes: NotesResult = entry["notes"]
    index: TranscriptIndex = entry["index"]
    speech = entry["speech"]
    qa_results: list[QAResult] = st.session_state.get(f"qa_{entry['info'].sha256[:8]}", [])

    report = notes.report
    report.qa.asked = len(qa_results)
    report.qa.answered = sum(1 for result in qa_results if result.covered)
    report.qa.refused = report.qa.asked - report.qa.answered

    findings = scan_all(" ".join(phrase.text for phrase in index.transcript.phrases))
    unclear = sum(
        1
        for phrase in index.transcript.phrases
        if phrase.confidence is not None and phrase.confidence < config.low_confidence_threshold
    )

    st.subheader("Verification report")
    st.caption("Every number below is derived from the objects this page displays.")
    columns = st.columns(3)
    cards = (
        ("Notes kept", f"{report.notes.verified}/{report.notes.generated}",
         f"{report.notes.removed} dropped as unverified"),
        ("Key terms kept", f"{report.key_terms.verified}/{report.key_terms.generated}",
         f"{report.key_terms.removed} dropped"
         + (", regenerated" if report.key_terms.regenerated else "")),
        ("Answers", f"{report.qa.answered}/{report.qa.asked}",
         f"{report.qa.refused} refused as not covered"),
    )
    for column, (label, value, note) in zip(columns, cards):
        with column, st.container(border=True):
            st.metric(label, value)
            st.caption(note)

    usage: dict[str, int] = {}
    for source in [notes.usage] + [result.usage for result in qa_results]:
        for name, value in (source or {}).items():
            usage[name] = usage.get(name, 0) + int(value)
    if usage:
        st.caption(
            "tokens this run · "
            + " · ".join(f"{name} {value}" for name, value in sorted(usage.items()))
        )

    details = {
        "audio_sha256": entry["info"].sha256,
        "duration_ms": entry["info"].duration_ms,
        "speech_cached": speech.cached,
        "phrases": len(index.transcript.phrases),
        "low_confidence_phrases": unclear,
        "injection_like_phrases": sum(1 for item in findings if item.kind == "injection"),
        "pii_like_phrases": sum(1 for item in findings if item.kind != "injection"),
        "report": asdict(report),
    }
    if findings:
        st.warning(
            f"{len(findings)} safety-flagged span(s) in the transcript — "
            "treated as content, never as instructions."
        )
        st.json([asdict(item) for item in findings])
    st.json(details)
    st.download_button(
        "Download report (.json)",
        data=json.dumps(details, indent=2),
        file_name="verification_report.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(
        page_title="Lecture to Revision Notes",
        page_icon="🎧",
        layout="wide",
    )
    st.session_state.setdefault("seek_s", None)
    st.markdown(_CSS, unsafe_allow_html=True)
    config = load_settings()
    _hero()

    with st.container(border=True):
        st.markdown("<div class='q-line'>Start here</div>", unsafe_allow_html=True)
        upload_column, sample_column = st.columns([1, 1], vertical_alignment="bottom")
        with upload_column:
            upload = st.file_uploader(
                "Upload a lecture clip",
                type=[suffix.lstrip(".") for suffix in sorted(ALLOWED_EXTENSIONS)],
                help="mp3, wav, m4a, mp4, ogg, flac or webm",
            )
        with sample_column:
            samples = _sample_paths()
            choice = st.selectbox(
                "…or use a bundled clip",
                ["(none)"] + [path.relative_to(ROOT).as_posix() for path in samples],
            )
        st.caption("20 s – 10 min · under 50 MB · transcript cached by audio SHA-256")

    path: Path | None = None
    if choice != "(none)":
        path = ROOT / choice
    elif upload is not None:
        path = _save_upload(upload.name, upload.getvalue())

    if path is None:
        st.markdown(
            """
            <div class="empty">
              <strong>No lecture loaded yet.</strong><br>
              Drop an audio file in the sidebar, or pick one of the bundled clips.
              You'll get a timestamped transcript, one page of verified revision notes,
              five key terms, and a Q&amp;A that cites the second it was said.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    try:
        entry = _process(path)
    except AudioValidationError as error:
        st.error(f"That file can't be used: {error}")
        st.stop()
    except MissingConfigError as error:
        st.error(f"Configuration problem: {error}")
        st.stop()
    except SpeechError as error:
        st.error(f"Transcription failed: {error}")
        st.stop()
    except LLMError as error:
        st.error(f"The model stage failed: {error}")
        st.stop()

    info = entry["info"]
    speech = entry["speech"]
    index: TranscriptIndex = entry["index"]
    notes: NotesResult = entry["notes"]
    sha = info.sha256

    player, facts = st.columns([7, 3], vertical_alignment="center")
    with player:
        st.audio(path.read_bytes(), format=_MIME.get(path.suffix.lower(), "audio/wav"))
    with facts:
        st.markdown(
            f"<div class='definition'><strong>{html.escape(path.name)}</strong></div>",
            unsafe_allow_html=True,
        )
        badge = "cached ✓" if speech.cached else "fresh transcription"
        st.caption(
            f"{info.duration_ms / 1000:.1f} s · {len(index.transcript.phrases)} phrases · "
            f"{badge} · audio {sha[:12]}"
        )

    tabs = st.tabs(["Notes", "Key terms", "Transcript", "Ask", "Verification"])
    with tabs[0]:
        _render_notes(notes, sha, index, config)
    with tabs[1]:
        _render_terms(notes, sha)
    with tabs[2]:
        _render_transcript(index, config)
    with tabs[3]:
        st.subheader("Ask about this lecture")
        question = st.text_input(
            "Your question", key=f"question-{sha[:8]}", placeholder="What is …?"
        )
        if st.button("Ask", key=f"ask-{sha[:8]}", type="primary") and question.strip():
            try:
                _answer(sha, index, question.strip())
            except LLMError as error:
                st.error(f"That question failed: {error}")

        examples = [f"What is {term.term}?" for term in notes.key_terms[:3]]
        if examples:
            st.caption("Try one of these:")
            columns = st.columns(len(examples))
            for position, (column, example) in enumerate(zip(columns, examples)):
                with column:
                    if st.button(example, key=f"example-{sha[:8]}-{position}"):
                        try:
                            _answer(sha, index, example)
                        except LLMError as error:
                            st.error(f"That question failed: {error}")

        for position, result in enumerate(
            reversed(st.session_state.get(f"qa_{sha[:8]}", []))
        ):
            _render_answer(result, key=f"qa-{sha[:8]}-{position}", index=index, config=config)
    with tabs[4]:
        _render_report(entry, config)

    _flush_seek()


if __name__ == "__main__":
    main()
