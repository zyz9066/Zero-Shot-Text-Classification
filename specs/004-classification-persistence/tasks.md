---
description: "Implementation tasks for text classification and prediction persistence"
---

# Tasks: Text Classification and Prediction Persistence

**Input**: Design documents from `specs/004-classification-persistence/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/classification.md`, and `quickstart.md`

**Tests**: Required by FR-015 and the project Constitution. Unit tests use deterministic fakes without model downloads; storage integration tests are opt-in and use an isolated MinIO-compatible bucket.

**Organization**: Tasks are grouped by the single P1 user story for independent implementation and validation.

## Phase 1: Setup

**Purpose**: Add the direct runtime dependencies required by the planned inference and storage services.

- [X] T001 Add compatible direct runtime constraints for `torch`, `transformers`, and the MinIO Python client to `pyproject.toml`, regenerate `uv.lock` with `uv`, and preserve Python 3.11+.

## Phase 2: Foundational

**Purpose**: Provide reusable model access and cross-process coordination before classification work begins.

- [X] T002 Extract a non-rendering shared model-manager provider into `app/services/model_provider.py` and update `app/pages/model_management.py` to use it without changing existing model-management behavior.
- [X] T003 Add a canonical native per-model use/mutation guard in `app/services/model_manager.py`; use it for classification and app-managed model deletion or promotion, with bounded acquisition, safe timeout errors, and the documented lock ordering. Preserve download and existing deletion behavior; add focused manager regression coverage in `tests/unit/test_model_manager.py`.
- [X] T004 Add a narrow finalization interface in `app/services/label_manager.py` that validates the complete catalog and holds its existing lock while confirming that a captured stable set ID remains available and valid through the prediction-storage outcome; permit revision changes when the set remains present and valid and preserve existing stale-edit/removal behavior in `tests/unit/test_label_manager.py`.

**Checkpoint**: Shared model access and model/label coordination contracts are ready for the classification story.

## Phase 3: User Story 1 - Classify text and save the prediction (Priority: P1)

**Goal**: Classify one submitted text with a ready local model and valid saved label set, display the ranked result only after a confirmed MinIO write, and safely retain request state across failures.

**Independent Test**: With a ready local model, valid saved label set, and reachable prediction storage, submit non-blank text, inspect the ranked result and metadata, and verify the corresponding MinIO record. Exercise invalid inputs, inference failures, exact and changed in-progress submissions, confirmed and indeterminate storage outcomes, changed dependencies, accessibility, and retained input without downloading models in ordinary unit tests.

### Tests for User Story 1

- [X] T005 [P] [US1] Add deterministic local-inference tests in `tests/unit/test_inference.py` for PyTorch/local-only loading, full premise/hypothesis token limits without truncation, actionable failure when no reliable input bound can be determined, competing-label scoring, tie ordering, and rejection of missing, duplicate, nonnumeric, or non-finite scores.
- [X] T006 [P] [US1] Add prediction-record and storage-outcome tests in `tests/unit/test_prediction_store.py` for strict JSON, exact object key `predictions/<request-id>.json`, record fields, configured/default bucket behavior, bucket creation, confirmed rejection, indeterminate writes, lost acknowledgement/late completion, no retry after a single missing-object lookup, and disabled automatic write retries.
- [X] T007 [P] [US1] Add orchestration tests in `tests/unit/test_classification.py` for validation, captured model and label snapshots, safe failures, retained text, confirmed-save gating, uncertainty guidance, and exact duplicate identity using text plus model and label IDs/revisions; verify a different submission is blocked during processing with its text and selections retained.
- [X] T008 [P] [US1] Add Streamlit `AppTest` coverage in `tests/smoke/test_classification.py` for model/label selection, pre-submit storage notice, result display only after save, retained input, safe error states, exact versus changed in-progress submissions, accessible control names, and accessible status/error content.
- [X] T009 [P] [US1] Add deterministic cooperating-process tests in `tests/integration/test_classification_concurrency.py` for model deletion/promotion exclusion, label edit versus removal during inference, finalization lock ordering, and lock release on failures; extend `tests/integration/test_label_concurrency.py` to preserve existing confirmed deletion, stale edits/removals, unrelated-set updates, and download behavior.
- [X] T010 [P] [US1] Add an explicitly opt-in MinIO-compatible storage test in `tests/integration/test_prediction_storage.py` that uses only a configured isolated test bucket and verifies a complete write/read without contacting services during ordinary tests.
- [X] T011 [P] [US1] Add safe-logging tests in `tests/unit/test_classification_logging.py` that assert useful allowlisted model, inference, request, and storage outcome metadata is emitted while sentinel input, prediction data, credentials, tokens, exception payloads, and sensitive local paths are excluded.

