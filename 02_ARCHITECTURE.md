# 02 · Architecture

Tech is **flexible**. The *contracts* (data shapes, services, verification) are what must hold. A reference stack is suggested; swap freely if the team is stronger elsewhere.

## High-level pipeline

```
Audio upload (mp3/wav/m4a, 5-10 min)
   │
   ▼
[1] Validate + normalise (duration <= 10 min, size cap, optional ffmpeg -> 16 kHz mono wav)
   │
   ▼
[2] Azure AI Speech transcription  ──►  raw JSON (phrases, words, offsets, confidence)
   │
   ▼
[3] Transcript Index (our own data structure)
      - phrases[] with start/end/confidence
      - words[] with start/end (if available)
      - normalised text for matching
   │
   ├──► [4] Foundry model: notes + 5 key terms (JSON with evidence quotes)
   │         │
   │         ▼
   │     [5] Verification Engine: locate each quote in the index, compute timestamp,
   │         drop/regenerate failures, build Verification Report
   │
   └──► [6] Q&A: question → Foundry model (JSON with covered/answer/quotes)
             │
             ▼
         [5] Verification Engine → timestamp(s) or "Not covered in this lecture"
   │
   ▼
[7] UI: audio player + transcript + notes + key terms/flashcards + Q&A + verification report + metrics page
```

## Recommended reference stack (not mandatory)

| Layer | Suggestion | Alternatives |
|-------|-----------|--------------|
| Language | Python 3.11 | TypeScript/Node |
| UI | **Streamlit** (fastest) with `st.audio(start_time=...)` for click-to-play | FastAPI + React/HTMX (smoother click-to-play with an HTML5 `<audio>` element and JS `currentTime`) |
| Speech | Azure AI Speech **fast transcription** REST API | Batch transcription (slower, needs blob storage); Speech SDK |
| LLM | Foundry deployment, e.g. `gpt-4o-mini` or a current small/fast chat model with JSON/structured output | Any Foundry-hosted chat model that supports structured output |
| Matching | `rapidfuzz` + custom token alignment | `difflib`, `regex` |
| WER | `jiwer` | `evaluate` |
| Audio tools | `ffmpeg` (trim 2-min clip, convert) | `pydub` |
| Config | `python-dotenv`, `.env` (gitignored) | OS env vars, Azure Key Vault (optional) |
| Auth | Key from env var for hackathon; **Entra ID / `DefaultAzureCredential`** if time allows (bonus for "no keys") | — |

**Streamlit caveat:** `st.audio(start_time=seconds)` works for seeking but reruns the script. If seamless in-place seeking feels clunky, embed a custom HTML audio component (`st.components.v1.html`) with JS that seeks on chip click. Decide by end of Milestone 2.

## Azure AI Speech: fast transcription (reference)

> Verify against current Microsoft docs; API versions change. Use the latest GA version.

