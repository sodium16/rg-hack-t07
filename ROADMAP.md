# ROADMAP · P11 Lecture to Revision Notes

Complete development plan for the one-day AI-103 hackathon build. Read `AGENTS.md` first; this file turns its invariants into a time-boxed sequence with **hard gates**. Times are elapsed from kickoff (T+0), not wall-clock, and assume five people working in parallel.

**Success = A1, A2 and A3 pass with measured numbers, four deliverables uploaded, no secrets anywhere.** Nothing on this roadmap is worth trading verification, click-to-play or metrics for.

Times run roughly 45–60 minutes past the M0–M4 outline in `09_TASK_PLAN.md`. That is deliberate: the buffer sits at the end, where evidence and upload happen, because that is where teams with a working app still lose marks.

## Status (2026-11-09)

| Phase | State | Note |
|---|---|---|
| 0 Setup | done | Repo skeleton, secret hygiene, Azure Speech + Foundry resources provisioned |
| 1 Verification core | **built** | Offline tests green |
| 2 Speech | **live-verified** | 87 tests green; real call on `data/smoke/sapi_lecture.wav` → 8 phrases, 98 word offsets, 3.8 s; second run served from cache in 0.02 s |
| 3 Notes + key terms | **live-verified** | Live run: 7 bullets → 6 verified, 7 terms → 5 verified after one regeneration, all timestamps computed |
| 4 Q&A gate | **live-verified** | Covered questions answer with a computed timestamp; unrelated and near-miss questions refused with the literal text |
| 5 UI | **built** | Streamlit app: upload/sample picker, audio player, notes, key terms, transcript, Q&A, verification report; click-to-play verified in the browser |
| 6 Eval | **harness built** | `eval/run_eval.py` computes WER, timestamp accuracy and refusal rates and writes `eval/results/*.json` + `summary.md`; gold questions still need the team clip |
| 7 Safety | **built** | Injection/PII scanners, a display-masking toggle and unclear-audio tags in the UI; live content-filter demo pending |
| 8 Deliverables | not started | — |

"Built" means tested offline, not proven against Azure. G0, G2, G3, G4, G6 and G7 still require credentials and audio.

---

## 1. Sequencing principle

The trust layer is the product, so it is built first and tested offline:

```
fixture → transcript_index + verify (offline tests)
        → Speech (real transcript)
        → notes + key terms (verified)
        → Q&A + not-covered gate
        → UI (click-to-play)
        → eval numbers → evidence → video
```

Two consequences:

1. **Speech and the verification core overlap by design.** Role 4 can finish `locate()` on a hand-written fixture while Role 2 wires the real API; they meet at the `Transcript` contract and neither blocks the other.
2. **UI comes late but not last.** It needs verified objects to render, but the demo is scored on what judges can see, so it gets a dedicated 90-minute block and no more polish after it.

## 2. Target metrics (decide these now, measure later)

| Test | Metric | Target | Measured by |
|---|---|---|---|
| A1 | WER vs 2-minute script | ≤ 10% (report actual) | `eval/run_eval.py` |
| A1 | Timestamps monotonic, inside clip duration | 100% | unit check + 5 manual spot-checks |
| A2 | `primary_timestamp_ms` within ±5 s of gold window | ≥ 90% | eval table |
| A2 | Clicking the chip plays the right sentence | 100% (spot-check) | manual |
| A3 | Unrelated questions → `Not covered in this lecture` | 100% | eval |
| A3 | Near-miss questions → not covered | ≥ 90% | eval |
| A3 | Key terms literally present in transcript | 100% (5/5) | assertion + eval |

Targets are goals, not claims. If a number misses, it is reported honestly with what changed.

## 3. Workstreams and owners

Same five roles as `09_TASK_PLAN.md`; "Lead" owns the phase gate, "Support" is expected in the same room.

| Phase | Hours | Role 1 Azure/Safety | Role 2 Speech/Data | Role 3 LLM/Notes | Role 4 Verify/Q&A | Role 5 UI/Evidence |
|---|---|---|---|---|---|---|
| 0 Setup | 0–0:45 | Lead | Support (record clip) | Support | Fixture prep | Support |
| 1 Verify core | 0:45–2:15 | — | — | Support | **Lead** | — |
| 2 Speech | 1:00–2:45 | — | **Lead** | — | Support | — |
| 3 Notes + terms | 2:45–4:15 | — | — | **Lead** | Support | — |
| 4 Q&A gate | 4:15–5:30 | — | — | Support | **Lead** | — |
| 5 UI | 5:30–7:00 | — | Support | — | — | **Lead** |
| 6 Eval/evidence | 7:00–8:15 | — | Support | Support | Support | **Lead** |
| 7 Safety/robustness | gaps, done by 8:15 | **Lead** | — | — | Support | — |
| 8 Deliverables | 8:15–9:30 | Support | Support | Support | Support | **Lead** |

