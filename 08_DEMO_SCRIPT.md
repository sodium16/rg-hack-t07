# 08 · Demo Video Script (max 5:00, screen recording with voice)

The handout requires: **the problem, the app working, the three tests, then ONE new input made up on the spot.** The script below hits all of that and spends the most time on what scores.

Rehearse twice. Record in one take if possible. Pre-load the cached sample so waiting is minimal (but show one real upload). **Hide `.env`, terminals with keys, and Azure portal key pages.**

| Time | Scene | What you show / say |
|------|-------|---------------------|
| 0:00 to 0:25 | **Problem + pitch** | "Students re-watch hour-long recordings to find one explanation. Our app turns a lecture clip into notes, key terms and answers, and *every sentence is traced to a second in the audio, or it isn't shown.*" Show title screen. |
| 0:25 to 0:55 | **Upload + pipeline** | Upload Clip 1 (or 'Use sample'). Show progress: transcribe → notes → verify. Mention Azure AI Speech fast transcription + Foundry model. |
| 0:55 to 1:25 | **A1 · Transcript** | Show the timestamped transcript (2-min portion). Show WER table (e.g. "WER 6.1% vs our script"). Click 2 timestamps; audio jumps. Point to an amber low-confidence flag. |
| 1:25 to 2:00 | **Notes + key terms** | One-page notes with ✓ chips. Open the **verification report**: "14 bullets generated, 2 removed as unverifiable." Show 5 key terms; say "each term is asserted to appear in the transcript; here's the check passing." |
| 2:00 to 2:40 | **A2 · Covered question** | Ask a covered question. Answer + "Said at 03:42 ▶". **Click: audio plays exactly that sentence.** Show the quote. Mention "timestamp comes from locating the quote in the Speech output, not from the model." Flash the timestamp-error table (median 1.3 s, 10/10 within ±5 s). |
| 2:40 to 3:20 | **A3 · Not covered** | Ask unrelated question → "Not covered in this lecture". Ask the **near-miss** → same, show reason: "no supporting quote found" and the metric "model claimed covered; verifier overruled". |
| 3:20 to 3:50 | **Safety** | Switch to Clip 2: the injection sentence is ignored (show report flag). PII warning on the fake phone number. Content filter on (one-second cut to Azure proof screen, keys hidden). Budget alert mention. |
| 3:50 to 4:40 | **ONE NEW INPUT (live)** | A teammate who hasn't pre-tested shouts a **brand-new question** (or the team records a 20 s fresh clip on the spot and uploads it). Show it working through the pipeline. Choose a new question that is covered, then ask one more that's a near-miss, if time. **Must be something not used in any earlier test.** |
| 4:40 to 5:00 | **Close** | "Measured, verified, and safe: WER x%, y% timestamps within 5 s, z% not-covered correct. Every claim traceable." Show the metrics tab. End card with team name. |

## Roles during recording
- **Driver** (one person): operates the app.
- **Narrator** (one person): speaks; can be the same person if comfortable.
- **Surprise-input person**: prepares nothing; picks the new input in the moment (but the team must have confirmed the app is stable beforehand).

## Pre-flight checklist
- [ ] App runs from a clean start; cached samples loaded; internet stable (the new input needs live Azure calls).
- [ ] Browser zoom ~125%; dark/light theme legible; notifications off.
- [ ] No keys on screen (close `.env`, hide portal key blades).
- [ ] Audio volume set so click-to-play is audible in the recording.
- [ ] Timer: total ≤ 5:00 (judges may stop watching at 5:00).
- [ ] Export as `4_Demo_Video.mp4`.

## If something fails live
Stay calm; show the error handling (friendly message), retry once, and move on. Graceful failure beats a crash. Do **not** swap in hard-coded results.

## Explain-ability prep (for Q&A with judges)
Every member should be able to answer:
1. How do you compute the timestamp? (locate the model's quote in the Speech word index.)
2. How do you decide "not covered"? (verification + relevance gate; model can't override.)
3. How do you ensure key terms come from the lecture? (literal presence assertion + quote check.)
4. What happens on prompt injection? (data delimiters, flag, verification gate.)
5. What does it cost per run and how is cost controlled? (tokens/minutes, caching, budget alert.)
6. What are the limitations? (accents/noise → confidence flags; very long audio; single speaker.)
