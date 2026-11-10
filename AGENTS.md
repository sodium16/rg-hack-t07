# AGENTS.md — working rules for this repository

Repo for **AI-103 Hackathon, problem P11: Lecture to Revision Notes**. Five people, one day, one working app on the team's own Azure account. Team number/name are placeholders (`T##`, `P11`); substitute them only where a deliverable requires it.

> **Pitch, and the test for every design decision:**
> "Every sentence this app shows you can be traced to a second in your lecture, or it doesn't show it."

## 1. Read before changing anything

| File | Why it matters |
|---|---|
| `00_PROJECT_BRIEF.md` | Problem statement, handout rules, deliverables, scoring. Non-negotiables. |
| `01_VISION_AND_DIFFERENTIATORS.md` | The Trust Layer and P0/P1 feature priority. |
| `02_ARCHITECTURE.md` | Pipeline, data contracts, config, repo layout. |
| `03_FEATURE_SPECS.md` | Behaviour + acceptance criteria per feature (F1–F13). |
| `04_VERIFICATION_ENGINE.md` | The grounding/verification algorithm. **The heart of the project.** |
| `05_PROMPTS.md` | Prompt templates and JSON schemas. |
| `06_SAFETY_COST_ENGINEERING.md` | Risks, secrets, error handling, cost control. |
| `07_TESTING_AND_EVIDENCE.md` | A1/A2/A3 tests, metrics, Evidence Sheet material. |
| `08_DEMO_SCRIPT.md` | The 5-minute video, second by second. |
| `09_TASK_PLAN.md` | Milestones, roles, backlog, definition of done. |

If a convention in this file conflicts with an older doc, **this file wins** (it carries the current API facts in §5). Fix the stale doc in the same change when practical.

## 2. Scope: build only what P11 asks for

**Required (P0):** audio upload → Azure AI Speech transcript with timestamps → one-page revision notes → exactly 5 key terms defined from the lecture → grounded Q&A that cites a timestamp → literal `Not covered in this lecture` for unrelated questions.

**Explicitly out of scope** (do not add, even though the workshop covered them): text-to-speech, vision/image Q&A, Document Intelligence, a Foundry *agent* with threads, a vector index or Azure AI Search, embeddings retrieval, auth/accounts, a database, deployment pipelines, multi-user features. The Day-4 capstone "agent + RAG + one modality" shape is **not** this problem; Speech + a Foundry chat deployment is.

P1 items (confidence flags, flashcards, injection handling, LLM judge call) are worth building **only after** every P0 acceptance criterion passes on real audio. P2 is optional. Never trade verification, click-to-play, or metrics for extra features.

## 3. Non-negotiable behaviour

1. **Timestamps are computed in code.** Locate the model's *verbatim* quote in the Speech word/phrase index (`04_VERIFICATION_ENGINE.md`). Never display a timestamp the model produced.
2. **Unverified content is not shown.** A note bullet, key term, or answer without a verified supporting quote is dropped (or regenerated), and the count appears in the Verification Report.
3. **`Not covered in this lecture` is a code decision**, from quote verification + the relevance gate — not a string the model may choose to emit. It must be reachable for both unrelated and **near-miss** questions.
4. **Exactly 5 key terms, each literally present in the transcript** (normalised match), each with a verified evidence quote. Assert this in tests and in the eval.
5. **No fake, cached-as-truth, or hard-coded results.** Gold answers/timestamps live only under `eval/`; the app must work on a lecture and a question it has never seen (the demo requires one).
6. **Secrets stay in the environment.** Nothing in code, `.env.example`, screenshots, video, logs, or git history. A visible key costs 5 points.
7. **Content filter stays on**; catch `finish_reason == "content_filter"` and show a friendly message instead of blocked output.
8. **Synthetic audio only.** Team-recorded clips; no real student data.

## 4. Architecture invariants

Keep the contracts in `02_ARCHITECTURE.md` stable: `TranscriptPhrase`, `Transcript`, `Evidence`, note bullet, `KeyTerm`, `QAResult`, `VerificationReport`. Extend them; do not rename or repurpose fields.

- Model returns **quotes**; the Verification Engine returns **milliseconds**. UI seeks to `start_ms − 1000`.
- `norm()` is applied identically to the transcript and to quotes; matching is exact → fuzzy sliding window → fail (`MATCH_THRESHOLD` default `0.88`, minimum 5 tokens, maximum 40).
- All thresholds and caps live in config/env, not scattered literals, and their final values are recorded in the Evidence Sheet.
- Build order matters: `transcript_index.py` + `verify.py` with offline fixture tests **first**, then Speech, then the LLM pipeline, then Q&A, then UI. A thin verified vertical slice beats a broad unverified app.
- Modules stay small and readable (see the layout in `02`). Every teammate must be able to explain any file, so prefer clarity over cleverness.
- Cache by audio SHA-256 (Speech JSON and LLM output) so repeat demo runs are instant and free; cache must never bypass verification.