### Implementation for User Story 1

- [X] T012 [P] [US1] Define typed immutable request, model-snapshot, candidate-label-snapshot, and result values in `app/services/classification.py`: the request constraint is "An immutable request contains a UUID request identifier, the exact submitted text, a model snapshot, and a label-set snapshot"; the model snapshot "Contains display name, model identifier, selected local artifact identity, and recorded resolved revision"; the label snapshot "Contains the stable saved-set ID, set revision and name captured on submission, and an ordered immutable tuple of at least two valid unique labels." Use the existing manager's 40-character resolved-revision hash; represent a genuinely unavailable revision as `null`, never fabricate it.
- [X] T013 [P] [US1] Implement an allowlisted operational logging boundary in `app/utils/logging_config.py` for useful non-sensitive model, inference, request, and storage lifecycle events; define safe structured fields and ensure callers cannot interpolate raw payloads or third-party exception text.
- [X] T014 [P] [US1] Implement local PyTorch inference in `app/services/inference.py`: load only the app-managed local artifact with `local_files_only` and remote code disabled; reject text that is blank after whitespace checking, is not valid for the model, or would exceed the model's actual pair-input limit for any candidate; fail actionably if no reliable bound can be determined; use the same full untruncated premise/hypothesis pairs for inference and return "one finite numeric score per label ordered descending" with "top class and its identical score"; do not describe scores as calibrated probabilities unless established.
- [X] T015 [P] [US1] Implement the typed MinIO prediction boundary in `app/services/prediction_store.py`, using the existing lazy MinIO settings loader and configured bucket or default `zeroshot_learning_output`; create a missing bucket only when permitted, never substitute another bucket, verify the client and transport do not automatically retry writes, and distinguish confirmed failures from indeterminate writes. Write one strict JSON object at `predictions/<request-id>.json` with `request_id` as a UUID string equal to the key identifier; exact submitted `input_text`; `predicted_class` equal to the first ranked label; finite `predicted_score` equal to its first ranked score; captured `candidate_labels`; exactly one ranked result per candidate in descending score order; captured model name and identifier; resolved model revision or JSON `null` only when genuinely unavailable; UTC ISO 8601 timestamp identical to the displayed value; and effective application version.
- [X] T016 [US1] Implement request orchestration in `app/services/classification.py`: capture and revalidate model and label snapshots, acquire the model guard before the catalog lock, allow label revisions to change while requiring the same valid set ID at finalization, hold the catalog lock through the storage outcome, retain text on failure, and report success only after a confirmed write. Match active duplicates by exact text plus model ID/revision and label-set ID/revision; block a different submission until completion while retaining its text and selections. Register one in-progress request per session and return its status on an exact repeat without starting another worker or write; assign a new request ID to a later intentional submission.
- [X] T017 [US1] Implement the classification interface in `app/pages/classification.py` with session-scoped request state, a pre-submit storage notice, trusted-environment/access-limit guidance, ready-model and valid-label selection, ranked-result display, and safe actionable validation, inference, confirmed-failure, and indeterminate-outcome guidance; keep Streamlit calls on the script thread, make controls keyboard-operable with accessible names and accessible validation/progress/save/error updates, do not present hidden navigation as access control, and exclude sensitive values from logs and errors.
- [X] T018 [US1] Register the Classification page through the existing `st.Page`/`st.navigation` structure in `app/streamlit_app.py`, preserving shell startup without MinIO credentials and preserving existing overview, model-management, and label-management routes.

