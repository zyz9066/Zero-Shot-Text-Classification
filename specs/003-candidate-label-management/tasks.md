---
description: "Implementation tasks for candidate-label management"
---

# Tasks: Candidate-Label Management

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contract](contracts/label-management.md), and [quickstart.md](quickstart.md).

**Tests**: The feature specification defines independent validation, the approved planning input requests deterministic tests, and the Constitution requires automated core-service tests. Tests use temporary directories and do not require network access, model downloads, or service credentials.

**Organization**: The specification contains one P1 user story; its phase is the independently testable MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks in the same group after their prerequisites are complete; each touches different files.
- **[US1]**: Belongs to User Story 1.
- Paths are repository-relative.

## Phase 1: Setup

**Purpose**: Prepare the existing project for local label persistence without changing other features.

- [X] T001 [P] Add `filelock>=4.2.10` as a direct runtime dependency in `pyproject.toml` and update `uv.lock` reproducibly, preserving Python 3.11+ and existing dependencies.
- [X] T002 [P] Ignore the default mutable `configs/labels.yaml`, its initialization marker, lock, and same-directory temporary files in `.gitignore` without hiding unrelated configuration files.

## Phase 2: Foundational Prerequisites

**Purpose**: Resolve label-specific configuration lazily, without changing application startup or the existing model/MinIO settings.

- [X] T003 Add an independently testable label-path resolver in `app/config/label_settings.py`: explicit injection for tests, then non-empty `LABEL_CONFIG_FILE`, then `configs/labels.yaml`; report an empty override safely and defer resolution until label management is used. Test explicit-path precedence, environment override, default, and empty override.

**Checkpoint**: Setup and path resolution are ready; User Story 1 can begin.

## Phase 3: User Story 1 - Manage reusable candidate-label sets (Priority: P1)

**Goal**: Enable trusted local administrators to create, inspect, edit, and safely remove persistent validated label sets for future classification.

**Independent Test**: Without inference or service credentials, create a named set with two labels, restart and inspect it, update it, exercise validation and stale-change handling, and confirm removal while preserving unrelated sets.

### Tests for User Story 1

Write focused tests before the corresponding implementation. All four files below can be authored in parallel after Phase 2; use the documented contract rather than assuming unimplemented internals.

- [X] T004 [P] [US1] Add catalog contract and validation tests in `tests/unit/test_label_catalog.py` for valid/empty catalogs, preserved order and case, case-folded/trimmed uniqueness, duplicate mapping keys, invalid types, IDs, revisions, schema versions, unknown fields, and all-or-nothing rejection.
- [X] T005 [P] [US1] Add service and failure-recovery tests in `tests/unit/test_label_manager.py` for first use, pre-provisioned catalog, initialization marker states, restart, final-set deletion, invalid/unreadable state, stale snapshots, cancellation, pre-commit failures, indeterminate outcomes, draft-facing error categories, and secret/path-safe messages.
- [X] T006 [P] [US1] Add deterministic local multiprocess tests in `tests/integration/test_label_concurrency.py` for concurrent updates to different sets, duplicate-name creates/renames, stale edits/deletes, lock timeout, and preservation of unrelated sets using isolated temporary directories.
- [X] T007 [P] [US1] Add Streamlit `AppTest` coverage in `tests/smoke/test_label_management.py` for navigation without model or storage credentials, creation/editing, field and collection errors, session-scoped drafts across reruns and conflicts, empty/error states, and confirmed versus cancelled removal.

### Implementation for User Story 1