- Endpoint pattern: `POST https://{region}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=<current GA, e.g. 2024-11-15>`
- Auth header: `Ocp-Apim-Subscription-Key: <from env>`
- Body: `multipart/form-data` with
  - `audio`: the file
  - `definition`: JSON string, e.g. `{"locales":["en-US"]}` (consider `en-IN` if the team's accent fits better; optionally enable profanity filter / diarization only if needed)
- Response (fields we rely on; names may vary slightly, check docs):
  - `durationMilliseconds`
  - `combinedPhrases[].text`
  - `phrases[]`: `offsetMilliseconds`, `durationMilliseconds`, `text`, `confidence`, `locale`, `words[]` (each with `text`, `offsetMilliseconds`, `durationMilliseconds`)
- Limits: roughly under 2 hours / 300 MB per file; our 10 min cap is well within it.
- **Save the raw response** to `data/cache/<audio_sha256>.speech.json` (debugging, evidence, cost saving).

Batch transcription is allowed by the brief but needs Blob storage and polling; use only if fast transcription is unavailable in the region.

## Foundry model usage

- Deploy one chat model in the Foundry project (Azure OpenAI-compatible endpoint). Keep the **default content filter on** (screenshot for `3_Azure_Proof.pdf`).
- Use **structured output / JSON mode** with a schema for each call (see `05_PROMPTS.md`).
- `temperature` 0 to 0.2 for all grounded tasks.
- Cap `max_tokens`; log token usage per request (cost evidence).
- Call via the official SDK (`openai` Python package with Azure endpoint, or `azure-ai-inference` / `azure-ai-projects`), whichever the team knows.

## Core data contracts (stable; build everything on these)

```jsonc
// TranscriptPhrase
{
  "id": 17,
  "start_ms": 83120,
  "end_ms": 88640,
  "text": "Gradient descent updates the weights in the direction of the negative gradient.",
  "confidence": 0.93,            // from Speech; null if unavailable
  "words": [                     // optional, if Speech returns them
    {"text": "Gradient", "start_ms": 83120, "end_ms": 83560}
  ]
}

// Transcript
{
  "audio_id": "sha256-...",
  "duration_ms": 412000,
  "locale": "en-US",
  "phrases": [ /* TranscriptPhrase[] */ ]
}

// Evidence (output of the Verification Engine for ONE quote)
{
  "quote_claimed": "text the model returned",
  "quote_matched": "text as it appears in the transcript",
  "start_ms": 83120,
  "end_ms": 88640,
  "phrase_ids": [17],
  "match_score": 0.97,           // 0..1
  "verified": true
}

// Note bullet
{ "text": "...", "evidence": [Evidence], "verified": true }

// Key term
{ "term": "gradient descent", "definition": "...", "evidence": [Evidence], "term_found_in_transcript": true, "verified": true }

// QAResult
{
  "question": "...",
  "covered": true,                  // FINAL value after verification, not the model's raw claim
  "answer": "...",
  "evidence": [Evidence],
  "primary_timestamp_ms": 83120,
  "refusal_reason": null,           // e.g. "no supporting quote found in transcript"
  "model_claimed_covered": true     // kept for the metrics page
}

// VerificationReport
{
  "notes": {"generated": 14, "verified": 12, "removed": 2},
  "key_terms": {"generated": 6, "verified": 5, "removed": 1, "regenerated": true},
  "qa": {"asked": 8, "answered": 5, "refused": 3}
}
```

## Suggested repo layout

```
p11-lecture-notes/
├─ README.md                 # how to run (required by the handout)
├─ .env.example              # placeholders only
├─ .gitignore                # includes .env, data/cache, *.mp3, *.wav if large
├─ requirements.txt
├─ app/
│  ├─ main.py                # UI entry
│  ├─ config.py              # env loading, constants, thresholds
│  ├─ audio.py               # validation, ffmpeg helpers, hashing
│  ├─ speech.py              # Azure Speech client + response parsing -> Transcript
│  ├─ transcript_index.py    # normalisation, phrase/word index, search
│  ├─ llm.py                 # Foundry client, JSON-schema calls, retries
│  ├─ prompts.py             # prompt templates (see 05_PROMPTS.md)
│  ├─ verify.py              # Verification Engine (see 04)
│  ├─ notes.py               # notes + key-terms pipeline with regeneration loop
│  ├─ qa.py                  # Q&A pipeline with not-covered gate
│  ├─ safety.py              # injection screening, PII scan, content-filter error handling
│  └─ ui_components.py       # timestamp chips, badges, flashcards, report
├─ eval/
│  ├─ run_eval.py            # CLI: WER, timestamp error, not-covered rate, key-term check
│  ├─ a1_reference.txt       # script for the 2-minute portion
│  ├─ qa_gold.json           # labelled questions (see 07)
│  └─ results/               # generated reports (commit these; they are evidence)
├─ data/
│  ├─ samples/               # team lecture clips (synthetic, recorded by team)
│  └─ cache/                 # speech JSON + LLM outputs (gitignored)
└─ docs/                     # these markdown files
```

## Configuration (env vars)

```
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
AZURE_SPEECH_LOCALE=en-US
AZURE_FOUNDRY_ENDPOINT=
AZURE_FOUNDRY_KEY=            # or use Entra ID instead
AZURE_FOUNDRY_DEPLOYMENT=
AZURE_FOUNDRY_API_VERSION=
MAX_AUDIO_MINUTES=10
MATCH_THRESHOLD=0.88
```

Never commit real values. `.env.example` contains empty placeholders only.

## Non-functional requirements

- Cold start to first transcript for a 10-minute clip: aim for < 90 s (fast transcription is usually much faster than real time).
- Idempotent caching by audio SHA-256 so repeated demo runs are instant and free.
- Every external call wrapped with timeout, retry (exponential backoff, max 3), and a friendly error message in the UI.
- Deterministic where possible (temperature 0, fixed prompts) so evidence is reproducible.
