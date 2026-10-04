# Changelog

All notable changes to VerifyIQ are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Test suites and `verifyiq.v1`/`verifyiq.v2` imports failing because the `code/` package is
  shadowed by the standard-library `code` module
- `verifyiq evaluate` CLI command (always failed)
- Missing `numpy` / `opencv-python-headless` dependencies required by the risk analyzer
- Hard-coded Windows Tesseract path that disabled OCR on Linux, macOS and Docker
- Path-sanitizer prefix bypass for sibling directories
- V2 fraud layer reading a non-existent parser key (severity escalation never detected)
- "Contradicted because" label on `not_enough_information` justifications
- API: pipeline loaded from `code.v2` instead of `verifyiq.v2`, raw exception text in 500
  responses, credentialed wildcard CORS
- Dockerfile, docker-compose and deploy scripts that could not build or start the API
- Examples importing `code.v2`

### Removed

- Committed build artifacts (`dist/`, `verifyiq.egg-info/`)

## [0.1.0-dev] — 2026-06-20

### Added

- V1 deterministic claim verification pipeline (6-path rule engine)
- V2 10-layer production pipeline (observability, security, fraud, conversation, confidence, critic, explainability)
- V1→V2 adapter layer for backward compatibility
- Multi-model VLM provider system (Gemini, OpenRouter stub, local VLM stub)
- Fraud detection (image hash dedup, metadata EXIF analysis, behavioral pattern detection)
- Conversation analysis (negation, uncertainty, retraction, sarcasm, contradiction)
- Confidence calibration with 4-tier routing (auto, fast_review, manual_review, evidence_request)
- Cross-layer critic for consistency validation
- DecisionTrace explainability with 6 trace types
- Input sanitization (prompt injection, path traversal, CSV injection)
- Metrics collection and trace logging
- 107 unit tests (58 V1 + 49 V2)
- 20/20 static evaluation on sample claims
- 10-phase validation framework
- Adversarial testing suite
- Competition submission package
- 26+ design and evaluation documents

### Changed

- Repository reorganized for open-source release
- Package structure established (verifyiq/)
- CI/CD pipeline configured (GitHub Actions)
- Docker support added

### Fixed

- Observation data passthrough bug (V2 pipeline not passing vision data to rule engine)
- ClaimParser key mismatch (wrong field names in V1RuleAdapter)
- Missing valid_image field in V2Decision
- Risk flag propagation from rule engine to final decision