- [X] T008 [US1] Define immutable catalog and label-set values in `app/config/label_catalog.py` with these data-model constraints: ID is an \"Opaque UUID generated at creation, unique within the catalog and stable through rename or edits\"; revision is a \"Positive integer\" that starts at 1 and increments on every successful edit; name is a \"Non-empty trimmed string, preserving display case\"; labels are an \"Ordered collection of at least two valid, distinct candidate labels\".
- [X] T009 [US1] Implement complete UTF-8 YAML parsing, serialization, and validation in `app/config/label_catalog.py`: schema version is \"Integer `1`; unknown or missing versions are invalid\"; the set list may be empty; reject duplicate mapping keys, unknown fields, invalid IDs/revisions, and normalized duplicate names or labels; preserve saved order and trimmed spelling, comparing with `casefold()`; return no partial results.
- [X] T010 [US1] Define typed snapshots, structured safe errors, and a canonical same-directory lock in `app/services/label_manager.py`; use native `filelock` with `preserve_lock_file=True`, `fallback_to_soft=False`, and a 10-second timeout, and hold it across marker/catalog reads and complete mutations.
- [X] T011 [US1] Implement initialization and recovery states in `app/services/label_manager.py`: marker contents are \"UTF-8 YAML mapping with exactly `schema_version: 1`\"; validate and durably establish the marker before exposing a provisioned catalog or the first save; distinguish valid empty, first use, missing-after-initialization, invalid/unreadable evidence, and partial initialization; preserve the marker after final-set removal and warn that total evidence loss is indistinguishable from first use.
- [X] T012 [US1] Implement safe catalog replacement in `app/services/label_manager.py` using a unique same-directory temporary file, file flush/`fsync`, and `os.replace`; preserve prior sets on confirmed pre-commit failures, clean only owned temporary files, and surface uncertain replacement or post-commit durability outcomes as indeterminate with inspection guidance.
- [X] T013 [US1] Implement the `list_sets`, create, update, and confirmed removal service contract in `app/services/label_manager.py`: validate against the latest whole catalog under the lock, reject stale ID/revision pairs, reject duplicate-name races, preserve unrelated sets, return immutable saved snapshots, and log only safe non-sensitive operation metadata.
- [X] T014 [US1] Create the management UI in `app/pages/label_management.py` using native widgets and separate per-session draft state: show trusted-environment guidance, saved sets, first-use/recovery warnings, field/collection validation, and preserve draft text and captured revision across reruns, errors, and refresh after stale conflicts.
- [X] T015 [US1] Add explicit removal confirmation, cancellation without mutation, and safe success, failure, stale, and indeterminate outcome presentation in `app/pages/label_management.py`; keep draft state isolated between sessions and do not request credentials or initiate inference.
- [X] T016 [US1] Register the new page through the existing `st.Page`/`st.navigation` structure in `app/streamlit_app.py`, preserving the existing overview and model-management routes and shell startup behavior.

**Checkpoint**: US1 is independently usable and its focused tests cover the specified normal, failure, recovery, and concurrent flows.

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T017 [P] Document configuration, ignored files and overrides, validation, trusted-environment limits, supported locking scope, backup/recovery, and durable-marker limitations in `specs/003-candidate-label-management/quickstart.md`; retain the illustrative catalog contract in `specs/003-candidate-label-management/contracts/label-management.md`.
- [X] T018 [P] Add concise label-management launch and recovery guidance to `README.md` without expanding into the deferred full project documentation.
- [X] T019 Run the focused pytest files in `tests/unit/test_label_catalog.py`, `tests/unit/test_label_manager.py`, `tests/integration/test_label_concurrency.py`, and `tests/smoke/test_label_management.py`, followed by existing unit/smoke regression tests, Ruff, formatting, and mypy for `app/`; resolve feature-caused failures and report any unavailable Windows/POSIX validation.
- [X] T020 Run the documented 3-minute creation/restart check and the 90% first-attempt usability protocol in `specs/003-candidate-label-management/quickstart.md`; record measured results and participant count, or explicitly report the check as unverified if representative participants are unavailable.

## Dependencies & Execution Order

### Phase and story dependencies

```text
Phase 1: T001 + T002
         ↓
Phase 2: T003
         ↓
Phase 3: US1 tests T004-T007 → catalog T008-T009 → service T010-T013 → UI T014-T015 → routing T016
         ↓
Phase 4: T017 + T018 → T019 → T020
```

- US1 is the only story and has no dependency on another feature story; it builds on the existing foundation and model-management application.
- T001 and T002 touch separate files and can proceed in parallel; T003 is a prerequisite for story work.
- T004-T007 touch different files and can be authored in parallel after Phase 2; the corresponding implementation follows them. T008-T016 have the sequential dependencies shown because later work consumes earlier contracts or modifies the same file.
- T017 and T018 may proceed in parallel after US1; T019 validates the integrated change. T020 requires a working feature and a representative usability exercise; do not claim its threshold passed without measurement.
- The custom requirements checklist in `specs/003-candidate-label-management/checklists/label-management.md` is reviewer-owned and currently unchecked. Review it before invoking `/speckit-implement`; task generation does not mark its items complete.

## Parallel Example: User Story 1

After Phase 2, separate contributors can author the four test files in T004-T007 independently. Merge them before beginning their corresponding implementations; then follow the catalog → service → UI → routing order. After the story is integrated, T017 and T018 can update their separate documentation files concurrently.

## Implementation Strategy

