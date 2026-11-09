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