---

## Phase 0 · Setup and Azure (0:00–0:45)

Goal: nothing in later phases waits on an account, a key or an unrecorded clip.

**Role 1 — Azure (do this first, before any code):**
- [ ] Resource group `rg-hack-T##` created.
- [ ] **Budget + alert created before any resource is used**; screenshot for `3_Azure_Proof.pdf`.
- [ ] Azure AI Speech resource in a fast-transcription-capable region; note region.
- [ ] Foundry project + one chat model deployment; content filter confirmed ON (default or stricter); screenshot.
- [ ] Record deployment name and API version; keys go into a local `.env` only.
- [ ] Confirm fast transcription is available in the region (a 10-second curl on a sample; if it 404s, switch region now — this is the one hard blocker).

**Role 2 + one other — audio:**
- [ ] Clip 1 recorded (5–10 min, quiet room, 16 kHz+ mono) **and** `clip1_script.txt` written from what was actually said.
- [ ] Clip 2 scripted with: a repeated concept, an unrelated aside, the injection sentence, and a fake phone/email. Record after Phase 2 so Phase 1 is not blocked.

**Role 5 — repo skeleton:**
- [ ] Layout from `02_ARCHITECTURE.md` (`app/`, `eval/`, `data/`, `tests/`, `docs/`), `.gitignore` (`.env`, `data/cache/`, media), `.env.example` with empty placeholders, `requirements.txt`.
- [ ] Secret-scan baseline (`gitleaks`/`detect-secrets`) runs clean on an empty repo.

**Role 4 — fixture:**
- [ ] Hand-written `tests/fixtures/transcript_sample.json` in the `Transcript` contract, including one phrase with `words[]` and one without (to exercise interpolation), and one phrase repeated later in the clip.

**Gate G0:** all of — resource group + budget alert screenshot exists; Speech and Foundry calls both succeed once from the team machine; clip 1 with script on disk; repo skeleton pushes; secret scan clean.

**If G0 slips:** record clip 1 and create the budget alert above everything else. A late clip costs the whole evidence chain; a late Foundry deployment costs only the LLM phases, which have an offline substitute (fixture-driven prompts).

---

## Phase 1 · Verification core, offline (0:45–2:15)

Goal: the algorithm in `04_VERIFICATION_ENGINE.md` works on a fixture with no Azure dependency. This is the critical path.

**Role 4 leads; Role 3 pairs on `norm()`.**

- [ ] `config.py`: env loading, `MATCH_THRESHOLD=0.88`, min 5 / max 40 tokens, seek lead-in 1000 ms, low-confidence threshold. Fail fast on missing env with a readable message.
- [ ] `transcript_index.py`: `norm()` (NFKC, lowercase, dash/quote folding, hyphen→space, punctuation strip, whitespace collapse); phrase list; flattened token list with word offsets where present, proportional character-length interpolation where absent; `norm_text`.
- [ ] `verify.py`: `locate()` — exact match → fuzzy sliding window (`n−2 … n+2`, score ≥ threshold) → fail; cross-phrase spans return all touched `phrase_ids`; earliest on ties unless `hint_ms`; quotes under 5 or over 40 tokens handled as specified.
- [ ] The 10 unit tests from `04 §8`, including hallucinated quote, repeated phrase (`hint_ms` picks the later one), interpolation, and the not-covered decision table.
- [ ] A tiny CLI that prints the `Evidence` object for a quote, so the team can see the algorithm working without a UI.

**Gate G1:** `pytest -m "not integration"` green; a demo on the fixture shows a quote with a deliberately changed word still verified and a fabricated quote rejected at the right score.

**Common failure:** threshold set low enough that any sentence matches. If the hallucinated-quote test passes at a threshold that also verifies a three-word-changed quote, raise the threshold — do not weaken the test.

---

