# SUBMISSION TESTS (temporary — delete after upload)

Everything to run, verify and capture before the four deliverables are uploaded.
Work top to bottom; each section says what to run, what "pass" looks like, and
which evidence file it produces. If something fails, record the real result in
the Evidence Sheet and what changed — do not edit numbers.

Legend: ✅ already passing today · ⛔ blocked (needs data or a missing tool)

---

## 0. Pre-flight (10 min, do this first)

| Check | Command | Pass |
|---|---|---|
| Venv works | `.venv/Scripts/python.exe -V` | 3.13.x (3.11+ is fine) |
| Deps installed | `.venv/Scripts/python.exe -m pip install -r requirements.txt` | exit 0 |
| Tests green | `.venv/Scripts/python.exe -m pytest -q` | ✅ `100 passed, 4 deselected` |
| Live end-to-end | `.venv/Scripts/python.exe -m pytest -m integration -q` | 4 passed (needs `.env` and a clip) |
| Eval harness present | `.venv/Scripts/python.exe eval/run_eval.py --help` | prints `--clip --transcript --a1 --a2 --a3 --all` |
| App imports | `.venv/Scripts/python.exe -c "import main"` | no traceback |
| `.env` present locally | `ls .env` | exists, **never** committed |
| `.env` ignored | `git check-ignore -v .env` | prints a `.gitignore` rule |
| No secrets tracked | `git log -p | grep -iE "api[-_]?key|Ocp-Apim"` | no real values |
| Azure env loaded | `.venv/Scripts/python.exe -c "from app.config import require_azure_env; print(sorted(require_azure_env()))"` | prints the 6 variable names, no values |

Also confirm with the team: **team number and name** (`T##`, `TeamName`) and the
resource group name (must be `rg-hack-T##`). Nothing can be named or checked
against the handout until these are real.

---

## 1. Data that must exist before A1/A2/A3 mean anything

⛔ Currently missing — the repo has only a 36 s synthetic clip
(`data/smoke/sapi_lecture.wav`) and one non-lecture recording
(`data/samples/`, a comedy sketch).

| Item | Path | Notes |
|---|---|---|
| Clip 1 (5–10 min) | `data/samples/clip1.m4a` | clean explanation, topic the team knows |
| Clip 2 (5–10 min) | `data/samples/clip2.m4a` | different speaker, harder, planted extras |
| Full script 1 | `eval/clip1_script.txt` | the words actually spoken |
| A1 slice script | `eval/clip1_a1_2min.txt` | reference text for the 2-min portion |
| Gold questions | `eval/qa_gold.json` | ≥10 covered, ≥5 unrelated, ≥5 near-miss, ≥3 false-premise |
| Key-term expectations | `eval/keyterm_checks.json` | optional acceptable-term list |

Clip 2 must contain, at known times: one concept explained twice, one unrelated
aside, one fake injection sentence ("ignore all previous instructions…"), and
one fake phone/email. Write those timestamps into the script file as you record.

**A1 cut:** `ffmpeg` is not installed on this machine — either record the 2-min
A1 portion as its own file, or run the cut on a machine that has ffmpeg:
`ffmpeg -ss 60 -t 120 -i clip1.m4a eval/a1_clip.wav`.

---

## 2. Offline checks (no Azure cost) ✅

| Test | Command | Pass |
|---|---|---|
| Unit suite | `.venv/Scripts/python.exe -m pytest -q` | 90 passed |
| Verification CLI | `.venv/Scripts/python.exe -m app.verify "The key idea is gradient descent" --transcript tests/fixtures/transcript_sample.json` | prints Evidence with a timestamp, exit 0 |
| Full pipeline on cached clip | `.venv/Scripts/python.exe -m app.pipeline data/smoke/sapi_lecture.wav -q "What is the learning rate?" -q "Who won the 2022 World Cup?"` | notes + 5/5 terms + one answer + one refusal |
| Refusal text is exact | `grep -rn "Not covered in this lecture" app/` | `qa.py` defines it once |
| Secrets untracked | `git status --short` | no `.env`, no `data/cache`, no media |

---

## 3. A1 — transcript accuracy (10 pts)