## 5. Azure facts to build against (verified 2026-11)

- **Speech fast transcription** is the required route (batch only if the region lacks fast). Current GA: `POST {endpoint}/speechtotext/transcriptions:transcribe?api-version=2025-10-15`. `2025-10-15` supersedes `2024-11-15`; the v3.x APIs were retired 31 March 2026. Re-check Microsoft Learn before wiring it — do not copy the older `2024-11-15` value from `02_ARCHITECTURE.md`.
- Request is `multipart/form-data` with `audio` and `definition` (`{"locales":["en-US"]}`). REST reference limits: under 2 hours and under 250 MB (the how-to page quotes other figures — the REST reference governs). Our 10-minute cap is far inside either.
- **Phrase lists are supported from `2025-10-15`** (`definition.phraseList.phrases`, optional `biasingWeight`). Use them for domain terms so the transcript spells them correctly, and then keep the key-term check honest against the transcript.
- Word-level timestamps come back inside `phrases[].words[]` **only when explicitly enabled** — confirm the exact definition field name against the current docs, and fall back to proportional character-length interpolation inside the phrase when they are absent.
- Transcript response fields we rely on: `durationMilliseconds`, `combinedPhrases[].text`, `phrases[]` (`offsetMilliseconds`, `durationMilliseconds`, `text`, `confidence`, `locale`, `words[]`).
- **Foundry model**: one chat deployment, Azure OpenAI-compatible endpoint, structured output / JSON mode, `temperature` 0–0.2, `max_tokens` capped, token usage logged. Grounding is the pasted transcript — no retrieval layer needed at 10 minutes.
- The workshop lab's 2 MB upload limit is a LabForge constraint, not ours; our cap is duration-based (10 min).

## 6. Configuration and secrets

Read only from env (names already fixed in `02_ARCHITECTURE.md`): `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_LOCALE` (default `en-US`), `AZURE_FOUNDRY_ENDPOINT`, `AZURE_FOUNDRY_KEY` (or Entra ID), `AZURE_FOUNDRY_DEPLOYMENT`, `AZURE_FOUNDRY_API_VERSION`, `MAX_AUDIO_MINUTES`, `MATCH_THRESHOLD`.

- `.env` is gitignored; `.env.example` holds empty placeholders only. Fail fast with a readable message when a variable is missing — never with a stack trace.
- Redact `Ocp-Apim-Subscription-Key` / `api-key` headers in any debug output. Don't screen-record a terminal or portal blade showing a key or the subscription ID.
- Run a secret scan (`gitleaks` / `detect-secrets`) before zipping code and before recording the demo.

## 7. Evidence is a deliverable, not an afterthought

- Capture screenshots while testing: `a1_transcript.png`, `a2_q03_answer.png`, `a3_notcovered.png`, content-filter settings, budget alert, resource group, model deployments.
- `eval/run_eval.py` produces the numbers (WER via `jiwer`, timestamp error vs gold windows, not-covered rates by category, key-term pass rate). No metric may be hand-typed into the UI.
- For each of A1/A2/A3 the Evidence Sheet needs **input, pasted output, screenshot, Pass/Fail**. Report misses honestly and say what changed; faked results disqualify the team.
- The demo needs a **live, previously unused input** to work — so the live code path must stay functional, not just cached samples.

## 8. How to work in this repo

1. State the plan in one or two sentences, then implement; don't idle on questions. Only ask for genuinely blocking decisions (real team number, lecture locale, UI framework choice); otherwise take the documented defaults.
2. Prefer editing existing modules over adding new ones; no new dependency unless the project needs it and it is justified by a doc.
3. After any change, run the narrowest check that proves it: offline unit tests for verification/matching, the eval for pipeline behaviour, one manual upload for UI. Report exactly what ran and what did not.
4. Handle every external call with timeout, bounded retry on 429/5xx, a typed error, and a friendly UI message. Partial results (e.g. notes without Q&A) are better than a blank page.
5. Update `README.md` (how to run) after each milestone, and record departures from these docs in `docs/DECISIONS.md`; park unrequested ideas in `docs/IDEAS.md`.
6. Definition of done for a feature: matches its ACs in `03_FEATURE_SPECS.md`, offline tests pass where applicable, errors handled, no secrets, demonstrated on a real team clip, evidence captured.
7. Project done: A1/A2/A3 pass with numbers in `eval/results/summary.md`; a fresh clone plus `.env` reproduces them; all four deliverables named exactly, in `T##_P11_TeamName`, with the self-check in `00_PROJECT_BRIEF.md` ticked.
