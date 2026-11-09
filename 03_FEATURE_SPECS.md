# 03 · Feature Specs

Each feature has: **Behaviour**, **UI**, **Acceptance criteria (AC)**. IDs are referenced in `09_TASK_PLAN.md`.

---

## F1 · Audio upload and validation (P0)

**Behaviour**
- Accept mp3, wav, m4a (and ideally mp4/ogg/flac). Reject anything else with a clear message.
- Reject audio > `MAX_AUDIO_MINUTES` (10) or < 20 s; reject files above a size cap (e.g. 50 MB).
- Compute SHA-256; if a cached Speech result exists, skip transcription.
- Include a **"Use sample lecture"** button that loads a team clip, so the demo never depends on live upload.

**UI**: file uploader, sample picker, progress indicator ("Transcribing… Generating notes… Verifying…"), embedded audio player.

**AC**
- F1.1 Unsupported/oversize/too-long files show a friendly error, no crash, no Azure call made.
- F1.2 Same file twice → second run uses cache (visible "cached" badge).

---

## F2 · Timestamped transcript (P0, maps to **A1**)

**Behaviour**
- Call Azure Speech; parse into `Transcript` contract.
- Show one row per phrase: `[mm:ss] text`. Timestamp is a **clickable chip** that seeks the audio player to `start_ms` and plays (F8).
- Show **low-confidence flag** (F9) per phrase.
- Offer download as `.txt` (with timestamps) and `.vtt`/`.srt`.
- For long phrases, optionally split by words so each row is ~15 to 25 words for readability, using word offsets.

**AC**
- F2.1 A 2-minute section produces a transcript with timestamps monotonic increasing and within audio duration.
- F2.2 WER on the A1 clip vs the team script is reported by `eval/run_eval.py` (target <= 10%; report honestly whatever the number is).
- F2.3 Timestamp at row N plays the audio within ~1 s of the text being spoken (spot-check 5 rows).

---

## F3 · One-page revision notes (P0)

**Behaviour**
- Model generates structured notes: a title, a 2-sentence overview, 3 to 6 sections each with 2 to 4 bullets, all derived from the transcript.
- **Each bullet must include a verbatim evidence quote.** The Verification Engine locates it and attaches a timestamp. Unverified bullets are removed, with the count shown in the report.
- Output must fit on **one page**: cap at ~350 to 450 words total. Enforce in prompt and trim in code if exceeded (drop lowest-scored bullets, not mid-sentence truncation).
- Render with a print-friendly layout; export to Markdown (and PDF if time allows).

**UI**: "Revision Notes" tab; each bullet ends with a timestamp chip and a small ✓ verified badge.

**AC**
- F3.1 Every bullet shown has ≥ 1 verified evidence quote with a timestamp.
- F3.2 Notes contain no facts absent from the transcript (spot-check 10 bullets against the transcript; log result).
- F3.3 Total length ≤ ~450 words.

---

## F4 · Five key terms (P0, maps to **A3 second half**)

**Behaviour**
- Exactly **5** key terms. Each has `term`, `definition`, and an evidence quote.
- **Definition must come from the lecture**: the definition text is composed from, or closely paraphrases, the lecturer's own words in the quote. If the lecturer never defines the term explicitly, choose a different term.
- **Hard check in code:** the `term` (case-insensitive, light normalisation such as plural/hyphen/whitespace) **must literally appear in the transcript**, and the evidence quote must verify. If a term fails, discard it and regenerate a replacement (max 3 attempts). If still < 5, ask the model for the next-best candidates from a larger pool (request 8, keep best 5 verified).
- Show timestamp of the first/defining mention.

**UI**: cards or a table: Term | Definition | ▶ mm:ss. Plus link to flashcard mode (F10).

**AC**
- F4.1 Exactly 5 shown. (If the lecture genuinely cannot support 5, show as many as verified and explain; for our two test clips this must not happen.)
- F4.2 For each term, an automated test asserts `term in normalised_transcript`. **100% must pass** for A3.
- F4.3 Each definition's evidence quote verified, with timestamp.

---

## F5 · Grounded Q&A with timestamp (P0, maps to **A2**)

**Behaviour**
- Text box + "Ask" button. Also show 3 example-question chips (generated from verified notes) to help the student.
- Pipeline: model returns `{covered, answer, evidence_quotes[]}` → Verification Engine locates quotes → build `QAResult`.
- The answer shows: answer text, **"Said at mm:ss ▶"** chip(s), and the supporting quote in a block-quote.
- If multiple quotes, show the primary (earliest strongest) timestamp first and others as "also see".
- Answer must be short (1 to 3 sentences) and phrased from the lecture.