## Phase 2 · Speech → real transcript (1:00–2:45, overlaps Phase 1)

Goal: A1 has a real, timestamped transcript.

**Role 2 leads; Role 4 supports on the index hand-off.**

- [ ] `audio.py`: extension/size/duration validation (reject > `MAX_AUDIO_MINUTES`, < 20 s, > 50 MB) **before** any Azure call; SHA-256 hashing; optional ffmpeg normalisation to 16 kHz mono.
- [ ] `speech.py`: `POST {endpoint}/speechtotext/transcriptions:transcribe?api-version=2025-10-15`, multipart with `audio` + `definition` (`locales`, `phraseList` for domain terms), key from env.
- [ ] Raise `SpeechError` on non-2xx; timeout; retry 429/5xx with backoff ×3; redact the subscription-key header from all logs.
- [ ] Parse response into `Transcript` / `TranscriptPhrase`, enabling word-level timestamps if the definition field supports it; fall back to interpolation when `words[]` is absent.
- [ ] Save raw JSON to `data/cache/<sha256>.speech.json`; a second run of the same file hits cache with a visible "cached" badge.
- [ ] Dump the transcript as `[mm:ss] text` and cut the 2-minute A1 portion.
- [ ] Log token-free cost telemetry for the Speech call (audio seconds).

**Gate G2:** a real team clip produces a `Transcript` whose timestamps are monotonic and within duration; the first 10 lines read correctly; WER glance-check vs the script is in single digits; cache hit on rerun.

**Contingency:** if fast transcription is unavailable or returns no word offsets, keep the phrase offsets and interpolate — accuracy target becomes ±2 s within a phrase, which still passes ±5 s. Do not switch to the retired v3.x API.

---

## Phase 3 · Notes and key terms (2:45–4:15)

Goal: the two content features, both fully verified before display.

**Role 3 leads; Role 4 wires verification and the regeneration loop.**

- [ ] `llm.py`: Foundry chat client, structured output/JSON mode, `temperature` 0–0.2, capped `max_tokens`, one JSON repair retry, typed `LLMError`, `ContentFilterError` on `finish_reason == "content_filter"`, token usage logged per call.
- [ ] `prompts.py`: shared system prompt (transcript as untrusted data inside delimiters, verbatim quotes 5–40 words, no outside knowledge) + notes/key-term prompt requesting title, overview, 3–6 sections, ≤ 400 words, and **8 key-term candidates** with importance.
- [ ] `notes.py`: verify every bullet; drop unverified; drop sections left with < 2 bullets; enforce the one-page word cap by dropping lowest-value bullets, not mid-sentence truncation.
- [ ] Key terms: request 8, keep first 5 verified; `term` must appear in `norm_text` (plural/hyphen variants allowed); quote must verify and contain or neighbour the term; definition faithfulness check (content-word overlap ≥ 50% or support check); regenerate with failure reasons, max 2 retries.
- [ ] Assertion in code path: `len(key_terms) == 5` and every term present in `norm_text`. Wire it into the eval too.
- [ ] `VerificationReport` populated from these objects — not recomputed, not hard-coded.

**Gate G3:** on clip 1, notes render with every bullet carrying a verified timestamp; exactly 5 terms pass the literal-presence assertion; a deliberately rejected term is shown in the report as replaced.

**If < 5 terms verify:** the prompt is asking for concepts the lecturer did not actually explain. Tighten the prompt (and add phrase-list hints for transcript spelling) before relaxing any check.

---

## Phase 4 · Q&A and the not-covered gate (4:15–5:30)

Goal: A2 and A3 are decidable in code, including near-misses.

**Role 4 leads; Role 3 tunes the prompt.**

- [ ] `qa.py`: model returns `{covered, answer, evidence_quotes, reason}`; every quote goes through `locate()`.
- [ ] Final `covered` = ≥ 1 verified quote **and** relevance gate **and** model did not veto. Model's raw claim is kept only as `model_claimed_covered` for metrics.
- [ ] Relevance gate in order: (a) question's central noun phrase is absent from the whole transcript → refuse immediately; (b) central concept must appear in the quote or its ±1 phrase neighbourhood; (c) ≥ 60% of answer content words present in the evidence window; (d) optional judge call on a ±20 s excerpt at temperature 0.
- [ ] Refusal path renders the literal string `Not covered in this lecture` plus a one-line reason. No suggested answer, no model guess.
- [ ] Decision-table tests (five rows from `04 §5`) as unit tests over a fixture.
- [ ] Log `model_claimed_covered=true but final=false` — this count is a demo asset.

