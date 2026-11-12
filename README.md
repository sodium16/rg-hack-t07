# P11 · Lecture to Revision Notes

> **"Every sentence this app shows you can be traced to a second in your lecture, or it doesn't show it."**

An AI-powered revision study tool built for the **AI-103 Hackathon (Problem P11)**. A student uploads a 5–10 minute lecture recording and gets:
1. A **timestamped transcript** with word-level precision.
2. A **one-page set of revision notes** (≤ 400 words) where every bullet carries a verified timestamp.
3. **Exactly 5 key terms** with definitions quoted directly from the lecture and asserted against the transcript.
4. A **grounded Q&A box** that answers with a clickable timestamp chip or deterministically returns `"Not covered in this lecture"`.
5. An interactive **click-to-play audio player** that jumps to 1 second before the relevant spoken sentence.
6. A **Verification Report** detailing kept vs. dropped claims, token usage, and safety findings.

---

## Architecture & Trust Layer

Unlike standard RAG or basic prompt wrappers that trust model-emitted timestamps or hallucinated facts, this project implements a strict **Trust Layer**:

```
Audio Upload (5–10 min)
         │
         ▼
[Azure AI Speech] ──► Fast Transcription (api-version=2025-10-15)
         │            Cached by audio SHA-256 (phrases + word offsets)
         ▼
[Transcript Index] ──► Token normalisation, word-level offsets, interpolation
         │
         ▼
[Azure Foundry] ──► Chat Model (JSON mode): drafts notes, key terms, answers + verbatim quotes
         │
         ▼
[Verification Engine] ──► Locates model quotes in the transcript index (Exact ➔ Fuzzy sliding window)
         │                • Dropped unverified bullets/terms never reach the student
         │                • Key terms asserted to literally appear in the transcript
         │                • Coverage Gate: Quote verified AND relevance check passed
         ▼
[Streamlit Frontend] ──► Notes, 5 Key Terms, Transcript (w/ PII masking), Q&A, Click-to-Play Player
```

- **Timestamps are computed in code:** The model only provides verbatim quotes; `verify.py` searches the Speech token index to find exact millisecond offsets (`start_ms - 1000`).
- **Unverified content is discarded:** If a bullet or term cannot be grounded in the transcript, it is pruned and recorded in the Verification Report.
- **`Not covered in this lecture` is a code decision:** A question without a verified supporting quote is refused by code, preventing hallucinated answers on out-of-scope or near-miss topics.

---

## Measured Acceptance Results (A1, A2, A3)

Evaluated against the team's real lecture recording (`clip1.mp3`, 5:13, 881 words) using [`eval/run_eval.py`](file:///f:/Documents/Projects/rg-hack-t07/eval/run_eval.py):

| Test | Metric | Target | Result | Verdict |
|---|---|---|---|---|
| **A1** | Word Error Rate (WER) vs. spoken script (`0–100s`) | ≤ 10% | **1.50%** (263/267 words matched) | **PASS** |
| **A1** | Timestamps monotonic and within audio | 100% | **True** | **PASS** |
| **A2** | Answer timestamp lands within ±5s of gold window | ≥ 90% | **10/10 (100%)** | **PASS** |
| **A2** | Answer correctness | 100% | **10/10 (100%)** | **PASS** |
| **A3** | Unrelated questions refused (`"Not covered in this lecture"`) | 100% | **5/5 (100%)** | **PASS** |
| **A3** | Near-miss questions refused (`"Not covered in this lecture"`) | ≥ 90% | **5/5 (100%)** | **PASS** |
| **A3** | False-premise questions refused | 100% | **3/3 (100%)** | **PASS** |
| **A3** | Exactly 5 key terms present in transcript | 100% | **5/5 present (100%)** | **PASS** |

Detailed machine-readable metrics are located in `eval/results/` (`a1_wer.json`, `a2_timestamps.json`, `a3_notcovered.json`, `a3_keyterms.json`, and `summary.md`).

---

## Engineering, Safety & Cost Controls