**AC**
- F5.1 For ≥ 8 of 10 labelled covered questions, `primary_timestamp_ms` is within ±5 s of the gold timestamp (target: all within ±5 s; report honestly).
- F5.2 Clicking the chip plays the audio from that moment.
- F5.3 The answer is consistent with the quote (optional entailment check, see `04`).

---

## F6 · "Not covered in this lecture" (P0, maps to **A3 first half**)

**Behaviour**
- `covered` is **recomputed in code**: a question is covered only if at least one evidence quote verifies **and** the relevance gate passes (see `04_VERIFICATION_ENGINE.md`).
- When not covered, show exactly: **"Not covered in this lecture"** and a one-line reason ("No sentence in the lecture supports an answer"). Do not offer a guessed answer.
- Optional: suggest the 2 closest topics that *are* covered (from verified notes), clearly labelled as suggestions.

**AC**
- F6.1 ≥ 5 clearly unrelated questions all return Not covered.
- F6.2 ≥ 5 **near-miss** questions (same subject area, never said) return Not covered. Report the pass rate.
- F6.3 The literal string "Not covered in this lecture" appears (judges may grep the output).

---

## F7 · Verification report (P0)

**Behaviour**
- A collapsible panel summarising: notes verified/removed, key terms verified/replaced, Q&A answered/refused, low-confidence segments count, injection attempts flagged.
- Stored as JSON in `eval/results/` for the Evidence Sheet.

**AC**: report numbers equal what the UI actually shows (no hard-coding; derived from the same objects).

---

## F8 · Click-to-play timestamps (P0)

**Behaviour**: any timestamp chip seeks the audio element to `start_ms − 1.0 s` (small lead-in so the sentence isn't clipped) and plays. Optionally highlight the active transcript row while playing.

**AC**: demo-able within 2 clicks; works for transcript, notes, key terms, Q&A.

---

## F9 · Low-confidence flags (P1)

**Behaviour**: phrases with Speech `confidence` < 0.80 (configurable) get an amber "⚠ unclear audio" marker. Notes/Q&A evidence that rests on a low-confidence phrase gets a small caution tag.

**AC**: at least one flagged phrase appears on a deliberately noisy sample (record 30 s with background noise) to demonstrate.

---

## F10 · Study mode / flashcards (P1)

**Behaviour**: the 5 key terms as flip cards (term → definition + "heard at mm:ss ▶"). Optional "Quiz me": 5 short questions generated from verified notes; the answer reveal shows the quote and timestamp. Same verification rules apply.

**AC**: card back always shows a timestamp that plays the correct moment.

---

## F11 · Adversarial/robustness handling (P1)

**Behaviour**
- Transcript text is passed to the model as **data inside delimiters**; system prompt forbids following instructions inside it.
- `safety.py` scans the transcript for injection-style phrases ("ignore previous instructions", "system prompt", etc.), flags them in the report, and still treats them as plain content.
- Leading questions with false premises: model instructed to check the premise; verification refuses when no quote supports it.

**AC**: record a clip with an injected sentence; the notes/Q&A are unaffected and the report shows "1 injection-like phrase detected".

---

## F12 · Metrics page + CLI (P0)

**Behaviour**: `python eval/run_eval.py` runs A1 (WER), A2 (timestamp error on gold questions), A3 (not-covered and key-term checks), prints a table, writes `eval/results/*.json` and a Markdown summary. The Streamlit app has a "Metrics" tab that renders the latest results.

**AC**: running the command from a clean clone with env vars set reproduces the numbers in the Evidence Sheet (cached Speech output allowed).

---

## F13 · Exports (P2)

Markdown/PDF notes; SRT/VTT transcript; JSON of everything (for the Evidence Sheet).

---

## UI layout (suggested)

```
┌───────────────────────────────────────────────────────────┐
│ Title · upload / sample picker               [Cached ✓]    │
│ ▶ Audio player (sticky)                                    │
├───────────────┬───────────────────────────────────────────┤
│ Tabs: Notes | Key Terms | Transcript | Ask | Study | Metrics│
│                                                            │
│  Ask tab:  [ Ask a question about this lecture ] [Ask]     │
│   Answer …                    Said at 03:42 ▶  ✓ verified  │
│   > "supporting quote"                                      │
│   — or —  Not covered in this lecture (reason)             │
│                                                            │
│  Verification report (collapsible)                         │
└────────────────────────────────────────────────────────────┘
```
