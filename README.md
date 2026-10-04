# VerifyIQ — Multimodal Damage-Claim Verification

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)

VerifyIQ reviews damage claims for **cars, laptops and packages**. For each claim it reads the
customer/support conversation, looks at the submitted photos through an external vision-language
model (Google Gemini), and decides whether the photos **support**, **contradict**, or give
**not enough information** for the claim. It also reports the visible issue type, the object part,
risk flags, severity and a short justification.

The design keeps the vision model in the role of an *observer*: it extracts visual facts as JSON,
and deterministic Python code (parser, evidence checker, rule engine, risk and severity engines)
makes the decision. The project started as a solution to the challenge described in
[problem_statement.md](problem_statement.md).

> VerifyIQ does not contain its own vision model. Without a `GEMINI_API_KEY` the pipelines still
> run, but every image-dependent decision degrades to `not_enough_information` /
> `manual_review_required`.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Installation](#installation)
- [Usage](#usage)
- [REST API](#rest-api)
- [Configuration](#configuration)
- [Testing](#testing)
- [Docker](#docker)
- [Known limitations](#known-limitations)
- [Audit fixes (2026-10)](#audit-fixes-2026-10)
- [License](#license)

---

## Features

What exists in the code today:

| Area | Implementation |
|---|---|
| Claim parsing | Keyword-based extraction of damage type and object part from the customer's turns of the conversation (`code/claim_parser.py`) |
| Vision observation (V1) | Gemini call with a structured JSON prompt, retries on rate limits, on-disk response cache in `.gemini_cache/` (`code/vision_analyzer.py`, `code/prompts.py`) |
| Evidence check | Per-object minimum evidence requirements from `dataset/evidence_requirements.csv` (`code/evidence_checker.py`) |
| Decision | Deterministic rule engine → `supported` / `contradicted` / `not_enough_information` (`code/rule_engine.py`) |
| Risk flags | Vision-derived flags, user-history risk, plus local CV checks: blur (OpenCV Laplacian), crop, wrong object, and OCR text detection via Tesseract (`code/risk_analyzer.py`, `code/cv/`) |
| Output | Validated 14-column CSV (`code/output_validator.py`, `code/submission_critic.py`) |
| V2 pipeline | Layered orchestrator around the V1 engines: input sanitization, vision-availability manager with circuit breaker, consensus, image/EXIF/behavioral fraud checks, conversation analysis (negation, retraction, uncertainty), confidence calibration and routing, a critic, and a decision trace (`verifyiq/v2/`) |
| API | FastAPI service exposing the V2 pipeline (`api/main.py`) |
| Dashboard | Streamlit UI (`dashboard/app.py`) — **renders randomly generated mock data only**; it is not connected to the pipeline |

---

## Architecture

### V1 batch pipeline (`python -m code.main`)

```
dataset/claims.csv
   │
   ▼
ClaimProcessor (per claim)
   ├─ image_preprocessor / image_validator   – normalise and validate files
   ├─ ClaimParser                            – claimed damage type + part from the conversation
   ├─ vision_analyzer (Gemini)               – per-image observations as JSON
   ├─ EvidenceChecker                        – minimum evidence requirements
   ├─ RuleEngine                             – claim_status + confidence
   ├─ RiskAnalyzer (+ code/cv OpenCV/OCR)    – risk flags
   └─ DecisionAgent → SeverityEngine → OutputValidator
   │
   ▼
submission_critic.validate_output_rows → output.csv
```

Every stage is wrapped in `try/except`; a failing stage produces a conservative fallback
(`not_enough_information`, `manual_review_required`) instead of stopping the batch.

### V2 pipeline (`verifyiq.v2.V2Pipeline`, used by the API)

```
sanitize inputs → vision availability check → observation (providers) → consensus
  → fraud (image hash, EXIF, behavioral) → evidence (V1 EvidenceChecker)
  → conversation analysis → confidence calibration → V1 RuleEngine adapter
  → critic → decision assembly + DecisionTrace
```

`VERIFYIQ_MODE` controls what happens when no vision provider is reachable:
`production` (default) refuses image claims and the API refuses to start; `demo` and `research`
continue on text only and add a `vision_unavailable` flag.

---

## Project structure

```
code/                 V1 pipeline (flat modules, imported as `code.*` or by bare name)
  cv/                 OpenCV / Tesseract checks
  evaluation/         static_evaluate.py, evaluate.py, error_analysis.py
  tests/              V1 unit tests
  v2/                 Older copy of the V2 package (imports `code.v2.*`) + its tests
verifyiq/             Installable package
  __main__.py         `verifyiq` CLI
  v1/                 Re-exports of the V1 classes from code/
  v2/                 V2 pipeline (the copy used by the API and examples)
api/main.py           FastAPI service
dashboard/            Streamlit mock-data dashboard
dataset/              claims.csv (44 claims), sample_claims.csv (20 labelled), user_history.csv,
                      evidence_requirements.csv, images/
examples/             Runnable examples (01–04) and provider examples
tests/                Package-level tests (v1/, v2/)
docker/               Dockerfile, Dockerfile.gpu (stub), docker-compose.yml
scripts/              deploy.sh / deploy.ps1 (build image and start the API container)
docs/, reports/, submission/, research/, archive/
                      Design notes, evaluation reports and competition material written
                      during development. They were not re-verified in the 2026-10 audit.
```

---

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/ShibilAhamed701212/verifyiq-ai-claim-verification.git
cd verifyiq-ai-claim-verification
python -m venv .venv && source .venv/bin/activate

pip install -e ".[v1]"          # core + Gemini client (needed for the V1 pipeline)
pip install -e ".[v1,api]"      # + FastAPI / uvicorn
pip install -e ".[dev]"         # + pytest, ruff, mypy
# or: pip install -r code/requirements.txt
```

Optional OCR check: install the Tesseract binary (`apt install tesseract-ocr`,
`brew install tesseract`, or the Windows installer) and `pip install pytesseract`. Without it the
`text_instruction_present` flag cannot be raised; everything else still works.

The package is not published on PyPI; install it from a clone.

---

## Usage

### Run the V1 pipeline on `dataset/claims.csv`

```bash
export GEMINI_API_KEY="your-key"
python -m code.main            # run from the repository root
```

Writes `output.csv` in the repository root. Without a key the run still completes, with
vision-dependent fields set to `unknown` / `not_enough_information`.

### Static evaluation (`verifyiq evaluate`)

```bash
verifyiq evaluate
# equivalent: python code/evaluation/static_evaluate.py
```

This runs the deterministic part of the V1 pipeline on the 20 labelled rows of
`dataset/sample_claims.csv`. **It feeds the expected labels in as the "vision" input**, so it tests
the parser, evidence checker, rule, risk and severity logic under ideal observations. It does
**not** measure end-to-end accuracy with a real vision model. Output captured during the audit
(Docker image with Tesseract, dataset mounted):

```
Running evaluation on /app/dataset/sample_claims.csv...
======================================================================
STATIC EVALUATION (ideal vision + CV modules)
======================================================================
Correct: 20/20 (100%)
```

Without Tesseract installed, `user_034` misses `text_instruction_present` and the result is 19/20.

`python code/evaluation/main.py` runs the full pipeline (including Gemini) against
`sample_claims.csv` and writes `evaluation_report.md` and `error_report.md` into
`code/evaluation/`. This is the end-to-end measurement; it needs `GEMINI_API_KEY`, and without a
key the scores are close to zero because no visual evidence is available.

### V2 pipeline from Python

```python
from verifyiq.v2 import V2Pipeline

pipeline = V2Pipeline()  # defaults to the Gemini provider
decision = pipeline.process(
    claim_text="Customer: There is a deep dent on the rear bumper.",
    image_paths=["dataset/images/sample/case_001/img_1.jpg"],
    claim_object="car",
    user_id="user_001",
)
print(decision.claim_status, decision.risk_flags, decision.justification)
```

`image_paths` are local paths resolved against the current working directory; paths outside it
are dropped by the sanitizer. See [examples/](examples/) for runnable scripts
(`python examples/03_v2_pipeline.py` works without an API key).

### Dashboard

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

Pages: Overview, Claim History, Fraud Analysis, Risk Trends, System Health. All values are
generated by `_mock_claims()` / `_mock_metrics()` on each load.

---

## REST API

```bash
VERIFYIQ_MODE=demo uvicorn api.main:app --port 8000   # from the repository root
```

Interactive docs at `http://localhost:8000/docs` (`/` redirects there).

| Method | Path | Description |
|---|---|---|
| `POST` | `/claim` | Verify one claim. Body: `claim_text`, `claim_object`, `image_paths` (server-local paths), optional `user_id` |
| `POST` | `/batch` | Verify a list of claims sequentially (`{"claims": [...]}`) |
| `GET` | `/health` | Status, mode, vision state and per-provider health. Returns 503 in production mode when no provider is available |
| `GET` | `/metrics` | Request/failure counters, latency stats, per-stage metrics, vision report |

The API has **no authentication or rate limiting**, and it reads images from the server's
filesystem. Do not expose it publicly without putting it behind an authenticating proxy.

Example response captured during the audit (demo mode, no API key, so vision was unavailable):

```json
{
  "claim_status": "not_enough_information",
  "confidence": 0.2,
  "severity": "unknown",
  "risk_flags": ["evidence_insufficient", "exif_read_error", "manual_review_required", "vision_unavailable"],
  "justification": "Not supported because: Claim status: not_enough_information; Evidence insufficient: Image analysis temporarily unavailable — vision provider unreachable. Claim processed based on text only. | Confidence: 0.20 (evidence_request) | Fraud flags: exif_read_error",
  "trace_id": "81006e83916647f9",
  "latency_ms": 21.26
}
```

---

## Configuration

| Variable | Used by | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | V1 vision analyzer, V2 `GeminiProvider` | Google Gemini API key |
| `VERIFYIQ_MODE` | V2 pipeline, API | `production` (default), `demo`, `research` |
| `VERIFYIQ_VERSION` | API | Version string reported by `/health` |
| `OPENROUTER_API_KEY` | V2 `OpenRouterProvider` | Only marks the stub provider as available (see limitations) |
| `TESSERACT_CMD` | `code/cv/text_detector.py` | Path to the Tesseract binary if it is not on `PATH` |

V1 settings (model name, paths, thresholds) live in the `Config` dataclass in `code/config.py`.
The V1 default model is `gemini-3.1-flash-lite-preview`; the V2 Gemini provider defaults to
`gemini-2.0-flash`.

---

## Testing

```bash
pip install -e ".[dev]" -r code/requirements.txt
pytest                      # all suites from pyproject.toml: 281 tests
pytest code/tests           # V1 unit tests (58)
pytest code/v2/tests        # tests for the code/v2 copy (77)
pytest tests                # package tests: tests/v1 (60) + tests/v2 (86, incl. audit regressions)
```

Verified passing on Python 3.10, 3.11 and 3.12 during the audit. The tests need no API key.

CI (`.github/workflows/tests.yml`) runs all three suites on 3.10–3.12. The `lint` workflow runs
`ruff check`, which currently reports about 780 style findings (mostly line length, whitespace
and annotation style), so it fails; those were left as-is to avoid a cosmetic rewrite.

---

## Docker

All commands from the repository root.

```bash
docker build -f docker/Dockerfile -t verifyiq:latest .

# Static evaluation (mount the dataset so the images are available)
docker run --rm -v "$PWD/dataset:/app/dataset:ro" verifyiq:latest

# API
docker run --rm -p 8000:8000 -e VERIFYIQ_MODE=demo -e GEMINI_API_KEY \
  --entrypoint uvicorn verifyiq:latest api.main:app --host 0.0.0.0 --port 8000

# or with compose
docker compose -f docker/docker-compose.yml --profile api up --build
docker compose -f docker/docker-compose.yml --profile evaluation up --build

# or the helper script (builds, starts the API container, waits for /health)
./scripts/deploy.sh
```

The image includes Tesseract. In `production` mode the API container exits at startup if no
vision provider is configured; set `GEMINI_API_KEY` or `VERIFYIQ_MODE=demo`.
`docker/Dockerfile.gpu` is an unfinished placeholder (no CUDA runtime).

---

## Known limitations

- **Only Gemini is a working vision provider.** `OpenRouterProvider` and `LocalVLMProvider` are
  stubs whose `analyze()` returns no observations, so "multi-model consensus" in V2 effectively
  runs on one model at most.
- **The V2 Gemini provider sends no task prompt or JSON schema**, only the (sanitized) claim text
  and images, then looks for `per_image_assessments` in the reply. The V1 analyzer uses the full
  prompt in `code/prompts.py`. V2 vision results with a real key were not verified in this audit.
- **Behavioral fraud history is never loaded** by `V2Pipeline`; `BehavioralFraudDetector` only has
  history if you call `pipeline.behavioral_fraud.load_history(csv_path)` yourself.
- **The V2 package exists twice** (`verifyiq/v2/` and `code/v2/`), differing only in import paths.
  Fixes must be applied to both until one copy is removed.
- **The `code/` directory name collides with Python's standard-library `code` module.**
  `verifyiq` sidesteps it by importing the V1 modules by bare name (`from config import Config`)
  and never importing `code` as a package. `python -m code.main` works only from the repository
  root, and the `code/tests` / `code/v2/tests` suites rely on a test-only workaround in the root
  `conftest.py`. Renaming the directory would remove both, but touches every V1 import.
- The package only works from a source checkout or editable install, because `verifyiq` imports
  the V1 modules from the sibling `code/` directory.
- The API has no authentication, rate limiting or batch-size limit.
- The dashboard shows mock data.
- Accuracy and performance figures in `docs/`, `reports/` and `submission/` come from development
  runs and were not reproduced in this audit.

---

## Audit fixes (2026-10)

| Priority | Problem | Fix |
|---|---|---|
| P1 | Every test suite failed at import (CI red since the first run): pytest imports the stdlib `code` module before the project's `code` package, and `tests/v1` put the wrong directory on `sys.path` | Test-only workaround in a root `conftest.py`; fixed `tests/v1` paths |
| P1 | `import verifyiq.v1` / `verifyiq.v2` failed outside the repository root (same collision) | `verifyiq` imports V1 modules by bare name instead of `code.*`; regression tests check it imports with the stdlib `code` loaded and leaves that module intact |
| P1 | `verifyiq evaluate` always failed: it imported a non-existent `main()` from `static_evaluate.py` via the shadowed `code` name | CLI now runs the script with `runpy`; removed the unused `--output` flag and the unimplemented `analyze` command |
| P1 | `numpy` / `opencv-python-headless` were missing from all dependency lists, but the risk analyzer imports them whenever a claim has images (static evaluation crashed; in the batch pipeline the risk stage failed and every claim with images lost all of its risk flags except `manual_review_required`) | Added to `pyproject.toml` and `code/requirements.txt`; `google-genai` added to the `v1` extra |
| P2 | Tesseract path hard-coded to `C:\Program Files\...`, so OCR never worked on Linux/macOS/Docker | Uses `$TESSERACT_CMD`, the Windows default if it exists, else `PATH` |
| P2 | Path sanitizer used a string-prefix check, so `/base-other/file` passed for base `/base` | Uses `Path.is_relative_to` (both V2 copies) |
| P2 | V2 fraud layer read `parsed["damage_type"]`, a key the parser never returns, so severity-escalation detection could never fire | Reads `claimed_damage_type` (both copies) |
| P3 | `not_enough_information` justifications began with "Contradicted because:" | Label is "Contradicted because" only for `contradicted`, otherwise "Not supported because" (both copies) |
| P2 | API loaded the pipeline from `code.v2` while metrics came from `verifyiq.v2` (two separate metric collectors); 500 responses returned raw exception text; CORS allowed credentials with `*` origins | API uses `verifyiq.v2`; 500s return an error code and trace id; `allow_credentials=False` |
| P2 | Docker build could not work: compose pointed at a missing context/Dockerfile, `.dockerignore` excluded the `README.md` the build copies, the image lacked `api/` and the vision/CV dependencies, and compose started a non-existent `verifyiq.api.app` | Rewrote `docker/Dockerfile`, fixed compose, `deploy.sh` and `deploy.ps1`; image built and both the evaluation and the API ran in a container |
| P3 | Examples imported `code.v2` and failed outside pytest | Examples import `verifyiq.v2`; stub providers are labelled as stubs |
| P3 | Build artifacts (`dist/`, `verifyiq.egg-info/`) committed | Removed and ignored |

---

## License

MIT. See [LICENSE](LICENSE).