1. **Content Filtering:** Azure Foundry content filter is active. Handled in `app/llm.py` by trapping `finish_reason == "content_filter"` and displaying a user-friendly notification.
2. **Prompt Injection Resilience:** Tested on `clip2.mp3` with a planted injection (*"ignore all previous instructions..."*). Transcripts are isolated as data in prompts, the injection phrase is detected and flagged in the Verification tab, and notes/answers remain truthful.
3. **Personal Data (PII) Masking:** Spoken phone numbers and email addresses are scanned in `app/safety.py`. The UI includes a **"Mask personal details"** toggle that redacts sensitive text from display while preserving underlying verification truth.
4. **Zero Secret Leakage:** All secrets are loaded from environment variables (`.env`). `.env` is gitignored; `.env.example` provides clean placeholders.
5. **Cost Optimization:**
   - Azure Speech outputs are cached locally under `data/cache/<sha256>.speech.json`. Repeat runs and demo checks are instant and free.
   - Strict `max_tokens` limits and structured JSON schemas minimize token consumption.

---

## Repository Structure

```
rg-hack-t07/
├── app/                        # Core backend modules
│   ├── audio.py                # Audio validation, duration probe, SHA-256 hashing
│   ├── config.py               # Environment configuration and tunable thresholds
│   ├── language.py             # Normalisation, token stemming, and content-word overlap
│   ├── llm.py                  # Azure Foundry client (JSON mode, error handling, retries)
│   ├── models.py               # Frozen data contracts (Transcript, Evidence, QAResult, etc.)
│   ├── net.py                  # Resilient HTTP transport with exponential backoff & redaction
│   ├── notes.py                # Notes and 5 key terms generation with verification loop
│   ├── pipeline.py             # CLI pipeline runner
│   ├── prompts.py              # System prompts, JSON schemas, and few-shot formatting
│   ├── qa.py                   # Grounded Q&A with relevance gate and refusal decision
│   ├── safety.py               # Prompt injection and PII scanning & masking
│   ├── speech.py               # Azure AI Speech fast transcription REST client
│   ├── transcript_index.py     # Token index, word offset interpolation, term matching
│   └── verify.py               # Quote location (exact -> sliding window fuzzy match)
├── data/
│   ├── cache/                  # SHA-256 speech cache (makes repeat runs instant)
│   └── samples/                # Sample lecture audio clips (clip1.mp3, clip2.mp3)
├── docs/
│   └── DECISIONS.md            # Architecture decision records and real-world findings
├── eval/
│   ├── clip1_a1_2min.txt       # Spoken reference script for A1 WER slice
│   ├── clip1_script.txt        # Full reference script for Clip 1
│   ├── clip2_script.txt        # Full reference script for Clip 2
│   ├── qa_gold.json            # Gold Q&A evaluation benchmark
│   ├── results/                # Machine-readable evaluation outputs and summary
│   └── run_eval.py             # Full evaluation harness (A1, A2, A3)
├── tests/                      # Pytest test suite (101 unit tests + integration smoke tests)
├── .env.example                # Example environment variables
├── .gitignore                  # Git ignore rules (secrets, venv, temporary cache)
├── main.py                     # Streamlit web application
├── pytest.ini                  # Pytest configuration
└── requirements.txt            # Python dependencies
```

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.11+ (tested on Python 3.13)
- An active Azure AI Speech resource and Azure AI Foundry project deployment

### 2. Setup Virtual Environment
```bash
# Clone the repository
git clone <repo-url>
cd rg-hack-t07

# Create and activate virtual environment
python -m venv .venv
# On Windows (PowerShell / Command Prompt):
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and fill in your Azure credentials:
```bash
cp .env.example .env
```
Fill in the following variables:
```env
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=your_speech_region
AZURE_SPEECH_LOCALE=en-US
AZURE_FOUNDRY_ENDPOINT=https://your-resource.services.ai.azure.com/
AZURE_FOUNDRY_KEY=your_foundry_key
AZURE_FOUNDRY_DEPLOYMENT=gpt-4.1-mini
AZURE_FOUNDRY_API_VERSION=2025-04-14
```

### 4. Running the Web Application
Launch the Streamlit UI:
```bash
streamlit run main.py
```
Open your browser at `http://localhost:8501`.
- Choose `data/samples/clip1.mp3` or `data/samples/clip2.mp3` from the dropdown, or upload your own audio file.
- Navigate the tabs: **Notes**, **Key terms**, **Transcript**, **Ask**, and **Verification**.
- Click any **`▶ m:ss`** chip to seek the player and hear the exact second of audio.

### 5. Running the Tests & Evaluation
```bash
# Run the offline test suite (101 unit tests, ~1s, requires no credentials)
pytest -q

# Run live end-to-end integration tests (requires .env)
pytest -m integration -q

# Run full evaluation suite (A1, A2, A3 benchmarks)
python eval/run_eval.py --clip data/samples/clip1.mp3 --all --a1-script eval/clip1_a1_2min.txt --a1-range 0 100
```
