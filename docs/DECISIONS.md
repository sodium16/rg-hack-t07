# Decisions and departures from the planning docs

Newest first. Keep entries short: what changed, why, and what it affects.

## 2026-11-11 — Real-clip eval adjustments

- **Raised `llm_max_tokens` from `1600` to `4096` (`app/config.py`).** On the 5-minute `clip1.mp3` lecture (49 phrases), notes + quotes + 8 key-term candidates required `1868` completion tokens and truncated mid-JSON at `1600`. `4096` gives headroom up to the 10-minute cap without mid-JSON cuts.
- **Made `instructions?` / `rules?` optional-plural in `app/safety.py`.** Live Azure Speech transcribed `"ignore all previous instructions"` on `clip2.mp3` as `"ignore all previous instruction"` (singular). Allowing `s?` catches natural ASR inflection variance without broadening false positives.

## 2026-11-10 — Eval harness, integration test and UI trust details

- **Evaluation lives in `eval/run_eval.py` and imports `app/` read-only.** Gold questions, reference scripts and results sit under `eval/`, never in `app/`, per `07_TESTING_AND_EVIDENCE.md`; nothing in the product can leak an expected answer. Flags: `--clip`, `--transcript`, `--a1`, `--a2`, `--a3`, `--all`, `--refresh`, `--a1-range`. It writes a1/a2/a3 JSON plus `summary.md`, and exits non-zero when a target fails so it can gate a submission.
- **WER uses `jiwer` with identical normalisation on both sides** (lower case, punctuation stripped through `norm()`), and the A1 section also asserts timestamps are monotonic and inside the audio duration. `jiwer` joins the dependencies; the harness raises a readable message when it is missing instead of failing on the import.
- **The integration smoke test is excluded from the default suite by `addopts`.** Previously a plain `pytest` collected the live test and called Azure with whatever credentials were present; now `pytest` is 100 offline tests and the live run is explicit (`-m integration`), skipped automatically when credentials or the clip are absent.
- **`QAResult` gained a defaulted `usage` field** (an extension, not a rename) so the UI can total prompt/completion tokens per run. Existing construction sites are unchanged.
- **Trust details in the UI:** a transcript toggle that applies `safety.mask()` to the displayed copy only, and an unclear-audio tag on notes and answers whose evidence rests on a phrase below `low_confidence_threshold`. Verification keeps using the unmasked transcript, so evidence and timestamps are unaffected.

## 2026-11-09 — Live Azure bring-up (Speech + Foundry)

- **The chat endpoint is discovered from the configured URL, not hard-coded.** `AZURE_FOUNDRY_ENDPOINT` is the *project* URL, and on this resource only the OpenAI v1 route serves chat: `{root}/openai/v1/chat/completions` returns 200, the legacy `{root}/openai/deployments/<name>/...` returns 404, and the project-scoped legacy form returns 400 "API version not supported". `_chat_target()` therefore maps `/openai/v1`, `/api/projects/...` and any `.services.ai.azure.com` host to the v1 route (sending `model` = deployment name, plus both `api-key` and a bearer token) and keeps the legacy route for older resources. Documented here because `02_ARCHITECTURE.md` still describes only the legacy shape.
- **429s wait for `Retry-After`, capped at 30 s.** The first live Speech call was throttled with `{"code":"TooManyRequests","message":"Resource Exhausted"}` and succeeded on a manual retry; a fixed doubling delay either wastes time or hammers a throttled resource. The cap keeps a demo from stalling. Speech maps the failure to a plain "Speech is busy right now (rate limit)" message.
- **`max_tokens` still falls back to `max_completion_tokens`.** Both are accepted by `gpt-4.1-mini` (probed), but keeping the fallback costs nothing and protects a deployment swap the day of the demo.
- **Key-term regeneration now receives the transcript.** The retry prompt asked for terms in the lecture without showing it, so the model guessed words that were never spoken and the presence check rejected them forever. With the fenced transcript it produced 5/5 verified terms on the first retry; the retry logic and the presence rule are unchanged.
- **Inflections are folded before any overlap gate (`stem()` in `app/language.py`).** "update" vs "updates", "grade" vs "grading" were splitting matched word sets and pushing correct content under the thresholds, notably in the definition-grounding check. Stemming is deterministic and applies to both sides of every comparison; the 60% thresholds are unchanged.
- **Words *about* the material are not content words either.** Answers routinely read "a shrimp fried the rice, as confirmed earlier in the transcript of the recording". `confirm`, `transcript`, `conversation`, `dialogue`, `recording`, `quote`, `beginning`, `end`, `earlier` are now in `GENERIC_QUESTION_WORDS`, so they neither ground nor unground an answer. Found on the first non-lecture upload: a question answered verbatim in the transcript was refused five times out of five at 0.50 overlap, purely because of that clause.
- **`-ied` verbs now fold to the base form (`stem()`).** "fried"/"studied"/"applied" previously collapsed to "fri"/"studi"/"appli" while "fry"/"study"/"apply" stayed whole, so a question asked in the base form could miss a past-tense transcript. The substring order matters: `ied` is handled before the generic `ed` strip.
- **Answer grounding is measured against the ±20 s passage, and discourse words are not counted.** A correct answer explains, so it reuses words the lecturer said a few seconds before or after the quoted sentence ("landscape", "slope", "diverge") and is held together by connectives ("because", "instead", "toward"). Measuring only the quoted phrases plus one neighbour rejected two correct answers at 0.53 and 0.38 overlap. The gate now compares the answer's content words with the same excerpt the judge sees (`_excerpt`, ±20 s around the evidence, `04` §3), and `DISCOURSE_WORDS` are excluded from content words. The 0.60 threshold is unchanged, and an answer carrying outside knowledge still fails ("bananas … potassium" scores 0).