**Checkpoint**: The P1 story is independently usable, with confirmed-save success semantics, safe recovery, accessible interactions, and deterministic coverage of failure and concurrency paths.

## Phase 4: Polish and Cross-Cutting Concerns

**Purpose**: Complete operational documentation, quality gates, service-backed validation, accessibility review, and measurable usability reporting.

- [X] T019 Complete `specs/004-classification-persistence/quickstart.md` with the implemented configuration and launch steps, storage location and retention behavior, trusted-environment and access limitations, exact/changed in-progress submission behavior, keyboard/accessibility checks, opt-in integration command, and verified operator recovery guidance for uncertain writes.
- [X] T020 Run `uv run --locked pytest tests/unit tests/smoke tests/integration/test_classification_concurrency.py tests/integration/test_label_concurrency.py`, `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, and `uv run --locked mypy`; resolve feature-caused failures and record any unavailable checks in `specs/004-classification-persistence/quickstart.md`.
- [X] T021 Run `tests/integration/test_prediction_storage.py` only with an explicitly configured isolated MinIO-compatible test bucket; record service/client versions and actual result or skip reason in `specs/004-classification-persistence/quickstart.md`, and do not claim unrun coverage.
- [X] T022 Review the full classification flow in `app/pages/classification.py` using keyboard-only navigation and assistive technology; record control-name and validation/progress/save/error exposure results in `specs/004-classification-persistence/quickstart.md` without claiming formal WCAG conformance. The keyboard and browser accessibility-tree review is recorded; a manual screen-reader session was unavailable.
- [X] T023 Conduct the first-attempt usability exercise with ready model, labels, and storage; record participant count, successes, failures, and calculated rate against the 90% target in `specs/004-classification-persistence/quickstart.md`, or explicitly mark it unverified if participants are unavailable. The exercise is recorded as unverified because no participants were available.

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001; no feature tasks can use the new runtime dependencies until the lockfile is updated.
- **Foundational (Phase 2)**: T002-T004 depend on T001 and block story implementation.
- **User Story 1 (Phase 3)**: T005-T011 are authored against the service contracts after Phase 2; implementation then proceeds T012/T013 in parallel, T014/T015 in parallel, followed by T016, T017, and T018.
- **Polish (Phase 4)**: T019-T023 depend on the integrated story; the live storage and usability checks additionally require their respective external prerequisites.

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Setup and Foundational phases; no other feature story is required.

### Parallel Opportunities

- After Phase 2, test tasks T005-T011 can be authored in parallel because they use separate test files.
- After tests are ready, T012 (shared types) and T013 (logging boundary) can be implemented in parallel.
- After T012/T013, T014 (inference) and T015 (prediction storage) can proceed in parallel in separate service files.
- T019 documentation can be prepared after behavior is stable; external storage, accessibility, and usability validation remain separate checks.

## Parallel Example: User Story 1

After Phase 2, contributors can author inference, storage, orchestration, UI, coordination, opt-in integration, and logging tests in T005-T011 concurrently. After the tests are reviewed, implement T012 and T013 in parallel, then implement T014 and T015 in parallel; integrate them in T016 before completing the page and navigation.

## Implementation Strategy

### MVP First

1. Complete dependency setup and the model/label coordination foundation.
2. Complete User Story 1 through confirmed MinIO persistence and the classification page.
3. Validate the independent story with deterministic tests and the focused regression/quality gates.
4. Run the opt-in MinIO integration, accessibility review, and usability exercises when their prerequisites are available; report unrun checks explicitly.

### Incremental Delivery

Deliver the single P1 story as one coherent increment because displaying a prediction without its required MinIO record is not a successful classification under the specification. Keep unit and smoke tests service-independent; add service-backed and human usability evidence separately.

## Phase 5: Convergence

- [X] T024 Complete and record the full-flow accessibility review, covering keyboard operation, accessible names for every control, and accessible validation, progress, save, and error updates; fix any gaps per SC-008 (partial).
