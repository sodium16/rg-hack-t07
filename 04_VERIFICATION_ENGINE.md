# 04 · Verification Engine (the heart of the project)

Goal: **no AI-generated claim reaches the student unless a supporting quote is found in the transcript, and every timestamp is computed from the Speech output, not from the model.**

This module is small, pure, and heavily unit-tested. Build it first.

## 1. Transcript Index

Build once per transcript.

- `phrases[]`: from Speech, each with `start_ms`, `end_ms`, `text`, `confidence`.
- `tokens[]`: flatten the transcript into a list of normalised word tokens, each with `(token, start_ms, end_ms, phrase_id)`.
  - If Speech returns `words[]`, use their offsets directly.
  - Otherwise, interpolate: distribute the phrase duration across its tokens proportionally to character length.
- `norm_text`: tokens joined by single spaces.

### Normalisation function `norm(s)`
Apply identically to transcript and quotes:
- Unicode NFKC, lowercase.
- Replace curly quotes/dashes with ASCII; remove punctuation except intra-word apostrophes/hyphens (hyphen → space).
- Collapse whitespace.
- Number handling: keep digits as-is; optionally map "two"→"2" **only if** both sides need it (decide after testing; Speech display-format usually outputs digits).
- Optionally strip filler tokens ("um", "uh") on both sides.

## 2. Locating a quote (`locate(quote) -> Evidence`)

Input: a model-provided quote (string). Output: `Evidence` (see `02_ARCHITECTURE.md`).

Algorithm (try in order, stop at first success):

1. **Exact match** on `norm_text` (`norm(quote) in norm_text`). Score 1.0. Find the token span via a token-index map; `start_ms` = first token's start, `end_ms` = last token's end.
2. **Fuzzy sliding window.** Let `q` = tokens of `norm(quote)` (length `n`). Slide windows of length `n−2 … n+2` tokens across `tokens[]`; compute similarity (e.g. `rapidfuzz.fuzz.ratio` on the joined window / 100, or token-level Levenshtein). Keep the best window. Accept if `score >= MATCH_THRESHOLD` (default 0.88).
3. **Cross-phrase quotes:** because windows run over the flattened token list, quotes spanning two phrases work automatically. Return all `phrase_ids` touched.
4. **Fail** → `verified=false`, `match_score=best`, `start_ms=None`.

Rules:
- Minimum quote length: **5 tokens** (reject trivially short quotes, which match anywhere).
- Maximum quote length: **40 tokens** (we want the *moment*, not a whole paragraph). If a quote is longer, split into sentences and locate the best-scoring sentence.
- If several windows tie, prefer the **earliest** unless a `hint_ms` is passed (e.g. when the model gave an approximate timestamp or for re-asking).
- `start_ms` returned is the start of the first matched token. UI seeks to `start_ms − 1000`.

## 3. Verifying notes

For each bullet with quotes:
1. `locate()` each quote.
2. Bullet is `verified` if ≥ 1 quote verified.
3. Drop unverified bullets. If after dropping a section has < 2 bullets, drop the section or call regeneration for that section.
4. Optional semantic support check (P1): ask a small, separate LLM call "Does QUOTE support CLAIM? yes/no" (temperature 0). Drop on "no". This catches cases where a real quote is attached to an unsupported claim.
5. Update `VerificationReport.notes`.

## 4. Verifying key terms (A3)

For each candidate `{term, definition, quote}`:
1. `term_found`: `norm(term)` appears in `norm_text` (also allow simple plural/hyphen variants: "neural networks" vs "neural network"; "back-propagation" vs "backpropagation" via an alternate no-space check). **Must be true.**
2. `locate(quote)` verified.
3. The **quote should contain the term** (or a clear referent within the same/adjacent phrase). If the quote doesn't contain the term, widen: check that the term appears within ±1 phrase of the quote.
4. Definition faithfulness: ≥ 50% of the content words (non-stopwords) in `definition` appear in `quote` or its neighbouring phrases, **or** pass the semantic support check in §3.4. This enforces "definitions taken from the lecture itself".
5. All pass → verified; else discard.

Regeneration loop:
- Request **8 candidates** up front; keep the first 5 verified, ranked by the model's importance score then earliest timestamp.
- If < 5 verified: second call with the failure reasons ("term X not found in transcript") and exclusion list; up to 2 retries.
- If still < 5: show the verified ones and an honest note. (Should never happen on our team clips; if it does in testing, improve the prompt.)

**Automated assertion (must pass in CI and in the eval):**
```python
assert all(norm_term_in_text(kt.term, transcript.norm_text) for kt in key_terms)
assert len(key_terms) == 5
```