## 2026-11-09 — Phases 2–4 and safety screening built

- **No Azure SDK; `requests` + a small retry wrapper (`app/net.py`).** The docs allow either, and a hand-rolled transport keeps retry, redaction and the 400 `max_completion_tokens` fallback directly testable with fake sessions. No credentials are needed for any test.
- **Duration via `mutagen`, not `ffprobe`.** This machine has no ffmpeg/ffprobe, and mutagen reads duration from m4a/mp3/wav in pure Python. `ffmpeg` is still needed later to cut the 2-minute A1 clip from the master recording.
- **`max_tokens` is retried as `max_completion_tokens` on a 400.** Newer Foundry deployments reject the older field; without the fallback the first live run would fail for a reason unrelated to the app.
- **The judge call is behind `USE_JUDGE` (default off).** The deterministic gate runs first; the judge only matters if near-miss refusal measured below target at G4. Turning it on without re-measuring would add cost with no evidence.
- **Notes trimming drops whole bullets, then whole sections.** It never truncates mid-sentence, and it keeps at least two bullets per section so a "section" is not a single orphan claim.
- **Key-term rejection reasons are fed back into the retry prompt** ("term does not appear…", "definition is not built from the lecture's own words"), per 05. Accepted terms are excluded, so a retry cannot re-submit them.
- **Safety scans flag, they never rewrite.** `mask()` is applied only to a display copy; the transcript used for verification keeps the original text, so evidence and timestamps stay truthful.
- **`quote_matched` is rebuilt from matched token surface forms**, so punctuation *inside* a phrase is not reproduced (e.g. a comma disappears). Timestamps and phrase ids are unaffected. This is for display only; if exact punctuation is needed later, slice the original phrase text instead.
- **Definition grounding uses a 50% content-word overlap** with the quote plus one neighbouring phrase (04 §4), not the optional LLM support check. It is deterministic, free, and testable; the judge can be added later if real candidates get wrongly rejected.

## 2026-11-09 — Phase 1 (verification core) built

- **Added `app/models.py`.** `02_ARCHITECTURE.md` lists no models module, but the contracts are needed by the index, the verifier, the Speech parser and the UI. One small module beats re-defining dataclasses per file. Contracts themselves are unchanged.
- **Fast transcription targets `api-version=2025-10-15`, not `2024-11-15`.** The current GA version is newer than what `02_ARCHITECTURE.md` quotes; v3.x retired 31 March 2026. Verified against the REST reference before coding.
- **`norm()` keeps decimal points between digits** (so `3.14` stays one token) and keeps intra-word apostrophes. The docs specified apostrophes but not decimals; without this, numbers would split and quotes containing them could fail to match.
- **`quote_matched` is rebuilt from matched token surface forms**, so punctuation *inside* a phrase is not reproduced (e.g. a comma disappears). Timestamps and phrase ids are unaffected. This is for display only; if exact punctuation is needed later, slice the original phrase text instead.
- **Interpolated phrases** assign every normalised sub-token of a raw word the same raw spelling; `quote_matched` collapses consecutive duplicates so the surface text is not repeated. Only affects hyphenated words when Speech omits word offsets.
- **Local Python is 3.13**, while `02_ARCHITECTURE.md` suggests 3.11. No 3.11-only features are used; the venv pins nothing yet, so a teammate on 3.11 should also work.
- **`.env` is not created by the build.** `load_settings()` falls back to documented defaults and `require_azure_env()` is only called by the Speech/LLM clients, so Phase 1 runs with no credentials.

## Open questions

- Team number, team name and lecture locale are still placeholders (`T##`, `en-US`). Nothing depends on them yet; resolve before recording clips.
