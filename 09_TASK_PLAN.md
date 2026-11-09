# 09 · Task Plan, Team Split and Definition of Done

One-day build. Order matters: **get a verified end-to-end slice early**, then widen. The Verification Engine is the critical path and is testable offline.

## Team split (5 people)

| Role | Owner of | Key deliverables |
|------|----------|------------------|
| **1. Azure and Safety lead** | Azure setup, content filter, budget, secrets, `3_Azure_Proof.pdf`, `safety.py` | Resource group `rg-hack-T##`, budget alert, Speech + Foundry deployments, screenshots, PII/injection scan, secret scan |
| **2. Speech and Data lead** | `audio.py`, `speech.py`, `transcript_index.py`, clip recording, scripts | Working transcription → `Transcript` contract, caching, 2 clips + scripts, low-confidence flags |
| **3. LLM and Notes lead** | `llm.py`, `prompts.py`, `notes.py` | Notes + 5 key terms with regeneration loop, schema validation, flashcards |
| **4. Verification and Q&A lead** | `verify.py`, `qa.py` | Locate algorithm, relevance gate, not-covered logic, unit tests |
| **5. UI and Evidence lead** | `main.py`, `ui_components.py`, `eval/`, Evidence Sheet, demo video | Click-to-play UI, metrics tab, `run_eval.py`, WER/timestamp tables, final docs |

Everyone: pair-review at least one other module so all five can explain the whole system.

## Milestones (suggested timeline for ~8 to 9 hours)

### M0 · Setup (first 45 min)
- [ ] Azure: resource group, **budget alert first**, Speech, Foundry deployment, content filter confirmed. (Role 1)
- [ ] Repo with layout from `02_ARCHITECTURE.md`, `.gitignore`, `.env.example`, secret scan hook. (Role 5 + 1)
- [ ] Record Clip 1 + script (Role 2 + one other). Start recording early; it's the slowest dependency.
- [ ] Agree thresholds and contracts (copy from docs; don't change casually).

### M1 · Thin vertical slice (by ~2.5 h)
- [ ] Upload → Speech → `Transcript` → displayed with `[mm:ss]`. (Roles 2, 5)
- [ ] `verify.locate()` + tests passing on a fixture. (Role 4)
- [ ] One LLM call returns notes JSON; each bullet located. (Role 3)
- [ ] Q&A returns answer + verified timestamp. (Roles 3, 4)

### M2 · P0 complete (by ~5 h)
- [ ] 5 verified key terms with regeneration loop (F4).
- [ ] Not-covered gate incl. relevance checks (F6).
- [ ] Click-to-play on all chips (F8). Verification report (F7).
- [ ] Error handling, caching, cost logging (06).
- [ ] Clip 2 recorded with injection + PII lines.

### M3 · Evidence and polish (by ~7 h)
- [ ] `qa_gold.json` written for both clips; `run_eval.py` produces A1/A2/A3 numbers; iterate prompts/thresholds on results.
- [ ] Low-confidence flags (F9), flashcards (F10), injection handling (F11).
- [ ] Metrics tab in UI (F12).
- [ ] Screenshots captured for A1/A2/A3 as they pass.

### M4 · Deliverables (by ~8.5 h; **upload early**)
- [ ] Evidence Sheet (≈ 2 pages) filled and exported to PDF.
- [ ] Code zip / GitHub link + README; secret scan clean.
- [ ] `3_Azure_Proof.pdf` (keys and subscription ID hidden).
- [ ] Demo video recorded (≤ 5:00) with the on-the-spot new input.
- [ ] Self-check list from `00_PROJECT_BRIEF.md` ticked.
- [ ] Upload to `T##_P11_TeamName` and re-open files to confirm they play/open.
- [ ] After results: delete `rg-hack-T##`.

## Backlog (prioritised)

**P0**: F1 Upload · F2 Transcript · F3 Notes · F4 Key terms · F5 Q&A · F6 Not covered · F7 Report · F8 Click-to-play · F12 Eval/Metrics · safety basics · caching.
**P1**: F9 Confidence flags · F10 Flashcards · F11 Injection handling · LLM judge call · near-miss test set · Entra ID auth.
**P2**: F13 Exports · section detection · embeddings retrieval gate · transcript search · PDF export of notes.

## Definition of done (per feature)

- Behaviour matches `03_FEATURE_SPECS.md` ACs.
- Unit tests (where applicable) pass offline.
- Errors handled; no stack traces shown; no secrets logged.
- Demonstrated once on real audio from our clips.
- Screenshot/metric captured for the Evidence Sheet if relevant.

## Definition of done (project)

1. A1, A2, A3 pass with numbers in `eval/results/summary.md`.
2. Fresh clone + `.env` + `pip install -r requirements.txt` + one run command works (README verified by a teammate who didn't write it).
3. Verification report numbers are derived, never hard-coded.
4. All four deliverables uploaded with exact names; self-check complete.
5. Every teammate can explain: Speech call, prompts, verification, not-covered logic, safety.

## Risk and contingency

| Risk | Contingency |
|------|-------------|
| Fast transcription unavailable in region | Use batch transcription (Blob + polling) or switch region; decide in M0 |
| Word-level offsets missing | Interpolate within phrase (04 §1); still accurate to ~1 to 2 s |
| Model quotes not verbatim | Fuzzy threshold + "quote exactly" prompt + repair retry; log verified-rate |
| Near-miss questions slip through | Add judge call + central-concept check; tune on `qa_gold.json` |
| Streamlit seek clunky | Custom HTML audio component with JS seek |
| Running out of time | Cut P2, then P1 in this order: embeddings, exports, quiz; **never cut verification, click-to-play, or metrics** |
| Clip recording delayed | Record Clip 1 first, M0; clip 2 by M2 |
| Rate limits/cost | Cache, small model, 10-min cap |

## Instructions for the coding agent (if you are one)

1. Read all docs in order. Ask the team only for decisions that block you (team number, locale, UI framework choice); otherwise use the defaults here.
2. **Build `verify.py` and `transcript_index.py` first** with offline tests, using a hand-made fixture.
3. Then `speech.py`, `llm.py`, `notes.py`, `qa.py`, then UI.
4. Keep the data contracts in `02_ARCHITECTURE.md` stable; extend, don't break.
5. Never hard-code outputs, expected answers, timestamps, or metrics. Gold data lives only under `eval/`.
6. Never write secrets to files; read env vars only; keep `.env.example` empty.
7. Prefer small, readable modules; every teammate must be able to explain your code. Comment the *why* of thresholds.
8. After each milestone, update `README.md` with run instructions and record any deviations from these docs in `docs/DECISIONS.md`.
9. Keep suggestions for improvement in `docs/IDEAS.md`; don't silently expand scope beyond P0/P1.
