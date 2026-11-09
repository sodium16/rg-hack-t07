# 06 · Safety, Privacy, Cost and Engineering Quality

Scoring bucket: **Engineering and safety (20 pts)**. The handout requires handling **at least one** risk; we handle **all three** (wrong answers, personal data, harmful content) and document each in the Evidence Sheet.

## Risk register

| Risk | Where it shows up | Mitigation (implemented) | Evidence to capture |
|------|-------------------|--------------------------|---------------------|
| **Wrong / hallucinated answers** | Notes, key terms, Q&A | Verbatim-quote verification, code-computed timestamps, relevance gate, "Not covered" refusal, optional judge call | Verification report; "N hallucinations caught" metric; near-miss test results |
| **Prompt injection via audio** | Lecturer says "ignore previous instructions" | Transcript delimited as data; system rule 1; injection regex flag; verification still gates output | Injection clip test (screenshot + report line) |
| **Harmful content** | Audio or questions containing hate/violence/self-harm | Foundry **content filter ON** (default or stricter); catch the filter's error/finish_reason and show a friendly message; do not display blocked output; Speech profanity masking option | Content filter screenshot in `3_Azure_Proof.pdf`; test with a mildly policy-triggering question showing graceful handling |
| **Personal data (PII)** | Lecturer names, emails, phone numbers in audio | Only synthetic/team-recorded audio (stated in sheet); PII scan on transcript (regex for email/phone/IDs, optionally Azure AI Language PII detection); mask in the display option + warn before processing; no audio or transcripts stored beyond local cache; no logging of full transcripts | PII scan results on a clip containing a fake phone number/email |
| **Secret leakage** | Code, screenshots, video, git history | `.env` gitignored, `.env.example` placeholders, pre-commit secret scan (e.g. `gitleaks`/`detect-secrets`), screenshot checklist, Entra ID auth if time allows | Clean scan output |
| **Cost runaway** | Repeated runs, long audio | Budget alert on resource group; 10 min cap; cache by audio hash; `max_tokens` caps; small model; log token usage and estimated cost per run | Budget alert screenshot; cost table in sheet |
| **Service failure** | Speech/LLM timeouts, throttling | Timeouts, exponential backoff retries (max 3), clear UI error states, partial results shown if later step fails | Simulated failure test (unset key → friendly error) |

## Azure setup checklist (for `3_Azure_Proof.pdf`)

1. Create resource group `rg-hack-T##` (use the real team number).
2. **Create a budget + alert first** (e.g. small amount, alerts at 50/80/100%). Screenshot.
3. Create Azure AI Speech resource (or multi-service AI Services resource) in a region supporting fast transcription. Screenshot overview (hide keys).
4. Create Foundry project + model deployment(s): chat model (required), embedding model (optional). Screenshot each deployment.
5. Content filter: show the filter configuration attached to the deployment. Screenshot.
6. Keep screenshots free of keys and the subscription ID (blur/crop).
7. After results: delete the resource group.

## Secrets and config

- All config via env vars (`config.py` reads them; fail fast with a clear message if missing).
- `.gitignore` must include: `.env`, `.env.*` (except `.env.example`), `data/cache/`, `*.pem`, `*.key`, large media.
- Run a secret scan before every push and before zipping the code. **A visible key costs 5 points.**
- Never print keys in logs; redact `Ocp-Apim-Subscription-Key` and `api-key` headers in any debug output.
- Do not record the terminal while `.env` is open.

## Error handling standards

- Every Azure call: timeout (e.g. 60 s for Speech, 30 s for LLM), retry on 429/5xx with jitter, raise typed errors (`SpeechError`, `LLMError`, `ContentFilterError`).
- UI maps typed errors to friendly messages with a "Try again" action. No stack traces for the user.
- LLM JSON parse failure → one repair retry ("return valid JSON only"); then fail gracefully.
- Validate every model output against a Pydantic (or similar) schema before use.
- If Notes succeed but Q&A fails, still show Notes.

## Cost controls and cost reporting

- Cache: `data/cache/<sha256>.speech.json`, `.notes.json`.
- Show a "Run cost" line in the UI/metrics: audio minutes × Speech rate + tokens × model rate (use the current published prices; label as estimate).
- Prefer a small, fast model; one combined notes+terms call; Q&A with the full transcript (10 min ≈ 1.5k to 2k words, cheap) rather than adding retrieval infrastructure.
- Delete the resource group after results (handout requirement).

## Code quality expectations

- Type hints, docstrings on public functions, small modules per `02_ARCHITECTURE.md`.
- Unit tests for `verify.py`, `transcript_index.py`, `safety.py` (offline, no Azure needed).
- `README.md` with: prerequisites, env setup, install, run app, run eval, run tests, and the architecture diagram.
- Linting/formatting (`ruff`, `black`) and a `make check` or script.
- **Every member can explain the code.** Keep it simple enough that this is true. Declare AI-tool use in the Evidence Sheet.

## Responsible-AI statement (paste-ready for the Evidence Sheet)

> The app only presents content it can match to a verbatim quote in the lecture transcript, with timestamps computed from Azure AI Speech output. Unsupported claims are removed, and out-of-scope questions return "Not covered in this lecture". The Foundry content filter is enabled. Only synthetic, team-recorded audio is used; no real student data is processed or stored. Keys are held in environment variables and excluded from source control.
