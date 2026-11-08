# Tasks: Application Foundation and Configuration

**Input**: Design documents from `specs/001-application-foundation-config/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/configuration-and-shell.md`, and `quickstart.md`

**Tests**: Included because the project Constitution and implementation plan require automated unit and shell smoke coverage.

**Organization**: Tasks are grouped by user story so the P1 foundation can be implemented and validated as an independent increment.

## Phase 1: Setup

**Purpose**: Establish the Python project and repository hygiene for the planned application structure.

- [X] T001 [P] Define Python 3.11+ project metadata, Streamlit and PyYAML runtime dependencies, pytest/Ruff/mypy development tools, and tool configuration in `pyproject.toml`; generate the reproducible `uv.lock`.
- [X] T002 [P] Update `.gitignore` to exclude `.env` files, `.venv/`, `models/`, and `.cache/huggingface/` while preserving non-secret examples.

## Phase 2: Foundational

**Purpose**: Create the shared settings types required before the application story.

- [X] T003 Define immutable, type-annotated application, model-runtime, and MinIO settings plus the safe configuration-issue type in `app/config/settings.py`.

## Phase 3: User Story 1 - Configure and launch the application (Priority: P1)

**Goal**: Give developers a runnable initial Streamlit shell backed by centralized configuration with explicit precedence, scoped validation, and safe diagnostics.

**Independent Test**: With valid shell-level settings and no model or MinIO credentials, launch the initial page. Unit coverage confirms environment-over-YAML-over-default resolution, service-specific validation is deferred until use, and configuration errors/logs do not expose secrets, raw text, or absolute paths.

### Tests for User Story 1

- [X] T004 [P] [US1] Add configuration-loader unit tests for environment-over-YAML-over-default precedence, documented defaults, malformed/non-mapping YAML, invalid types and boolean values, unknown keys, explicit missing config paths, deferred service validation, and secret/path-safe errors in `tests/unit/test_config_loader.py`.
- [X] T005 [P] [US1] Add logging configuration tests that require credentials, tokens, raw input text, and absolute paths to be absent from emitted events in `tests/unit/test_logging_config.py`.
- [X] T006 [P] [US1] Add a Streamlit AppTest smoke test proving the initial shell renders when model and MinIO credentials are absent in `tests/smoke/test_app_startup.py`.

### Implementation for User Story 1

- [X] T007 [P] [US1] Implement YAML parsing with safe loading, explicit environment/YAML/default precedence, typed conversion, scoped validation, and redacted configuration errors in `app/config/loader.py`.
- [X] T008 [P] [US1] Configure structured standard-library logging with stable event names and a non-sensitive field allow-list in `app/utils/logging_config.py`.
- [X] T009 [P] [US1] Add non-secret application, model/cache, and MinIO bucket defaults matching the configuration contract in `configs/app.yaml`.
- [X] T010 [US1] Implement the initial Streamlit entry point that loads only application-level settings, initializes safe logging, and renders the shell without requiring model or MinIO credentials in `app/streamlit_app.py`.

**Checkpoint**: User Story 1 is independently usable when the shell starts without service credentials and the focused unit and smoke tests pass.

## Phase 4: Polish and Cross-Cutting Concerns

**Purpose**: Keep the developer validation guide accurate and run the feature's required quality checks.

- [X] T011 Align the feature quickstart's configuration names, launch command, expected behavior, and test commands with the implemented foundation in `specs/001-application-foundation-config/quickstart.md`.
- [X] T012 Run pytest, Ruff lint/format checks, and mypy using the locked project environment; resolve feature-related failures in `tests/`, `app/`, and `pyproject.toml`.

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001 and T002 may run in parallel.
- **Foundational (Phase 2)**: Starts after setup; T003 establishes the shared settings types.
- **User Story 1 (Phase 3)**: Starts after T003. T004, T005, and T006 use separate files and may be authored in parallel; each test precedes its corresponding implementation. T007 follows T004. T008 follows T005. T009 may proceed in parallel with T007 and T008. T010 follows T007, T008, and T009.
- **Polish (Phase 4)**: Follows User Story 1. T011 updates the quickstart to match the completed feature; T012 requires the feature files and dependencies to be in place.

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Setup and Foundational phases. No other user story exists in this feature.

### Parallel Opportunities

- Setup: T001 and T002.
- Foundational: T003.
- User Story 1 tests: T004, T005, and T006.
- User Story 1 implementation: T007 and T008 after their respective tests; T009 may run in parallel with those tasks.
- Polish: T011 updates the quickstart after the P1 story; T012 runs after the relevant files are ready.

## Parallel Example: User Story 1

```text
Task: T004 Add configuration-loader requirement tests in tests/unit/test_config_loader.py
Task: T005 Add secret-safe logging requirement tests in tests/unit/test_logging_config.py
Task: T006 Add shell startup smoke test in tests/smoke/test_app_startup.py
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 project setup.
2. Complete Phase 2 settings foundations.
3. Complete Phase 3 User Story 1, including its focused tests.
4. Stop and validate that the shell starts without service credentials and that its configuration/error behavior matches the contract.

### Incremental Delivery

- Deliver this feature as the application foundation only.
- Add model management, candidate-label management, inference, and MinIO prediction persistence through their own feature specifications; do not broaden this task list to implement them.
- Complete the feature quickstart and static checks after the P1 story is functional.

## Notes

- Every task follows the required checkbox, sequential ID, optional parallel marker, required user-story label for story tasks, and concrete file-path format.
- `[P]` marks tasks that can work independently on different files; non-parallel tasks have ordering or shared-file dependencies.
- Task IDs T001-T012 are sequential; all tasks name the files or directories they create, update, or validate.

## Phase 5: Convergence

- [X] T013 Make the documented Streamlit launch command reliably import `app` from the repository root and add or adjust a launch regression check per FR-008 (partial)
