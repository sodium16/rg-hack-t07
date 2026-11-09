# 00 · Project Brief

## Problem (P11 · Lecture to Revision Notes)

A student uploads a recorded lecture clip of **5 to 10 minutes**. The app returns:

1. A **timestamped transcript**.
2. A **one-page set of revision notes**.
3. **5 key terms** with definitions **taken from the lecture itself**.
4. A **Q&A box** that answers with the **timestamp** where the answer was said.
5. For unrelated questions: **"Not covered in this lecture"**.

Starting points from the course: Day 4 speech, Day 2 grounded Q&A.

**Named user:** a student revising from a recorded lecture (the app must feel built for them: quick, trustworthy, easy to navigate).

## Must use

- **Azure AI Speech transcription** (batch or fast transcription). *Recommended: fast transcription.*
- **A Foundry model deployment** for notes, key terms and grounded Q&A.

## Must build

- Audio upload and a transcript with timestamps.
- Revision notes and exactly 5 key terms.
- A Q&A box that cites a timestamp.
- "Not covered in this lecture" for unrelated questions.

## Data

- 2 lecture clips recorded by the team (5 to 10 minutes each) with a **script** (ground-truth text) for checking accuracy.
- Synthetic or openly licensed data only. **No real student data.**

## Acceptance tests (must be shown working)

| ID | Test | Pass condition |
|----|------|----------------|
| **A1** | A 2-minute portion of a lecture clip is transcribed | Transcript closely matches what was said (we report WER vs the script) and has timestamps |
| **A2** | A question covered in the lecture is asked | Answer is correct and the **timestamp lands on the right moment** |
| **A3** | A question not covered is asked | Returns **"Not covered in this lecture"**. **Every key term shown appears in the transcript.** |

## Hard rules (from the handout)

- Resources in one resource group named `rg-hack-T##`. **Set a budget alert before starting.** Delete the group after results.
- **Never put keys or secrets** in code, screenshots, docs, or video. Use env vars (`.env` not uploaded). A visible key costs **5 points**.
- Synthetic / openly licensed data only.
- **Keep the content filter on** and handle **at least one risk** (wrong answers, personal data, harmful content). We will handle all three.
- AI coding tools are allowed. **Declare it in the Evidence Sheet.** Every member must be able to explain the code.
- Build what the problem asks. A1 to A3 are what must be shown working.

## Deliverables (exact file names inside folder `T##_P11_TeamName`)

| File | Content |
|------|---------|
| `1_Evidence_Sheet.pdf` (or .docx) | Filled template (~2 pages). **Most important item.** For each of A1, A2, A3: input, pasted output, screenshot, Pass/Fail. |
| `2_Code.zip` or `2_Code_Link.txt` | All code plus short README on how to run. No keys, no `.env`. If GitHub: link + share repo with judges. |
| `3_Azure_Proof.pdf` | Screenshots: resource group, each model deployment, content filter settings, budget alert. Hide keys and subscription ID. |
| `4_Demo_Video.mp4` | Max 5 min, screen recording with voice. Show problem, app working, the three tests, then **ONE new input made up on the spot**. |

Uploads close at the organisers' deadline; the folder becomes view-only. **Upload early.**

## Scoring (100 points)

| Criterion | Pts | What it means | How we win it |
|-----------|-----|---------------|---------------|
| Works as specified | 30 | 10 each for A1, A2, A3 from Evidence Sheet and video | Numbers + screenshots + live demo for each |
| Azure AI use | 25 | Right services, used properly, **answers grounded and checked** | Trust Layer (verification in code), correct Speech usage, confidence scores |
| Engineering and safety | 20 | Clean code, errors handled, keys hidden, PII and harmful content handled, cost controlled | See `06_SAFETY_COST_ENGINEERING.md` |
| Problem fit | 15 | Solves the assigned problem for the named user | Click-to-play, study mode, one-page notes that feel like revision material |
| Demo and clarity | 10 | Clear Evidence Sheet and video, can explain how it works | `08_DEMO_SCRIPT.md`; everyone can explain the verification algorithm |

Process: an automatic review checks all teams, then judges look closely at the top 6 and pick the top 3.

## Self-check before upload

- [ ] All four items exist with exact names.
- [ ] A1, A2, A3 each have input, pasted output, screenshot, Pass/Fail.
- [ ] No key or secret anywhere (code, screenshots, video, git history).
- [ ] Video is <= 5 min and includes the new on-the-spot input.
- [ ] Files are in the team folder named exactly `T##_P11_TeamName`.
