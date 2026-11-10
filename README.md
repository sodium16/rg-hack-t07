# P11 · Lecture to Revision Notes — Agent Starter Pack

You are an engineering agent helping a team of 5 build a one-day hackathon app (AI-103 Hackathon, problem P11). Read these files **in order** before writing code.

| # | File | Read it for |
|---|------|-------------|
| 0 | `00_PROJECT_BRIEF.md` | The problem, rules, deliverables, scoring. Non-negotiables. |
| 1 | `01_VISION_AND_DIFFERENTIATORS.md` | **What makes us win.** The "Trust Layer" idea and every standout feature. |
| 2 | `02_ARCHITECTURE.md` | Pipeline, components, data contracts, tech options (flexible). |
| 3 | `03_FEATURE_SPECS.md` | Each feature with behaviour and acceptance criteria. |
| 4 | `04_VERIFICATION_ENGINE.md` | The core grounding/verification algorithm (the heart of the project). |
| 5 | `05_PROMPTS.md` | Starting prompts and JSON schemas for the Foundry model. |
| 6 | `06_SAFETY_COST_ENGINEERING.md` | Safety, privacy, secrets, cost control, error handling. |
| 7 | `07_TESTING_AND_EVIDENCE.md` | A1/A2/A3 tests, metrics, eval harness, Evidence Sheet material. |
| 8 | `08_DEMO_SCRIPT.md` | The 5-minute demo video, second by second. |
| 9 | `09_TASK_PLAN.md` | Milestones, team split, backlog, definition of done. |

## One-line pitch (keep this in mind for every decision)

> **"Every sentence this app shows you can be traced to a second in your lecture, or it doesn't show it."**

## Guiding principles

1. **Grounded and checked beats clever.** Verified in code, not just prompted.
2. **Never fake or hard-code results.** It disqualifies the team from the top 3.
3. **Measured beats claimed.** Numbers (WER, timestamp error, not-covered rate) go in the Evidence Sheet.
4. **Tech is flexible, contracts are not.** Pick any language/framework, but the services in "Must use" and the data contracts in `02_ARCHITECTURE.md` stay.
5. **Demo-ability.** If a feature cannot be shown in the 5-minute video, it scores nothing. Build for the demo.
6. **No secrets, ever.** Keys live in environment variables only.

## Assumptions to confirm with the team (don't block on them, pick defaults)

- Language of lectures: default English (en-US / en-IN). Make locale configurable.
- Default stack suggestion: Python 3.11, Streamlit (or FastAPI + small React front-end if the team prefers). See `02_ARCHITECTURE.md`.
- Team number `T##` and team name are unknown; use placeholders and make them easy to replace.

## Current build state

Phases 1–4 of `ROADMAP.md` are built and **verified against the live Azure resources** (100 offline tests, no credentials needed for the suite): verification engine, Speech client, notes/key terms, Q&A gate, plus injection/PII screening. On a synthetic 36-second lecture clip: fast transcription returned 8 phrases and 98 word offsets in 3.8 s, notes kept 6 of 7 bullets and 5 of 5 key terms with computed timestamps, covered questions answered with clickable timestamps, and unrelated questions refused with the literal `Not covered in this lecture`. The Streamlit UI (`main.py`) shows the audio player, notes, key terms, transcript, Q&A and the verification report, with every timestamp a click-to-play chip (verified: the 0:19 chip seeks to 18.4 s and plays). The A1 WER cut and A2/A3 evidence still need the team's real clip.

| Module | What it does |
|---|---|
| `app/transcript_index.py` | `norm()`, token index, word offsets with interpolation, key-term variants |
| `app/verify.py` | `locate()` (exact → fuzzy → fail), coverage decision table, `seek_ms()` |
| `app/audio.py` | extension/size/duration validation, SHA-256, duration probe |
| `app/speech.py` | fast transcription, phrase lists, cache, retries, typed errors |
| `app/llm.py` | Foundry chat with JSON mode, one repair retry, content-filter handling |
| `app/notes.py` | notes + 5 key terms with verification and bounded regeneration |
| `app/qa.py` | grounded answers, relevance gate, literal `Not covered in this lecture` |
| `app/safety.py` | injection and PII flags, display masking |

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows Git Bash; use .venv/bin/python elsewhere
.venv/Scripts/python.exe -m pytest -q                          # 100 offline tests
.venv/Scripts/python.exe -m pytest -m integration -q           # live end-to-end (needs .env + a clip)
.venv/Scripts/python.exe eval/run_eval.py --clip data/samples/clip1.m4a --all  # A1/A2/A3 numbers
.venv/Scripts/python.exe -m streamlit run main.py               # the browser UI
.venv/Scripts/python.exe -m app.pipeline data/samples/lecture.m4a  # whole pipeline on one clip
.venv/Scripts/python.exe -m app.pipeline data/samples/lecture.m4a -q "What is gradient descent?"
.venv/Scripts/python.exe -m app.verify "a quote to locate"     # prints the Evidence object
```

Everything above runs without `.env`: the Azure clients are only constructed when called, and the tests use fake transports. Live calls need the variables listed in `.env.example`; see `AZURE_SETUP_TEMP.md` for provisioning.

**Next step: the team's recorded clip and script.** The pipeline is live-verified on a synthetic clip only, so A1 (WER against the spoken script), the 2-minute A1 cut, and the A2/A3 screenshots cannot be produced until that audio exists. Until then the UI is developed against the cached transcript in `data/cache/`.

`ROADMAP.md` is the build order. `docs/DECISIONS.md` records departures from the planning docs.
