# Implementation Plan: Candidate-Label Management

**Branch**: `003-candidate-label-management` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-candidate-label-management/spec.md`

## Summary

Add a local/trusted administration page for durable named candidate-label sets. A separately testable service validates a complete YAML catalog, serializes cooperating local writers, rejects stale edits and removals, and exposes only validated saved snapshots for later classification. A durable initialization marker distinguishes ordinary first use from a subsequently missing catalog; recovery is explicit and fail-closed. No inference, MinIO writes, authentication, or application implementation is part of this planning phase.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: Existing Streamlit, PyYAML, and pytest; add `filelock>=4.2.10` as an explicit runtime dependency for cross-process locking (already present transitively in `uv.lock`). Preserve Ruff, mypy, and locked `uv` workflow.

**Storage**: Non-secret YAML label catalog, durable initialization marker, and separate lock file in the catalog directory; no prediction storage. File-system limitations and recovery are described in [research.md](research.md).

**Testing**: pytest unit/integration tests with temporary directories, subprocess concurrency tests, and Streamlit `AppTest` smoke tests. No network, model downloads, or service credentials.

**Target Platform**: Local Windows and POSIX systems with a writable local filesystem; cooperating application processes on one host. Network filesystems and multiple hosts are not supported without a separately designed locking/storage contract.

**Project Type**: Existing Streamlit multipage application with isolated configuration and service layers.

**Performance Goals**: Create a two-label set within 3 minutes; assess the 90% first-attempt success target by a documented usability exercise. No latency or throughput targets were specified.

**Constraints**: Fail closed for invalid/unreadable initialized configuration; preserve drafts, saved sets, and scope boundaries; no credentials required; safe errors; explicit removal confirmation.

**Scale/Scope**: Small administrator-managed configuration and a few trusted local sessions, not a distributed or public multi-user service. No arbitrary label/count limits are imposed by the specification.

## Constitution Check

| Principle | Before research | Post-design |
|---|---|---|
| 1-3: stack, Python quality, model reproducibility | Pass: no stack replacement or model loading | Pass: explicit file-lock dependency supports, not replaces, the stack; no inference |
| 4-5: modular boundaries and Streamlit state | Pass: UI delegates operations and drafts are session-scoped | Pass: [contract](contracts/label-management.md) separates UI and service; no cached durable state |
| 6: configuration and secrets | Pass: non-secret label configuration is explicit | Pass: YAML catalog, marker, lock, and settings are documented; no secrets stored |
| 7: prediction persistence | Pass: no prediction outputs in scope | Pass: no alternative prediction store introduced |
| 8: security and safe failure | Pass: validation, trusted-environment limitation, safe errors | Pass with stated local-filesystem and marker-loss limits; failures require explicit recovery |
| 9: tests and quality gates | Pass: deterministic isolated tests planned | Pass: unit, local multiprocess, and UI tests planned; existing checks retained |
| 10: observability and documentation | Pass: actionable, redacted outcomes and documentation planned | Pass: quickstart and recovery guidance included; no raw labels in logs by default |

No constitutional exception is proposed. File-loss detection and durability guarantees are bounded explicitly rather than claiming protection against removal of all evidence or unsupported filesystems.

## Project Structure

### Documentation (this feature)

```text
specs/003-candidate-label-management/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/label-management.md
├── quickstart.md
└── tasks.md                      # future /speckit-tasks output; not created here
```

### Source Code (planned)

```text
app/
├── streamlit_app.py              # register label-management page
├── pages/label_management.py     # presentation and session-scoped drafts
├── config/label_catalog.py       # catalog parsing and validation
└── services/label_manager.py     # persistence, locking, revision checks
configs/
└── labels.yaml                   # proposed default, generated on save, non-secret
tests/
├── unit/test_label_catalog.py
├── unit/test_label_manager.py
├── integration/test_label_concurrency.py
└── smoke/test_label_management.py
```

**Structure Decision**: Follow the existing `app/pages`, `app/config`, `app/services`, and `tests` boundaries. Use a separate label-specific settings loader or explicit path argument following existing configuration precedence; do not make label availability a shell startup prerequisite. Ignore the default mutable catalog, marker, lock, and temporary files; document that override paths must be outside Git or separately ignored. Provide an explicit configuration example.

## Design and Validation Traceability

| Specification | Design | Validation |
|---|---|---|
| FR-001-005; scenarios 1-5 | UI drafts and service validation, stable set identity, normalized comparisons | Unit and `AppTest` cases for create, inspect, edit, duplicate/blank values, case-only rename, retained drafts |
| FR-006-008; scenarios 1, 5-6 | Durable validated snapshots, scoped updates and confirmation | Restart/read tests; two-set preservation; confirmed and cancelled removal |
| FR-009-010; scenarios 7-9 | Fail-closed catalog state, transactional writes and recovery | Empty, malformed, partial-invalid, unreadable/unwritable, injected pre-commit failures and restart tests |
| FR-011-014; scenarios 10-12 | Independent service configuration, safe error/log policy, trusted admin guidance | Startup/UI without credentials or models; log redaction; documentation review |
| FR-015; scenario 13 | Revision-checked mutation under cross-process lock | Stale update/delete, overlapping writers, unrelated-set preservation, duplicate-name races |
| FR-016; scenarios 7, 14 | Durable marker and missing-file state machine | First use, first valid load/save, restart, last-set removal, missing/invalid marker/catalog and crash points |
| SC-001 | Quickstart timed creation and restart | Record elapsed time and persisted result |
| SC-002-004 | Above validation and failure handling | All specified negative and preservation cases pass |
| SC-005 | Quickstart usability protocol | Record participant count and first-attempt successes; report 90% threshold without claiming an unrun result |

Detailed schemas, state transitions, and operation contracts are in [data-model.md](data-model.md) and [label-management.md](contracts/label-management.md).
