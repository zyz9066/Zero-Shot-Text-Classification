---
description: "Task list for Model Lifecycle Management"
---

# Tasks: Model Lifecycle Management

**Input**: Design documents from `specs/002-model-lifecycle-management/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, and `quickstart.md`

**Tests**: Included because the specification and plan require deterministic unit and Streamlit smoke coverage. Tests must use mocks or lightweight fixtures and must not download full models or require network access.

**Organization**: Tasks are grouped around the single P1 user story so it can be implemented and validated as an independent increment.

## Phase 1: Setup

**Purpose**: Add the feature's direct Hub dependency and preserve repository hygiene.

- [X] T001 Add `huggingface_hub` as a direct runtime dependency in `pyproject.toml` and regenerate `uv.lock` with the supported Python environment.
- [X] T002 Verify `.gitignore` excludes `models/`, `.cache/huggingface/`, and local secret files; append only missing patterns while preserving `.env.example` if present.

## Phase 2: Foundational

**Purpose**: Establish and validate the non-secret model catalog used by all model lifecycle operations.

- [X] T003 [P] Add catalog validation tests for required fields, optional revisions, duplicate identifiers, unsupported tasks, unknown keys, and malformed/non-mapping YAML in `tests/unit/test_model_catalog.py`.
- [X] T004 Implement the configuration-driven catalog parser in `app/config/model_catalog.py` and add the two required initial model entries to `configs/models.yaml`.

**Checkpoint**: A valid, extensible catalog loads without changing feature 001's application settings contract.

## Phase 3: User Story 1 - Manage configured model availability (Priority: P1)

**Goal**: Let a trusted-environment administrator inspect configured models, download and identify complete local snapshots, and safely delete models or clear the Hub cache.

**Independent Test**: With a two-entry catalog and mocked Hub operations, verify the catalog states, revision provenance, duplicate-download behavior, failed-download recovery, deletion boundaries, explicit cache-cleanup preview/confirmation, and administration without a Hugging Face token for public models.

### Tests for User Story 1

- [X] T005 [P] [US1] Add Hub adapter tests for default/configured revision resolution, pinned snapshot downloads, public-model access without a token, and safe handling of Hub errors in `tests/unit/test_huggingface_hub_adapter.py`.
- [X] T006 [P] [US1] Add model manager tests for availability states, valid-manifest reuse, same-model in-flight deduplication, staged-download failure recovery, preservation of complete installations, deletion path containment, and cache-cleanup preview/cancel behavior in `tests/unit/test_model_manager.py`.
- [X] T007 [P] [US1] Add a Streamlit AppTest smoke test for catalog visibility, model-operation status, and startup without a Hugging Face token in `tests/smoke/test_model_management.py`.

### Implementation for User Story 1

- [X] T008 [US1] Implement the Hugging Face Hub adapter for model metadata/revision resolution, full snapshot downloads, cache inspection, and cache-aware deletion in `app/services/huggingface_hub_adapter.py`.
- [X] T009 [US1] Implement catalog-driven local availability, thread-safe operation state, duplicate-request handling, staged snapshot copying, provenance manifests, and ready-state promotion in `app/services/model_manager.py`.
- [X] T010 [US1] Implement confirmed app-managed model deletion and separate cache cleanup with configured-path containment and safe operation feedback in `app/services/model_manager.py`.
- [X] T011 [US1] Add the model-management page and register it with `st.Page`/`st.navigation`, displaying catalog/status, download progress, revision provenance, and explicit deletion/cache-cleanup confirmations in `app/pages/model_management.py` and `app/streamlit_app.py`.

**Checkpoint**: The administrator can manage configured models without inference or prediction storage; partial downloads are never ready, and app-managed models survive Hub-cache cleanup.

## Phase 4: Polish and Cross-Cutting Concerns

**Purpose**: Keep local operating instructions accurate and verify the feature's quality gates.


## Dependencies and Execution Order

- **Polish (Phase 4)**: T012 follows the user story implementation. T013 runs after all feature files and dependency updates are complete.

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Setup and the model-catalog foundation only. It is the sole story in this feature and does not depend on candidate-label, inference, or MinIO features.

### Parallel Opportunities

- Setup: T001 and T002.
- Catalog foundation test: T003 can run independently from setup work.
- User Story 1 tests: T005, T006, and T007 use separate files and can be authored in parallel after T004 defines the catalog contract.
- Hub adapter (T008) and user-story tests (T006/T007) can proceed in parallel; the manager implementation waits for its adapter and tests.

## Parallel Example: User Story 1

```text
Task: T005 Add mocked Hub adapter tests in tests/unit/test_huggingface_hub_adapter.py
Task: T006 Add model lifecycle and safe cleanup tests in tests/unit/test_model_manager.py
Task: T007 Add model-management AppTest coverage in tests/smoke/test_model_management.py
```

## Implementation Strategy

### MVP First

1. Complete dependency and repository-hygiene setup.
2. Add and validate the configured model catalog.
3. Complete User Story 1 with mocked Hub operations and deterministic tests.
4. Stop and validate catalog display, download/revision state, duplicate requests, recovery, deletion, and cache cleanup without downloading full models in automated tests.

### Incremental Delivery

- Deliver model lifecycle management only.
- Keep candidate-label management, inference, and MinIO prediction persistence for their own feature specifications.
- Finish the feature quickstart and quality gates after the P1 story works independently.

## Notes

- Every task has a sequential ID, checkbox, concrete file path, and `[US1]` label for user-story tasks.
- `[P]` is used only when tasks can work on separate files without dependencies on incomplete tasks.
- Test tasks precede their corresponding implementation tasks; no task requires a live Hub download for automated validation.

## Phase 5: Convergence

- [X] T014 Handle incomplete Hub cache downloads with the supported prune/cache API and test preview plus confirmed cleanup against realistic incomplete-cache entries per FR-009, SC-005, and plan Decision 5 (partial).
- [X] T015 Keep `HF_TOKEN` out of the `st.cache_resource`-cached manager and resolve it only when making Hub requests per plan Decision 6 (contradicts).
- [X] T016 Add a deterministic failure-then-success download retry test that proves readiness is reached without damaging a prior complete installation per US1/AC4 and SC-004 (partial).
- [X] T017 Include an allowlisted, non-sensitive model identifier in lifecycle log events per plan Observability and Documentation (partial).
- [X] T018 Replace tab indentation in the quickstart YAML example and validate the fenced example with a YAML parser per T012 (partial).