## 5. Verifying Q&A and deciding "not covered"

```
model_out = ask_model(question, transcript)         # {covered, answer, evidence_quotes[]}
evidence  = [locate(q) for q in model_out.evidence_quotes]
verified  = [e for e in evidence if e.verified]

covered_final = (
    len(verified) >= 1
    and relevance_gate(question, verified, answer)  # see below
    and model_out.covered is not False               # model may veto
)
```

### Relevance gate (defends against near-miss questions)
A real quote can be found, but not actually answer the question (e.g. model quotes something nearby and bluffs). Layered checks:

1. **Key-concept overlap:** extract content words/noun phrases from the question (drop stopwords and generic words like "explain", "lecture", "say", "mean"). At least **one salient concept** (the question's main noun phrase) must appear in the evidence quote(s) or their neighbouring ±1 phrase window. If the question's central term never appears in the transcript at all → not covered immediately (cheap, strong signal for unrelated and near-miss questions).
2. **Answer-grounding check:** ≥ 60% of content words in `answer` should be present in the evidence quotes/neighbour window (guards against the model adding outside knowledge). Otherwise show only the quote-based answer or refuse.
3. **Judge call (P1, recommended):** a second, independent LLM call at temperature 0: *"Given only this excerpt, can the question be answered? Reply JSON {answerable: bool, reason}."* Run it on the **excerpt window (±20 s around the quote), not the whole transcript.** If `answerable=false` → not covered.
4. **Retrieval sanity check (optional):** embed question and transcript windows (30 s windows, 10 s stride) with a Foundry embedding deployment; require top-1 cosine similarity above a calibrated threshold. Calibrate the threshold on the eval set (`07`).

Decision table:

| Quote verified | Gate passes | Model said covered | Result |
|:-:|:-:|:-:|---|
| ✓ | ✓ | ✓ | **Covered**: show answer + timestamp |
| ✓ | ✗ | any | Not covered (reason: "quote does not answer the question") |
| ✗ | any | ✓ | Not covered (reason: "claimed answer not found in transcript"); log as *model hallucination caught* |
| any | any | ✗ | Not covered |

Log `model_claimed_covered` vs final `covered` so the Metrics tab can show "N hallucinated answers caught by verification". This is a great proof point.

### Timestamp selection
- `primary_timestamp_ms` = `start_ms` of the **best-scoring verified quote** (tie → earliest).
- Accuracy target: within **±5 s** of the gold moment; aim for ±2 s because we use word-level offsets.

## 6. Low-confidence handling
- Compute `min_confidence` across phrases touched by each evidence. If < threshold, attach `caution: "audio unclear"` to the item. Do not suppress.

## 7. Injection screening (in `safety.py`, feeds the report)
- Regex/keyword list over transcript: "ignore (all|previous|the above) instructions", "system prompt", "you are now", "disregard", "reveal your", etc.
- Flag only (do not delete); the model prompt already instructs to treat transcript as data. Show a note in the report.

## 8. Unit tests to write first (`tests/test_verify.py`)

1. Exact quote → score 1.0, correct start_ms.
2. Quote with punctuation/case differences → still verified.
3. Quote with one word changed → verified (≥ threshold). Quote with three words changed → fails.
4. Quote spanning two phrases → both phrase_ids returned.
5. Hallucinated quote (not present) → `verified=false`.
6. Quote < 5 tokens → rejected.
7. Duplicate phrase appearing twice (lecturers repeat) → earliest by default; `hint_ms` selects the later one.
8. Key term plural/hyphen variants accepted; absent term rejected.
9. Not-covered decision table cases.
10. Timestamp interpolation when word offsets missing.

Use a hand-written fake `Transcript` fixture so tests run offline without Azure.

## 9. Design notes / pitfalls

- Lecturers repeat themselves. The model may quote the second occurrence. Both are "right"; for A2 judge against the **gold window**, so store *all* gold timestamps for repeated ideas as acceptable (`gold_windows[]`).
- Speech may mis-transcribe domain terms ("gradient" → "gradiant"). Fuzzy matching handles light errors. For key terms, if a term is mis-transcribed, choose another term or allow a phonetic/fuzzy match ≥ 0.9 and show the transcript spelling. Prefer to **fix by providing phrase hints** to Speech (`phraseList` feature, if supported in the chosen API) for domain terms.
- Never "fix up" a timestamp with model output. If locate fails, there is no timestamp.
- Keep thresholds in `config.py`; record the values in the Evidence Sheet.