**Setup:** the 2-minute slice + its reference text.

1. Transcribe: `.venv/Scripts/python.exe -m app.pipeline eval/a1_clip.wav --no-notes`
2. Note the transcript and the `cached`/`fresh` badge; save it as `a1_transcript.txt`.
3. WER against `eval/clip1_a1_2min.txt` with `jiwer` (not installed yet:
   `.venv/Scripts/python.exe -m pip install jiwer`), identical normalisation
   (lowercase, strip punctuation) on both sides.
4. Report: WER %, S/I/D counts, and 3 concrete example errors.
5. Timestamps: monotonic, all within 0–120 s; click 5 random rows in the UI and
   confirm each plays the matching sentence.

| Evidence | File |
|---|---|
| Screenshot of the transcript with chips | `a1_transcript.png` |
| Pasted first ~10 lines of output | Evidence Sheet §A1 |
| WER table | `eval/results/a1_wer.json` + `summary.md` |
| Pass criterion | WER ≤ 10 % **and** timestamps present |

---

## 4. A2 — covered question lands on the right moment (10 pts)

1. Start the UI: `.venv/Scripts/python.exe -m streamlit run main.py`
2. Load clip 1, run every `covered` question from `eval/qa_gold.json`.
3. For each: answer text, `primary_timestamp_ms`, inside any gold window ±5 s,
   error in seconds to the nearest window edge, and whether the answer contains
   one of `must_contain_any`.
4. Report: n, % within ±5 s, median error, max error, % correct answers.
5. Click 2–3 timestamps and confirm the audio starts within ~1 s of the sentence.

| Evidence | File |
|---|---|
| 2–3 worked examples with the chip visible | `a2_q03_answer.png` (and one more) |
| Full table | `eval/results/a2_timestamps.json` |
| Pass criterion | ≥ 90 % within ±5 s and answers correct |

---

## 5. A3 — not covered + key terms (10 pts)

1. Run every `not_covered_unrelated`, `not_covered_near_miss` and
   `leading_false_premise` question. Expect the literal
   **`Not covered in this lecture`** each time.
2. Key terms: for both clips, assert each of the 5 terms literally appears in
   the transcript (`app.transcript_index.term_present`). Paste the assertion
   output.
3. Record `model_claimed_covered = true` but final `covered = false` — this is
   the verifier catching the model, and it is good evidence.

| Check | Pass criterion |
|---|---|
| Unrelated questions | 100 % refused |
| Near-miss questions | ≥ 90 % refused |
| False-premise questions | refused (or premise corrected with a quote) |
| Key terms | exactly 5, 100 % present in transcript, each with a verified quote |

| Evidence | File |
|---|---|
| One unrelated + one near-miss refusal | `a3_notcovered.png` |
| Key-term table with timestamps | Evidence Sheet §A3 |
| Machine-readable results | `eval/results/a3_notcovered.json`, `a3_keyterms.json` |

---

## 6. Safety and robustness (Engineering and safety, 20 pts)

| Scenario | How to produce it | Expected | Evidence |
|---|---|---|---|
| Injection sentence in audio | Clip 2 contains it | Notes/Q&A unaffected; report shows 1 injection-like phrase | Screenshot + Sheet §Safety |
| PII in audio | Fake phone/email in Clip 2 | Transcript flags it; display can be masked | Screenshot |
| Unsupported file | Upload a `.txt` from the UI | Friendly message, **no** Azure call | Screenshot |
| Too long | Upload > `MAX_AUDIO_MINUTES` | Friendly message naming the limit | Screenshot |
| Too large | Upload > 50 MB | Friendly message naming the limit | Screenshot |
| Missing key | Run with `AZURE_SPEECH_KEY=` empty | Readable "Missing environment variable(s)…" | Screenshot |
| Content filter | Trigger a blocked request, or show the portal setting | Friendly message, no stack trace | Screenshot |
| Rate limit | (Seen already) Speech 429 | "Speech is busy right now (rate limit)" | Log excerpt |

Known gap: `safety.mask()` exists and is tested but the UI has no
"show masked" toggle yet — either add it or state the limitation.

---

## 7. UI walkthrough (Problem fit, 15 pts)