**Gate G4:** 5 covered gold questions answered with timestamps; 5 near-miss and 3 unrelated questions refused; the hallucination-caught count is non-zero on at least one deliberate case.

**Go/no-go:** if near-miss refusal is below 60% at G4, add the judge call **now** and re-measure. Do not proceed to UI polish with a leaky gate — it is 10 points of A3.

---

## Phase 5 · UI and click-to-play (5:30–7:00)

Goal: a judge can see the whole claim in two clicks.

**Role 5 leads; Role 2 supports on audio seeking.**

- [ ] Entry point (`app/main.py`) with upload / "Use sample lecture" / progress states (transcribing → generating → verifying).
- [ ] Tabs: **Notes**, **Key Terms**, **Transcript**, **Ask**, plus collapsible **Verification report**.
- [ ] Sticky audio player; every timestamp chip seeks to `start_ms − 1000` and plays (custom HTML component if the framework's seek is clunky — decide here, once).
- [ ] Transcript rows `[mm:ss] text` with low-confidence amber marker.
- [ ] Q&A answer layout: answer text, `Said at mm:ss ▶`, supporting quote in a block-quote; refusal layout shows the literal string and reason.
- [ ] Key-term cards: term | definition | ▶ mm:ss; flashcard flip is a 15-minute add-on only if G5 is already met.
- [ ] Error surfaces: missing key, unsupported file, too long, Speech failure, content-filter block, JSON failure — friendly text plus "Try again"; partial results still render.

**Gate G5:** a teammate who has not touched the code uploads clip 1, gets notes/terms/transcript, asks a covered question and hears the right sentence; then asks a near-miss and reads `Not covered in this lecture`. Total under ~90 s on a cached rerun.

---

## Phase 6 · Eval harness and evidence numbers (7:00–8:15)

Goal: every number in the Evidence Sheet is produced by one command.

**Role 5 leads; Roles 3 and 4 iterate prompts/thresholds from results.**

- [ ] `eval/clip1_a1_2min.txt` (reference text for the 2-minute slice, trimmed with ffmpeg) and `eval/qa_gold.json` with ≥ 10 covered, ≥ 5 unrelated, ≥ 5 near-miss, ≥ 3 false-premise questions and `gold_windows_ms` per covered question.
- [ ] `run_eval.py --all`: WER, timestamp error (median, max, % within ±5 s), not-covered rates by category, key-term pass rate, hallucination-caught count.
- [ ] Writes `eval/results/a1_wer.json`, `a2_timestamps.json`, `a3_notcovered.json`, `a3_keyterms.json`, `summary.md`.
- [ ] One prompt/threshold iteration at most per failing metric, recorded with before/after numbers in `summary.md`.
- [ ] Screenshots while it runs: `a1_transcript.png`, `a2_q03_answer.png`, `a3_notcovered.png`.

**Gate G6:** `summary.md` exists with real numbers; A1/A2/A3 each marked Pass or Fail with the measured value; any Fail has a stated cause and change.

**Do not** tune thresholds per question to force a pass. A threshold change must be justified on the whole eval set and recorded.

---

## Phase 7 · Safety and robustness (gaps, complete by 8:15)

Goal: the safety section of the sheet is backed by demonstrated behaviour, not prose.

**Role 1 leads; runs in the gaps after G0.**

- [ ] `safety.py`: injection phrase scan (flag, never delete); PII regex (email, phone, ID) with warning + optional masking.
- [ ] Content-filter handling: catch the filter error, show a friendly message, never render blocked output; screenshot of the filter configuration.
- [ ] Secret scan clean across code and git history; `.env` untracked; no key in any screenshot.
- [ ] Failure tests: unset key → friendly message; unsupported/oversize file → rejected before any Azure call; long audio → rejected.
- [ ] Cost line: audio minutes + tokens × current rates, labelled estimate; cache proof.

**Gate G7:** injection clip leaves notes/Q&A unchanged and the report shows the flag; PII clip warns; secret scan output pasted into the sheet.

---

## Phase 8 · Deliverables and demo (8:15–9:30)

Goal: four files, exact names, uploaded early, verified after upload.

- [ ] `1_Evidence_Sheet.pdf` — header, what we built, A1/A2/A3 each with input, pasted output, screenshot, Pass/Fail; Azure AI use; safety/cost table; declarations (AI tools named, synthetic audio, no secrets).
- [ ] `3_Azure_Proof.pdf` — resource group, each deployment, content filter, budget alert; keys and subscription ID hidden.
- [ ] `2_Code.zip` or `2_Code_Link.txt` — code + README (install, env, run app, run eval, run tests); no `.env`, no keys.
- [ ] `4_Demo_Video.mp4` ≤ 5:00 following `08_DEMO_SCRIPT.md`, ending with the **on-the-spot new input**.
- [ ] Upload to `T##_P11_TeamName`; reopen every file to confirm it opens; tick the self-check list.
- [ ] After results are captured: delete `rg-hack-T##`.

**Gate G8:** all four items present with exact names, sheet numbers match `summary.md`, video length under 5:00, secret scan clean, folder name exact.

---

## 4. Dependency graph

```
G0 Azure + clip1 + skeleton
        │
        ├──► Phase 1 verify (fixture) ──► G1
        │                                   │
        └──► Phase 2 Speech ──► G2 ─────────┤
                                            ▼
                              Phase 3 notes + terms ──► G3
                                            │
                                            ▼
                              Phase 4 Q&A + gate ──► G4
                                            │
                                            ▼
                              Phase 5 UI ──► G5
                                            │
                                            ▼
                              Phase 6 eval ──► G6
                                            │
                     Phase 7 safety (parallel, ends by G6) ──► G7
                                            │
                                            ▼
                              Phase 8 deliverables ──► G8
```

Blocking facts to respect: G1 unlocks nothing downstream by itself but gates the *quality* of everything; **G4 is the last chance to fix A3**; G6 is the last chance to fix any metric; G8 has a hard external deadline.

## 5. Cut ladder (decide in advance, not in a panic)

Cut from the top when time runs short:

| Order | Drop | Why it is safe |
|---|---|---|
| 1 | Flashcard mode, exports (F10, F13), section detection | P1/P2, no acceptance test depends on them |
| 2 | Second clip's full eval set | One clip with a full gold set proves A1–A3 |
| 3 | Low-confidence flags (F9) | Nice honesty signal, not scored |
| 4 | Judge call for the relevance gate | Only if near-miss refusal already ≥ 90% without it |
| 5 | Clip 2 entirely (injection/PII demos) | Costs safety *evidence*, not acceptance tests |

**Never cut:** verification, click-to-play timestamps, the not-covered gate, the eval numbers, the secret scan, or the live unseen-input path. Cutting any of these turns a passing app into an unprovable one.

## 6. Risk register → phase response

| Risk | Detect at | Response |
|---|---|---|
| Fast transcription unsupported in region | G0 | Switch region immediately; batch only if no region works |
| No word-level offsets | G2 | Interpolate inside phrases; ±5 s target still holds |
| Model quotes not verbatim | G3 | Tighten quote instruction, keep fuzzy threshold, log verified rate |
| Near-miss leaks through | G4 | Add judge call + central-concept check, re-measure |
| Key terms < 5 verified | G3 | Add phrase-list hints, re-prompt for explicitly explained concepts, never relax the presence check |
| Framework seek is clunky | G5 | Custom HTML audio component with JS `currentTime`; decide once |
| Audio recorded late | G0/G2 | Clip 1 is the only blocker; record it before any coding starts |
| Time overrun | any gate | Descend the cut ladder; upload the code zip and sheet before the video |

## 7. Definition of done (project)

1. A1, A2, A3 pass with numbers in `eval/results/summary.md`, and the sheet quotes those numbers.
2. A fresh clone + `.env` + documented install/run commands reproduces the app and the eval (verified by someone who did not write it).
3. Every displayed note bullet, key term and answer carries verified evidence with a code-computed timestamp; the Verification Report numbers are derived.
4. All four deliverables uploaded with exact names inside `T##_P11_TeamName`; self-check ticked.
5. Every member can explain Speech call → index → locate → gate → UI in under two minutes.

## 8. After submission (out of scope for the hackathon)

Only if the team continues the project: multi-speaker diarisation, longer lectures with chunked transcription, an actual retrieval layer once a single transcript no longer fits the context window, and a persistent library of processed lectures. None of this belongs in the one-day build — adding it now would cost the verification work that wins the marks.
