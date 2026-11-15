# Implementation Plan: Text Classification and Prediction Persistence

**Branch**: `004-classification-persistence` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-classification-persistence/spec.md`

## Summary

Add a trusted-environment classification page that consumes the existing model and label services, runs local PyTorch zero-shot inference against an immutable request snapshot, and displays a result only after its complete JSON record is confirmed in MinIO. Coordinate concurrent model and label mutations, reject over-limit text without truncation, isolate per-session request state, and distinguish confirmed storage failure from an indeterminate write. An exact resubmission (same text, model ID/revision, and label-set ID/revision) reuses the active request status; a different submission waits until that request finishes with its draft retained. Controls are keyboard-operable, have accessible names, and expose status/error updates accessibly; no formal WCAG conformance is claimed. [Research](research.md), [data model](data-model.md), and [contract](contracts/classification.md) detail the decisions and limitations.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: Existing Streamlit, Hugging Face Hub, PyYAML, and filelock. Add compatible `torch`, `transformers`, and the `minio` Python client as direct runtime dependencies; preserve the repository's Hugging Face Hub 2.x compatibility when selecting Transformers and regenerate `uv.lock` with `uv` during implementation. Do not change the Python floor or introduce a second ML backend. Preserve strict mypy and Ruff checks.

**Storage**: Existing non-secret YAML model and label configuration; prediction JSON only in the configured MinIO bucket, default `zeroshot_learning_output`. This default can be rejected by standards-compliant clients/services: surface an actionable configuration error and require an operator-specified valid bucket; never substitute one.

**Testing**: pytest with deterministic local fakes and no model downloads for ordinary tests; Streamlit AppTest; bounded same-host concurrency/fault tests; separately selected MinIO-compatible integration test with an isolated valid test bucket.

**Target Platform**: Existing local Windows and POSIX application on one host with a local filesystem and cooperating application processes. External file edits require quiescing application writers. Multi-host and network-filesystem concurrency guarantees are not claimed.

**Project Type**: Existing Streamlit multipage application with modular services.

**Performance Goals**: No latency or throughput target specified. Measure the specification's 90% first-attempt completion outcome; never claim it before an actual usability check.

**Constraints**: Local model loading only; full pair-token limit checks; stable request identity; confirmed MinIO write before success; conservative uncertain-write recovery; exact per-session duplicate matching and one active request at a time; accessible keyboard-operable controls and accessible names/status updates without a formal WCAG claim; no raw input, prediction, credential, token, or sensitive local path in logs/errors. No new auth or prediction history.

**Scale/Scope**: Single-text requests in local or trusted environments; small numbers of cooperating sessions and model/label sets. No invented user, label, or throughput limits.

## Constitution Check

| Principle | Before research | Post-design |
|---|---|---|
| 1-3: stack, quality, reproducibility | Pass: use required stack and retain Python floor | Pass: explicit dependencies and local PyTorch loading; provenance and no ordinary-test downloads |
| 4-5: modularity and Streamlit lifecycle | Pass: separate UI, inference, and storage | Pass: typed service contracts, session-owned drafts, exact active-request matching, scoped shared resources and locks; keyboard and accessible status requirements included |
| 6: configuration and secrets | Pass: reuse existing settings | Pass: service settings validated on use; external secrets, TLS guidance, no secrets in artifacts |
| 7: prediction persistence | Pass: MinIO is required | Pass: only confirmed writes count as success, no alternative store; default-name incompatibility is reported |
| 8: security and safe failure | Pass: trusted environment and safe errors | Pass within cooperative single-host boundaries; explicit failures, uncertain writes, and external-change limits |
| 9: tests and quality gates | Pass: deterministic unit and service integration coverage planned | Pass: isolated integration command, regression tests, Ruff and mypy; report any unrun checks |
| 10: observability and documentation | Pass: safe logging and operational guidance | Pass: allowlisted event metadata, redaction tests, storage and recovery instructions |

No constitutional exception is proposed. The default bucket name remains unchanged even where the target service rejects it; the operator must configure a valid name.

## Project Structure

### Documentation (this feature)

```text
specs/004-classification-persistence/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/classification.md
└── quickstart.md
```

### Source Code (planned)

```text
app/
├── streamlit_app.py                 # add classification page to existing navigation
├── pages/classification.py          # widgets, notice, session state and result display
├── services/model_provider.py       # shared non-rendering model-manager provider
├── services/classification.py       # orchestration, snapshot checks and outcomes
├── services/inference.py            # local model, tokenizer, score validation
├── services/prediction_store.py     # MinIO boundary and typed write outcomes
├── services/model_manager.py        # narrow cooperative model-use/mutation guard
├── services/label_manager.py        # narrow guarded finalization interface
└── utils/logging_config.py          # safe, allowlisted operational events
tests/
├── unit/                            # inference, orchestration, storage and regression
├── integration/                     # coordination and MinIO-compatible store
└── smoke/                           # classification UI and existing-page regressions
```

**Structure Decision**: Extend existing directories rather than introducing a new application or external API. Reuse `load_model_settings`, `load_minio_settings`, `load_app_settings`, `ModelManager` readiness and manifest provenance, and `LabelManager.list_sets`; do not import a page script to obtain services. Extract the model-manager provider into a non-rendering shared module so management and inference use consistent settings and identities. Service-specific configuration remains lazy. Any changes to existing managers are narrowly scoped coordination interfaces, not new management workflows.

## Design and Validation Traceability

| Specification | Design | Validation |
|---|---|---|
| FR-001-003, FR-016; scenarios 1-2, 7, 10 | Page, existing ready-model and fail-closed catalog readers, storage notice and session draft | UI tests for selections, empty/invalid sources, pre-submit notice, retained text and startup without credentials |
| FR-004-005, FR-017; scenarios 3, 8, 11-12 | Immutable snapshots, local-only model provenance, input-pair validation, mutation guards and final revalidation | Boundary and over-limit tests; deterministic concurrent edit, removal, model mutation and dependency-failure tests |
| FR-006-007; scenarios 1, 13 | Exclusive-label scoring and exact one-to-one ranked output validation | Fake model/tokenizer results for score order, ties, missing/duplicate/non-finite outputs and labeling |
| FR-008-009; scenarios 1, 3, 9 | One request-keyed JSON object in configured bucket | Record-schema tests; service-backed create/read check, existing bucket, denied/invalid bucket |
| FR-010-011; scenarios 4-6 | Safe typed failures; no unsafe retry; indeterminate recovery protocol | Fault injection before send, rejected write, lost response/late completion and operator guidance |
| FR-012-014; scenario 7 | Allowlisted diagnostics, no payloads in logs/errors, documented storage and trust | Capture logs/errors with sentinel secrets/input/results; documentation review |
| FR-015 | Isolated unit tests and opt-in compatible-service integration | Offline test invocation and documented service-backed invocation |
| FR-018; scenario 14 | Session-owned active request keyed by exact text, model ID/revision, and label-set ID/revision; exact repeats reuse status, different submissions wait with draft retained | Exact-match, changed-text/selection, and two-session isolation tests |
| FR-019; scenario 15 | Keyboard-operable controls, accessible names, accessible validation/progress/save/error updates; no WCAG claim | Keyboard-only workflow check and accessibility review of control names/status exposure using supported Streamlit APIs |
| SC-001-005, SC-007 | Above contracts and failure behavior | Execute corresponding automated and integration checks; inspect saved record and exact/different in-progress submissions |
| SC-006 | Guided first-attempt exercise | Record participant count, successes and failures; calculate success rate and compare with 90% |
| SC-008 | Accessible controls and state feedback | Record keyboard operation and accessible-name/status checks; do not claim formal WCAG conformance |

See [classification contract](contracts/classification.md) for precise synchronization, outcome, and privacy guarantees and [quickstart](quickstart.md) for validation steps.