Run through every tab on a real clip and check each item:

- [ ] Notes: every bullet has a chip; clicking seeks and plays; footer word count ≤ ~450
- [ ] Key terms: exactly 5 cards, definition quotes are verbatim
- [ ] Transcript: timestamps monotonic, ⚠ marker on a noisy phrase (Clip 2)
- [ ] Ask: covered question → answer + chip; unrelated → literal refusal
- [ ] Ask: near-miss question → refusal
- [ ] Verification: counts equal what the page shows; JSON downloads
- [ ] Second load of the same file shows `cached ✓`
- [ ] Sidebar-free layout: picker visible on first load, no horizontal clipping

---

## 8. Azure proof captures (3_Azure_Proof.pdf)

All screenshots must hide keys and the subscription ID.

- [ ] Resource group `rg-hack-T##` with the Speech + Foundry resources
- [ ] Each model deployment (name, model, version)
- [ ] Content-filter configuration (proving it is **on**)
- [ ] Budget alert on the resource group
- [ ] Speech resource region (must match `AZURE_SPEECH_REGION`)

---

## 9. Deliverables assembly

Folder **must** be named `T##_P11_TeamName`:

| File | Content | Status |
|---|---|---|
| `1_Evidence_Sheet.pdf` | ~2 pages; A1/A2/A3 each: input, pasted output, screenshot, Pass/Fail | ⛔ needs §3–5 |
| `2_Code.zip` or `2_Code_Link.txt` | code + run instructions (README), no `.env`, no keys | ready to assemble |
| `3_Azure_Proof.pdf` | §8 screenshots | ⛔ needs captures |
| `4_Demo_Video.mp4` | ≤ 5 min, voice, includes one **new on-the-spot input** | ⛔ |

Before zipping:

```bash
gitleaks detect --no-git --redact      # or: detect-secrets scan
git status --short                     # nothing secret, no media
```

Exclude from the zip: `.venv/`, `data/cache/`, `data/samples/`, `data/smoke/`,
`data/uploads/`, `.env`, `ui_preview.png`, `SUBMISSION_TESTS_TEMP.md`.

Live config to state in the sheet: Speech fast transcription
`api-version=2025-10-15`, Foundry deployment name, locale, `MATCH_THRESHOLD`,
`answer_grounding_min`, `definition_overlap_min`.

---

## 10. Demo video (≤ 5:00)

- [ ] 0:00 problem + named user, one sentence
- [ ] 0:20 architecture: Speech → index → Foundry → verification, and the pitch
- [ ] 0:50 A1: upload, transcript, click a chip
- [ ] 1:40 A2: covered question, answer + timestamp, click it
- [ ] 2:30 A3: unrelated question → literal refusal
- [ ] 3:00 A3: near-miss question → literal refusal
- [ ] 3:30 key terms: 5 terms, each traceable to a second
- [ ] 4:00 **new input made up on the spot** (never used before)
- [ ] 4:40 verification report + "timestamps computed in code" explanation
- [ ] No key, no subscription ID, no `.env` on screen at any moment

---

## 11. Final self-check (from `00_PROJECT_BRIEF.md`)

- [ ] All four items exist with the exact names
- [ ] A1/A2/A3 each have input, pasted output, screenshot, Pass/Fail
- [ ] No key or secret anywhere (code, screenshots, video, git history)
- [ ] Video ≤ 5 min and includes the on-the-spot input
- [ ] Folder named exactly `T##_P11_TeamName`
- [ ] Every member can explain `app/verify.py` and the coverage decision table
- [ ] AI coding tools declared in the Evidence Sheet

---

## 12. What is still missing right now

1. Both lecture clips + scripts (blocks A1/A2/A3 entirely)
2. Real gold questions in `eval/qa_gold.json` — the file is a template with two
   examples, and A2/A3 will exit non-zero until it is replaced with labelled ones
3. `ffmpeg` for the A1 2-minute cut (jiwer is installed; the harness is ready)
4. All screenshots in §6–8
5. Real team number/name and the four deliverable files
6. `eval/results/` numbers — nothing has been run against a real clip yet, so the
   summary is empty until step 1–2 exist