### MVP First

1. Finish setup and the lazy label-path resolver.
2. Complete all US1 tasks, including validation, persistence, recovery, concurrency, and UI; these are all required parts of the single P1 story.
3. Run focused and regression checks, then demonstrate the independent test without model downloads or credentials.

### Incremental Delivery

Within the MVP, build the catalog contract first, then the persistent service, then the session-safe UI. Complete documentation and quality gates before considering the feature finished; record any usability or platform validation that cannot be performed.

## Phase 5: Convergence

- [X] T021 [US1] CRITICAL Handle path-resolution failures in `app/services/label_manager.py` and `app/pages/label_management.py` as safe, actionable configuration errors without exposing internal paths; retain drafts and add focused failure-injection tests per Constitution 8 and FR-010 (contradicts).
- [X] T022 [US1] CRITICAL Track catalog commit state through lock release in `app/services/label_manager.py` so an error after a committed create, update, or removal is never reported as a confirmed pre-commit failure; retain drafts and require inspection when appropriate, with fault-injection tests per Constitution 8 and FR-010 (contradicts).
- [X] T023 [US1] Preserve and accurately display each valid label, including embedded newlines, when opening, editing, and saving sets in `app/pages/label_management.py`; add a round-trip UI regression test per FR-001 and T014 (contradicts).
- [X] T024 [US1] Distinguish indeterminate write outcomes from confirmed failures in safe operational logs in `app/services/label_manager.py`, including necessary logging support and fault-injection coverage in `tests/unit/test_label_manager.py`, per FR-010 and Constitution 10 (contradicts).
- [X] T025 [US1] Synchronize competing local processes in `tests/integration/test_label_concurrency.py` to deterministically exercise overlapping create, rename, and unrelated-set updates under the lock per T006 (partial).
- [X] T026 [US1] Add `AppTest` coverage in `tests/smoke/test_label_management.py` for a successful edit, name and label validation, write-failure draft retention, and indeterminate-outcome inspection before retry per T007 and T015 (partial).

## Phase 6: Convergence

- [X] T027 [US1] CRITICAL Handle filesystem-root and other invalid catalog paths safely through all path and sidecar construction in `app/services/label_manager.py`, preserving drafts and returning actionable errors without exposing paths; add service and UI regression tests per Constitution 8, FR-010, and T021 (partial).
- [X] T028 [US1] CRITICAL Reject names and labels that cannot be encoded as UTF-8 at the validation boundary in `app/config/label_catalog.py`, fail closed for saved catalogs containing such values, and provide safe corrective errors in `app/services/label_manager.py`; add catalog, service, and UI tests in `tests/unit/test_label_catalog.py`, `tests/unit/test_label_manager.py`, and `tests/smoke/test_label_management.py` per Constitution 8 and FR-009 (contradicts).
- [X] T029 [US1] Ensure the set explicitly selected for removal is the one removed, or make the opened removal target unambiguous and prevent a conflicting selection from triggering deletion in `app/pages/label_management.py`; add a two-set UI regression test in `tests/smoke/test_label_management.py` per FR-008 and US1/AC6 (contradicts).

## Phase 7: Convergence

- [X] T030 [US1] CRITICAL Handle parser recursion and similarly bounded malformed or excessively nested saved YAML safely at the catalog boundary in `app/config/label_catalog.py` and `app/services/label_manager.py`; fail closed without changing catalog or marker, retain UI drafts, and provide actionable path-safe recovery feedback, with focused service and AppTest regressions per Constitution 8 and FR-009/FR-010 (contradicts).
- [X] T031 [US1] Prevent a conflicting saved-set selection from causing an edit to update a different opened set in `app/pages/label_management.py`; make the edit target unambiguous or require matching selection, preserve drafts, and add a two-set AppTest regression per FR-007 and US1/AC5 (contradicts).
- [X] T032 [US1] Provide actionable stale-removal and refresh/recovery guidance when an opened set was removed while other sets remain in `app/pages/label_management.py`; retain unsaved edits and prevent unintended changes, with a two-set AppTest regression per FR-015 and US1/AC13 (partial).

## Phase 8: Convergence

- [X] T033 [US1] CRITICAL Handle invalid YAML scalar construction failures, including malformed timestamps and oversized integers, safely at the parsing boundary in `app/config/label_catalog.py`; fail closed for catalogs and markers, preserve files and UI drafts, and add service and AppTest regression coverage per Constitution 8, FR-009/FR-010, and T030 (partial).
