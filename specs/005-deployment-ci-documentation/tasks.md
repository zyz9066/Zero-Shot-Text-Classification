---
description: "Executable tasks for feature 005 deployment, CI, and developer documentation"
---

# Tasks: Deployment, CI, and Developer Documentation

**Input**: Design documents in `specs/005-deployment-ci-documentation/`.

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [deployment contracts](contracts/deployment.md), and [quickstart.md](quickstart.md). Follow [the constitution](../../.specify/memory/constitution.md).

**Tests**: Explicitly required by FR-009, FR-012, FR-015 through FR-020, FR-025, and the acceptance scenarios. Reuse existing unit, smoke, concurrency, and prediction integration coverage; add focused tests only for new deployment/probe/CI behavior.

**Organization**: Setup and foundation, one phase for each user story, cross-cutting verification, then convergence remediation. Checkboxes reflect completed work and evidence, not the original task-generation state.

**Regeneration**: Synchronized with the U1/U2 re-plan. Original task IDs T001-T034 are retained; convergence appended T035-T049. Automated service tests use no published host ports and verified owned networks; both image targets use one explicitly filtered root context. No secondary build context or new deployment helper is required.

## Format and Path Conventions

- Every task uses `- [ ] Tnnn [P?] [USn?] Description with exact file paths`.
- `[P]` means different output files and no dependency on unfinished work **once its listed prerequisites are complete**. It does not waive phase gates or permit simultaneous edits of the same file.
- Repository paths below use `/` for documentation references; execute host commands using PowerShell/backslash paths and container commands using Linux paths, as specified in quickstart.md.
- Do not replace the existing application stack, schema, management flows, bucket default, or configuration loaders. Do not add a second lockfile/configuration system or silently re-resolve runtime dependencies.
- Native Windows/Docker data separation remains an **autonomous default, not a user-confirmed decision**. No live cross-environment sharing, automatic migration, multi-host, or network-filesystem guarantees.
- Checks involving real Docker, a permitted external AIStor license, or intentional full-model downloads need those prerequisites. Record unmet prerequisites explicitly; never mark unrun checks as passed or turn executed failures into skips.

## Phase 1: Setup (Shared Infrastructure)

**Original implementation status**: 49/49 original tasks completed. T017/T038/T041/T045 have
actual full-model/browser classification, cold offline ready-model reuse and
exact persistent-state comparison through normal loopback deployment lifecycle
commands. The supplied license and generated temporary credentials were used
only with fresh owned resources; no operator service or credentials were
borrowed. Full-model scope was an autonomous choice after the scope form was
unanswered, not user-confirmed authorization or reviewer/license-entitlement
certification. T030 is complete after its T017 prerequisite and guide/evidence
reconciliation. T031/T039/T042/T046/T048 now have a separate fresh-context
repository-only reviewer walkthrough with actual model/label preparation,
automatic saved classification, matching-record inspection and exact cleanup.
T032-T034/T040/T043/T047/T049 are complete after final native quality,
Linux offline, container/context/durability and licensed-storage checks plus
requirement/acceptance/constitution reconciliation. Hosted CI remains unrun.
Available automated checks and evidence reconciliation are recorded in
[quickstart.md](quickstart.md#8-failure-matrix-and-evidence-record), but do not
replace those walkthroughs. T024 now has actual isolated service-backed
write/read and cleanup evidence; earlier missing-license skips remain historical.

**Purpose**: Confirm baseline and implementation prerequisites without duplicating working features.

- [X] T001 Inventory the current app/config/model/label/storage boundaries, README, `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`, and existing tests; record baseline commands and unrun/observed status in `specs/005-deployment-ci-documentation/quickstart.md`, preserving feature 001-004 behavior and distinguishing current capabilities from planned files.
- [X] T002 [P] Recheck official AIStor support/licensing and public image/platform metadata, Python/uv identities and CPU-wheel availability; record verified identities, supported Docker/WSL/Linux prerequisites, reviewed CI action commit identities, and any external license limitations in `specs/005-deployment-ci-documentation/research.md`; do not read license contents into reports or substitute archived images.

**Checkpoint**: Baseline and current supported identities are known; external prerequisites are named, not assumed.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared reproducible dependency and sensitive-artifact boundaries.

- [X] T003 Configure an explicit `pytorch-cpu` uv index with a Linux-only torch source marker in `pyproject.toml` and regenerate `uv.lock` through uv; preserve Python `>=3.11`, declared runtime constraints, Windows resolution, Hub 2.x/cache-prune compatibility, and unrelated package identities where possible; verify Python 3.11/3.13 locked resolution without downloading models or creating a platform-specific second lock.
- [X] T004 Extend strict mypy's configured file scope in `pyproject.toml` to include `scripts/check_deployment.py`, retain existing Ruff/pytest configuration and strict settings, and keep runtime versus dev dependency groups separate; do not add new lint/test tooling or relax existing gates.
- [X] T005 [P] Update `.gitignore` to exclude real `.env` files while permitting `.env.example`, licenses, external-secret working directories, downloaded artifacts/caches, runtime catalogs/sidecars and backup/test-runtime artifacts; preserve existing useful exclusions and never untrack/revert unrelated user files.

**Checkpoint**: T003-T005 must finish before story implementation. Secrets/runtime artifacts cannot become accidental deliverables; the universal dependency workflow is retained.

## Phase 3: User Story 1 - Run the platform locally (Priority: P1, MVP)

**Goal**: A reproducible, loopback-only deployment with independently startable app, licensed storage, safe diagnostics, and durable data.

**Independent Test**: With supported Docker and external authorized credentials/license, start the deployment, prepare one model and label set through existing UI workflows, submit non-sensitive text once, observe automatic completion, inspect one matching complete prediction, and verify model/cache/label/sidecar/object preservation through stop/start/recreation. Independently start app without storage prerequisites and exercise safe failure/uncertainty cases.

### Tests for User Story 1

Author these focused tests before the corresponding implementation; demonstrate the missing behavior fails when prerequisites are available. A prerequisite skip is not a failing-behavior reproduction or passing coverage.

- [X] T006 [P] [US1] Add parametrized CLI contract/failure tests in `tests/unit/test_deployment_checks.py` for missing/unreadable/directory file inputs, safe output/exit codes, bounded app/node health, TLS/transport/configuration/rejection errors, explicit bucket rejection, and storage probe acknowledgement/readback/uncertainty/cleanup; use lightweight client/HTTP fixtures with zero model-service traffic, generate sentinel secret/path/payload values at test execution rather than embedding secret-like constants in source/images, and assert captured output does not disclose them.
- [X] T007 [P] [US1] Add opt-in container tests and the shared isolation fixture in `tests/integration/test_deployment.py`, including `test_isolated_prediction_storage`, with "`1` explicitly enables container lifecycle validation" via `RUN_DEPLOYMENT_TESTS`. Allocate UUID-scoped project/container/image/bucket identities; choose only the app base or base-plus-MinIO files needed for the case, control subprocess environment/env-file inputs to prevent accidental operator configuration inheritance, start services with `docker compose run -d --no-deps --use-aliases --name <owned-name>`, and prohibit `--service-ports`/`--publish`. Enforce "Host port bindings must be empty for automated service fixtures; clients use `app:8501`/`minio:9000` only on the owned network." Capture container IDs and verify project labels, actual network ownership and port bindings before probes/writes; mismatch/startup failure must fail without host fallback. Cover app-only startup without secrets, normal configuration's loopback bindings, non-root writability, model-parent locks/label markers and stop/start/owned-container recreation with the same volumes. Inspect the actual filtered context using a disposable context/inspection build with execution-generated forbidden sentinels, including an unlisted file under `tests/`, then inspect runtime/validation images separately. The storage case executes the existing `tests/integration/test_prediction_storage.py` inside validation on the verified network and requires the complete-record testcase actually passed, not merely a zero exit with skipped tests. Missing external prerequisites are named skips before execution; configured-invalid/executed failures fail. Clean only captured owned resources; no model downloads or unrelated service stops.

### Implementation for User Story 1

- [X] T008 [P] [US1] Implement typed `preflight` and `health --component app|minio` commands in `scripts/check_deployment.py` using the deployment contract: license input is an "existing readable regular file", root inputs are "external regular files; service receives `/run/secrets/...` paths, not host paths", and "Server root secret files must contain only their credential value, without extra whitespace/newlines"; validate without disclosing contents/paths or claiming license authenticity, use bounded no-retry HTTP/HTTPS health requests, and distinguish node health from S3 permission.
- [X] T009 [US1] Implement `storage --write-probe` and safe structured readiness results in `scripts/check_deployment.py`, reusing `load_minio_settings` and `create_minio_client`: outcomes are "`ready`, `unavailable`, `configuration_error`, `rejected`, `indeterminate`, `cleanup_failed`"; "Storage `ready` requires acknowledged PUT, exact readback, and successful owned-key cleanup." Allocate a UUID `healthchecks/<probe_id>.json`, use fixed non-sensitive content, preserve the exact bucket, perform one no-retry PUT, read at most expected length plus one byte and release responses, delete only the acknowledged exact key, retain original read/cleanup errors, and never DELETE/retry an indeterminate PUT. Emit contract JSON/exit codes with safe next actions, no raw exceptions or secret values; ambiguous access denial must not be mislabeled as a proven license cause.
- [X] T010 [P] [US1] Create app-only `compose.yaml` with service `app`, `127.0.0.1:8501:8501`, `app-runtime:/runtime`, no storage health dependency or server-file interpolation, and existing app environment names; preserve "optional for shell; required and validated on storage use" credentials, "scheme-free host:port; container `minio:9000`, native `localhost:9000`", "explicit Boolean; false only for local HTTP, true for TLS", and "exact `zeroshot_learning_output`; rejected names need explicit override". Set `MODEL_DIR=/runtime/models`, `HF_HOME=/runtime/hf-home`, `TRANSFORMERS_CACHE=/runtime/hub-cache`, `HF_HUB_CACHE=/runtime/hf-home/hub`, `XDG_CACHE_HOME=/runtime/xdg-cache`, and `LABEL_CONFIG_FILE=/runtime/labels/catalog.yaml`; keep library settings separate from app YAML keys and native runtime paths.
- [X] T011 [US1] Create `compose.minio.yaml` using the supported immutable AIStor image/platform from `research.md`, loopback API 9000/Console 9001, `minio-data:/mnt/data`, and `minio server /mnt/data --license /minio.license --console-address :9001`; use a read-only license bind with `create_host_path: false`, externally sourced file secrets and server `_FILE` container paths, fail on missing required inputs rather than default root credentials, and never automatically copy root secrets into app environment.
- [X] T012 [P] [US1] Create one root deny-by-default `.dockerignore` source allowlist for both Dockerfile targets, implementing "one filtered context; approved non-sensitive Python test source copied only into validation target". Allow only required directory ancestors and explicitly reviewed app/test Python file paths, manifests, selected non-secret configuration, Dockerfile and diagnostic tooling; do not broadly admit `tests/` or unlisted files. Keep bytecode/caches, catalogs/sidecars, models, `.env` files, credentials/licenses, logs, backups and specs excluded after allow rules, even inside permitted ancestors. New source entries require review; no secondary context/filter/staging helper is introduced. Verify this policy through T007's actual filtered-context inspection, not runtime COPY output alone.
- [X] T013 [P] [US1] Create `.env.example` with non-secret deployment/file-path placeholders, explicit host versus container endpoint explanations and an optional valid test-bucket override; preserve "existing explicit-path/YAML validation" for `APP_CONFIG_FILE`, "existing non-empty value rule" for `APP_VERSION`, "optional secret; absent from image/logs" for `HF_TOKEN`, and "Empty explicitly provided values do not silently fall through to YAML/defaults." Clearly distinguish app credentials from server file settings; include no usable credentials, license material or automatic bucket rename.
- [X] T014 [US1] Create `Dockerfile` runtime and validation targets using verified pinned Python/uv identities, Linux amd64, CA certificates, a non-root app user and owned `/runtime` subdirectories; install runtime dependencies locked without dev groups/build secrets/model downloads or startup resolution and configure headless Streamlit/container bind/telemetry. Both targets use the same root context filtered by `.dockerignore`; runtime COPY inputs include only app/config/manifest/diagnostic files and no tests, while validation copies approved tests from that filtered context and installs locked dev tools. Do not use an additional build context. Verify actual volume ownership, approved-test availability only in validation, forbidden-sentinel absence and tiny CPU inference/imports; do not infer compatibility or context exclusion from metadata/final COPY selection alone.
- [X] T015 [US1] Run the new CLI/unit and eligible container tests in `tests/unit/test_deployment_checks.py` and `tests/integration/test_deployment.py` with existing model/label/classification smoke/concurrency regressions; verify no-port fixture ownership and internal routing, actual filtered-context and both-image exclusions, safe timeouts/rejection/uncertainty, initialized-catalog loss recovery, interrupted-artifact preservation and zero unrelated cleanup. Exercise owned-container recreation separately from the normal deployment's publication assertions, fix only coupled regressions, and record executed/blocked outcomes plus tested runtime versions in `specs/005-deployment-ci-documentation/quickstart.md`.
- [X] T016 [US1] Turn `specs/005-deployment-ci-documentation/quickstart.md` into a runnable local validation guide with verified PowerShell/container single-context build/run/probe/stop/start/recreate commands, external credential/license provisioning and environment-recreation guidance. Document the preferred port-independent local storage command using `tests/integration/test_deployment.py -k isolated_prediction_storage`, and distinguish the optional direct host integration command as explicitly authorized, never an automatic fallback. Add copyable quiesced whole-volume backup/restore commands using a pinned verified utility image, exact resolved volume identities/ownership checks and operator-controlled native/container transfer preserving provenance/initialization evidence. Keep destructive reset separately warned/inventoried and never routine; do not promise live backups, shared cross-platform locks, session recovery or retry based on restart/time alone.
- [X] T017 [US1] Execute the licensed full-model/UI and durability walkthrough from `specs/005-deployment-ci-documentation/quickstart.md` in an authorized local environment with the normal local ports available; report/defer conflicts rather than stopping an unrelated server or silently changing addresses. Prepare model/labels intentionally, observe automatic saved outcome after one submission, privately compare the complete record/request ID, and verify ready-model reuse and all cache/lock/marker/object data across actual documented `up --force-recreate`, stop/start and `down`-without-volume-deletion operations. Exercise/defer uncertainty recovery safely. Record non-sensitive identities/results only; missing prerequisites remain pending evidence, not successful classification, accessibility or participant-usability coverage.

**Checkpoint**: US1 is the MVP. Independent shell startup and fast automated checks can be validated without a license; a completed licensed-classification/persistence walkthrough still needs actual external prerequisites.

## Phase 4: User Story 2 - Validate changes automatically (Priority: P1)

**Goal**: Preserve quality gates, execute concurrency/image checks, and run isolated real persistence whenever runtime/licensing permits, without hiding failures.

**Independent Test**: Observe all required gate results and representative failing jobs; run complete-record write/read against the selected isolated licensed service with unrelated sentinels preserved, or inspect an explicit prerequisite-based skip and reproducible local alternative. An available/configured-invalid service failure must fail.

### Tests for User Story 2

- [X] T018 [P] [US2] Extend `tests/unit/test_deployment_checks.py` with execution-based fixtures for the actual CI eligibility/run-command behavior defined in `.github/workflows/ci.yml`: absent/unavailable external prerequisites produce a named pre-execution skip, supplied-invalid license/service and executed test failures remain nonzero, each required lint/format/type/test command preserves failure, and sentinel secrets are absent from captured output. Exercise real command branches with disposable stubs/fixtures rather than tests that only restate workflow strings; explicitly scope Linux shell-dependent fixtures to supported runners.
- [X] T019 [P] [US2] Extend only directly needed isolation/cleanup coverage in `tests/integration/test_prediction_storage.py`, reusing its complete-record write/read and UUID key rather than duplicating the schema: `MINIO_TEST_BUCKET` is "explicit opt-in; isolated valid bucket identity", unrelated non-sensitive sentinel objects remain untouched, only acknowledged test-owned keys are removed, and existing buckets are never deleted. Preserve a missing-opt-in skip versus supplied-configuration failure and no model inference/download.

### Implementation for User Story 2

- [X] T020 [US2] Extend the existing quality job in `.github/workflows/ci.yml` with reviewed immutable action identities, a supported recorded runner, fixed uv 0.13.5 and locked install; retain existing lint/format/strict mypy/unit/smoke behavior, add script type-check scope and both `tests/integration/test_classification_concurrency.py` and `tests/integration/test_label_concurrency.py`, and ensure each required nonzero result fails the job without `continue-on-error`, success fallbacks or external model calls.
- [X] T021 [US2] Add license-independent runtime/validation image and app-only/layout/context checks to `.github/workflows/ci.yml` using `Dockerfile` and `tests/integration/test_deployment.py`; build both targets from the one root allowlist with no additional context, enable `RUN_DEPLOYMENT_TESTS=1`, select license-independent cases separately from `isolated_prediction_storage`, and run lightweight CPU/import/ownership/persistence, direct context-exclusion and both-image checks on supported Linux amd64. Reuse T007's no-port verified-network fixture; do not bind default host ports or claim these checks are licensed-service/full-model coverage.
- [X] T022 [US2] Add isolated service-backed validation to `.github/workflows/ci.yml` by invoking the shared `tests/integration/test_deployment.py -k isolated_prediction_storage` fixture, which uses `compose.yaml`/`compose.minio.yaml` to start owned no-port services and executes the existing `tests/integration/test_prediction_storage.py` inside validation on its verified network. Decide eligibility before execution from permitted runtime/license provisioning, protect untrusted fork secrets, generate masked test-only credentials/files outside source, and explicitly scope all settings rather than inheriting the operator's endpoint/env-file/credentials. Require verified project/network/container ownership, empty host port bindings and an actually passed complete-record inner testcase; a zero exit containing a skipped inner test is not integration evidence. Safely clean only this run's captured resources. Enforce "skip requires an identified missing external prerequisite before execution; configured-invalid prerequisites or executed failures are failures" and "Required failed checks propagate nonzero exit." Emit the specific skip/local fixture command when ineligible; no localhost fallback, legacy server, blind write retry or conversion of executed failures to skips.
- [X] T023 [US2] Demonstrate representative lint, formatting, strict type and test failures using temporary fixtures with the commands/jobs in `.github/workflows/ci.yml` and `tests/unit/test_deployment_checks.py`; restore/remove only owned fixtures, never commit deliberately broken source, and record actual failed-job evidence in `specs/005-deployment-ci-documentation/quickstart.md`. Distinguish local command exit verification from unrun hosted-job verification when provider access is unavailable.
- [X] T024 [US2] Run eligible isolated prediction integration and CI eligibility/cleanup branches from `.github/workflows/ci.yml` through `tests/integration/test_deployment.py:test_isolated_prediction_storage`; inspect owned-network/empty-port evidence and the actual executed result of the existing `tests/integration/test_prediction_storage.py`, confirm the selected AIStor/client/license combination writes/reads the complete record and leaves unrelated sentinel objects/buckets intact, and record identities/cleanup outcomes or exact missing-prerequisite reason plus the port-independent local command in `specs/005-deployment-ci-documentation/quickstart.md`; "Mock checks cannot be labeled service-backed."
- [X] T025 [US2] Run the extended required gates and container checks in `.github/workflows/ci.yml`, verify all results are visible, scan representative captured logs/artifacts/images for test sentinel credentials/license contents/sensitive payloads without publishing their values, and record safe pass/fail/skip evidence in `specs/005-deployment-ci-documentation/quickstart.md`; required failed checks remain failures and unrun hosted/service/accessibility checks remain explicitly unverified.

**Checkpoint**: US2 is independently measurable by its gate results, failure propagation and actual eligible integration/explicit ineligibility. It depends on US1's packaging/service interfaces, not the full-model browser walkthrough.

## Phase 5: User Story 3 - Understand and operate the project (Priority: P2)

**Goal**: A new developer can configure, run, inspect, stop, troubleshoot and understand the project using the repository alone.

**Independent Test**: A reviewer follows README from a clean supported environment with stated external prerequisites, reaches one completed saved classification, finds safe next actions for every documented setup failure, and locates all FR-021 through FR-025 topics and truthful validation outcomes.

### Validation Criteria for User Story 3

- [X] T026 [US3] Add a repository-only reviewer scenario/topic matrix to `specs/005-deployment-ci-documentation/quickstart.md`, covering all FR-021 through FR-025 topics, actual executable commands, clean setup/sample classification and common failure recovery; baseline-review the current README to identify missing guidance before expanding it, and define evidence fields for command, environment/identity, expected result, observed pass/fail/unrun or explicit prerequisite skip, with no payload/secret reporting.

### Implementation for User Story 3

- [X] T027 [P] [US3] Expand `README.md` without discarding useful existing guidance: purpose, actual directory structure and roles of `app/streamlit_app.py`, config loaders, pages, model/label managers, adapters, inference/classification coordinator and prediction store; explain supported model identifiers/revisions/provenance, local PyTorch preparation/cache cleanup/deletion and locking, label initialization/validation, automatic classification refresh and the complete existing `predictions/<UUID>.json` schema; link earlier feature quickstarts instead of duplicating conflicting workflows.
- [X] T028 [US3] Add complete native Windows and supported Compose prerequisites/configuration/run/test sections to `README.md`, covering every deployment/data-model variable and environment > YAML > default precedence, independent label resolver, library versus project cache settings, required non-empty/explicit values, app/server secret-variable distinction, external file/license acquisition/registration/support limits, API versus Console/internal DNS and HTTP/TLS, explicit valid bucket override and app recreation after environment changes; provide copyable shell-correct commands without credentials or license contents.
- [X] T029 [US3] Add the complete lifecycle/troubleshooting/privacy guide to `README.md`: absent Docker/server, occupied ports, unwritable/full storage, directory/missing/invalid license, denied operations despite healthy ports, wrong endpoint/TLS, missing/stale process environment, credential/bucket/permission rejection, background status and confirmed/uncertain writes. Require request-key inspection and definitive absence plus non-completion before retry; document durable locations/parent locks/label markers, non-destructive stops/recreation, quiesced backups/restores/transfers, sensitive input/record retention and authorized inspection, least privilege/TLS, trusted-local/navigation limits and separately warned destructive reset; never prescribe blind retry, routine volume deletion or live sharing.
- [X] T030 [P] [US3] Reconcile implemented single-context build commands, normal host versus internal no-port test endpoints, unit/smoke/concurrency/container selectors and the shared `isolated_prediction_storage` local/CI alternative in `specs/005-deployment-ci-documentation/quickstart.md`; identify direct host-server testing as explicitly authorized only, link the canonical README and relevant feature 001-004 guides, and replace design-only wording only for actually delivered capabilities. Preserve unrun integration/accessibility/participant-usability limitations and the recorded autonomous separation default.
- [X] T031 [US3] Perform the repository-only clean README walkthrough and safe diagnostic/topic review using `README.md` and `specs/005-deployment-ci-documentation/quickstart.md`; account for every FR-021 through FR-025 topic and every executable validation example, privately verify one saved non-sensitive request and corrective next actions using authorized isolated fixtures/services, fix contradictory/copy-invalid guidance, and record reviewer evidence or explicit unmet prerequisites without claiming unrun participant/screen-reader checks passed.

**Checkpoint**: US3 supplies a complete entry point and honest operating evidence. Drafting can proceed independently, but the final walkthrough needs the actual US1 deployment and US2 commands/outcomes.

## Phase 6: Polish and Cross-Cutting Verification

**Purpose**: Verify the completed feature against the constitution and measurable acceptance criteria without unrelated refactoring.

- [X] T032 Run the final combined Ruff lint/format, strict mypy, deterministic unit/smoke/concurrency and eligible deployment/prediction tests specified by `pyproject.toml`, `.github/workflows/ci.yml` and `specs/005-deployment-ci-documentation/quickstart.md`; fix only feature-coupled regressions, verify no ordinary test downloads models, and record remaining external prerequisites without treating required failures as passes.
- [X] T033 Reconcile task completion and actual evidence in `specs/005-deployment-ci-documentation/tasks.md` and `specs/005-deployment-ci-documentation/quickstart.md` against every FR-001 through FR-025, all 13 story acceptance scenarios and SC-001 through SC-008; preserve pending blocked walkthrough/hosted evidence, mark allowed integration skips with exact reasons/local alternatives, and recheck all ten constitution gates without claiming designed coverage is executed coverage.
- [X] T034 Inspect the feature-scoped final diff for secrets/licenses/data, immutable identities, safe diagnostics, unchanged app/prediction/model/label contracts and zero unrelated destructive cleanup; validate links/commands against `README.md`, `.env.example`, `Dockerfile`, `compose.yaml`, `compose.minio.yaml` and `specs/005-deployment-ci-documentation/quickstart.md`, record the safe final review there, and stop/remove only specifically owned disposable helpers while preserving local/user volumes and unrelated worktree changes.

## Dependencies and Execution Order

### Phase and Story Graph

```text
Setup: T001 + T002
        |
Foundation: T003 -> T004, with independent T005
        |
        +--> US1 contract tests -> CLI/Compose/context/image -> local validation -> MVP
        |
        +--> US2 CI/test drafts -> needs US1 packaging/service interfaces -> CI validation
        |
        +--> US3 topic/content drafts -> needs US1/US2 guide/evidence -> reviewer validation
                                                                        |
                                                all stories -> T032 -> T033 -> T034
```

- Setup gates foundation. All story tasks wait for T003-T005.
- Stories are listed in priority order, not assumed to be independent of components they actually consume.
- US2 may draft CI tests/gates early; its image/service execution waits for the listed US1 tasks. It does not wait for T017.
- US3 can prepare content early; reviewer criteria/final guide/walkthrough wait for runnable instructions and evidence. Its final walkthrough is distinct from feature 004 participant usability.
- A single implementer should follow phase order. Multiple implementers use the ready-task prerequisites below and serialize every shared file, especially `pyproject.toml`, the CLI, CI workflow, README, and quickstart.

### Exact Additional Prerequisites

All Phase 2 tasks depend on T001 and T002; all story tasks also depend on the foundation checkpoint. Listed prerequisites are completion gates, not a requirement that every earlier task number be complete.

| Task | Additional prerequisite IDs |
|---|---|
| T001, T002 | none |
| T003, T005 | setup checkpoint only |
| T004 | T003 |
| T006, T007 | foundation checkpoint only |
| T008 | T006 |
| T009 | T006, T008 |
| T010 | T007 |
| T011 | T007, T010 |
| T012, T013 | T007 |
| T014 | T009, T012 |
| T015 | T006, T007, T009, T010, T011, T013, T014 |
| T016 | T015 |
| T017 | T016 |
| T018 | T006; serialize the shared unit test file |
| T019 | foundation checkpoint only |
| T020 | T018, T019 |
| T021 | T007, T010, T014, T020 |
| T022 | T007, T009, T011, T013, T019, T021 |
| T023 | T018, T020, T021, T022 |
| T024 | T007, T019, T022, T023 |
| T025 | T015, T020, T021, T022, T023, T024 |
| T026 | T016, T024 |
| T027 | T026 |
| T028 | T013, T027 |
| T029 | T016, T028 |
| T030 | T017, T025, T026 |
| T031 | T017, T025, T029, T030 |
| T032 | T017, T025, T031 |
| T033 | T032 |
| T034 | T033 |

External runtime/license/reviewer prerequisites are recorded separately from code dependencies. Required evidence that cannot be obtained remains pending; only integration prerequisites explicitly covered by FR-018 may produce that documented skip.

## Parallel Execution Examples

These are scheduling examples, not instructions to launch agents automatically. Each wave starts only after its stated prerequisite gate.

### Shared Work

- After setup: T003 (`pyproject.toml`, `uv.lock`) can run with T005 (`.gitignore`); T004 follows T003.
- T001 (quickstart baseline) and T002 (research identities) use different output files.

### User Story 1

```text
After foundation:
  T006: tests/unit/test_deployment_checks.py
  T007: tests/integration/test_deployment.py no-port/context inspection fixture and cases

After the relevant contract tests are authored:
  T008: scripts/check_deployment.py preflight/health
  T010: compose.yaml
  T012: .dockerignore single root source allowlist
  T013: .env.example
```

T009 follows T008 in the same script; T011 follows T010 for the overlay; T014 waits for CLI/context/locked dependencies. Do not run image validations before their inputs exist.

### User Story 2

```text
After foundation and US1's T006, with no other unit-test-file writer:
  T018: tests/unit/test_deployment_checks.py CI execution fixtures
  T019: tests/integration/test_prediction_storage.py isolation coverage
```

T020-T022 all edit the CI workflow and must be serialized. T021/T022 reuse T007's fixture; service checks run inside its verified no-port network, never the local developer deployment. No additional build context is supplied.

### User Story 3

```text
After T026 and the listed implementation/evidence prerequisites:
  T027: README.md architecture/model/label/record content
  T030: specs/005-deployment-ci-documentation/quickstart.md runnable guide reconciliation
```

T028 and T029 extend the same README after T027; T031 waits for the completed README and quickstart. Never parallelize quickstart edits with unfinished US1/US2 evidence writers.

## Requirement and Evidence Coverage

| Requirement | Main implementation/verification tasks |
|---|---|
| FR-001 | T007, T010, T011, T014, T017 |
| FR-002 | T002, T003, T004, T014, T015, T020 |
| FR-003 | T002, T008, T011, T017, T022, T028 |
| FR-004 | T005, T006, T007, T012, T013, T014, T025, T034 |
| FR-005 | T010, T013, T016, T028 |
| FR-006 | T007, T010, T011, T029 |
| FR-007 | T007, T010, T011, T014, T016, T017 |
| FR-008 | T007, T010, T015, T016, T029 |
| FR-009 | T006, T008, T009, T015, T029 |
| FR-010 | T007, T010, T015 |
| FR-011 | T006, T009, T010, T013, T028 |
| FR-012 | T015, T017, T027 |
| FR-013 | T007, T016, T017, T029, T034 |
| FR-014 | T006, T009, T016, T017, T029 |
| FR-015 | T004, T015, T020, T025, T032 |
| FR-016 | T002, T003, T006, T014, T020, T025, T032 |
| FR-017 | T019, T022, T024 |
| FR-018 | T018, T022, T024, T030 |
| FR-019 | T007, T009, T019, T022, T024, T034 |
| FR-020 | T018, T020, T021, T022, T023, T025 |
| FR-021 | T026, T027, T028, T031 |
| FR-022 | T016, T028, T030, T031 |
| FR-023 | T006, T008, T009, T029, T031 |
| FR-024 | T016, T027, T029, T031, T034 |
| FR-025 | T023, T024, T025, T026, T030, T031, T033 |

| Acceptance scenarios / success criteria | Required evidence tasks |
|---|---|
| US1/AC1, US3/AC1, SC-001 | T016, T017, T031 |
| US1/AC2, SC-002 | T015, T017, T031 |
| US1/AC3, SC-003 | T007, T015, T017 |
| US1/AC4, US3/AC2, SC-004 | T006, T008, T009, T015, T029, T031 |
| US1/AC5 | T007, T010, T015 |
| US1/AC6 | T006, T009, T016, T017, T029 |
| US2/AC1-2, SC-005 | T018, T020, T023, T025 |
| US2/AC3-4, SC-006 | T019, T022, T024 |
| US2/AC3, SC-007 | T007, T019, T024, T025, T034 |
| US3/AC3, SC-008 | T026, T027, T028, T029, T030, T031, T033 |

## Implementation Strategy

### MVP First

1. Finish setup and foundation.
2. Implement and validate US1's fast contract/container checks and independently usable shell.
3. Supply authorized external licensing and intentionally prepare a model for T017.
4. Stop at the US1 checkpoint to validate one automatic completed result, one matching record, safe failures, and non-destructive persistence. Do not call the full MVP verified while its licensed walkthrough is unrun.

### Incremental Delivery

1. Add US1 without changing existing model/label/inference/storage semantics.
2. Add US2's preserved/extended gates and isolated eligible integration, with honest skips only for specified external prerequisites.
3. Add US3's complete README and repository-only reviewer evidence.
4. Finish T032-T034; do not chase unrelated refactors, add new management workflows, expose services publicly, or delete user data.

### Completion Rules

- Check a task off only when its specific work/evidence is complete. Distinguish authored tests from passed tests, command execution from hosted-job evidence, and intentional prerequisite skips from failed execution.
- Keep full model downloads out of ordinary unit/smoke/concurrency/CI packaging checks.
- Task generation completed the U1/U2 handoff recorded during re-planning. Retain no-port verified-network fixtures, one filtered root context, direct context inspection and shared local/CI storage validation. Only the recorded executed checks establish runtime evidence; pending walkthroughs remain unverified.
- Store safe validation identities/outcomes, not credentials, licenses, raw text or prediction payloads.
- No automatic commit is required by this task list. Preserve the user's unrelated worktree changes; optional extension commits remain optional.
- Current count: **49 tasks**: setup 2, foundation 3, US1 12, US2 8, US3 6, polish 3, convergence 15. Twelve original tasks have `[P]` markers, subject to the explicit prerequisites and file ownership rules above.

## Phase 7: Convergence

- [X] T035 CRITICAL - Prevent disclosure of test-generated credentials through deployment failure reports in `tests/integration/test_deployment.py` and directly dependent CI reporting. `docker` and `run_owned` currently receive ordinary credential-bearing environment dictionaries; suppressing command output does not redact pytest's argument/local-variable rendering. An in-memory helper failure reproduced credential disclosure with locals enabled, without contacting Docker or printing sentinel values. Protect credential-bearing representations and relevant failure boundaries, including caller frames, while retaining non-sensitive actionable errors; cover default and verbose/locals-enabled pytest reports and any emitted artifacts with execution-generated sentinels. Do not rely on truncation or masking only the externally supplied license, and do not solve disclosure by hiding every failure reason. Record safe outcomes in `specs/005-deployment-ci-documentation/quickstart.md` per Constitution 10, FR-004, FR-016, SC-007 and T007/T018/T022/T025 (contradicts).
- [X] T036 Correct post-PUT S3 failure classification in `scripts/check_deployment.py` and add focused cases to `tests/unit/test_deployment_checks.py`: an XML `S3Error` with HTTP 500 currently returns `rejected`/`s3_rejected`, although it does not establish that the write failed. Use response evidence to distinguish authoritative write rejection from indeterminate server/unknown-status failures, consistently with the existing prediction-storage boundary. For uncertain outcomes retain the exact probe ID/key and require authorized inspection plus definitive absence and non-completion before retry or deletion; never retry the PUT or clean an unacknowledged object. Preserve safe 4xx credential/bucket rejection behavior and acknowledged readback/cleanup semantics; verify SDK response bodies/messages stay out of output per FR-009, FR-014, plan: readiness and lifecycle, and T009/T015 (contradicts).
- [X] T037 Restore useful non-sensitive failure diagnostics for Docker build/start operations and nested validation in `tests/integration/test_deployment.py`, after T035. The current generic exit-code assertions discard the failing nested testcase/gate identity and safe service-check reason, so required jobs can fail without enough information to identify the regression. Return or retain a narrowly allowlisted summary of operation, gate/test identity, exit category and corrective action; do not dump raw Docker output, subprocess environments, payloads, license contents or unsanitized tracebacks. Exercise representative image/helper/nested-test failures and cleanup failures, asserting both nonzero propagation and absence of generated sensitive sentinels; record local execution separately from unrun hosted jobs in `specs/005-deployment-ci-documentation/quickstart.md` per FR-020, SC-005, plan: CI and tests, and T023/T025 (partial).
- [X] T038 Complete the remaining T017 licensed local deployment/full-model evidence using `README.md` and `specs/005-deployment-ci-documentation/quickstart.md` after T035-T037. Require explicitly supplied licensing authorized for the compute resource, external credentials, available normal loopback ports and intentional model preparation; do not inspect operator containers for secrets, borrow an existing service implicitly, or stop unrelated services. Observe one automatic completed saved outcome, privately verify exactly one matching complete prediction/request ID, and verify ready-model reuse plus model provenance, all configured caches, labels/initialization/coordination sidecars and prediction preservation across the documented stop/start, force-recreation and non-volume-deleting down/up commands. Exercise authorized safe failure/recovery cases and record tested image/client identities and cleanup results without payloads; separately record any still-unrun real-data backup/restore or transfer checks. If prerequisites remain unavailable, leave this task and T017 pending with the exact prerequisite rather than treating lightweight fixtures or a permitted integration skip as the full walkthrough per FR-001, FR-003, FR-007, FR-012, FR-013, US1/AC1-6, SC-001 through SC-004 and T017 (partial).
- [X] T039 Complete the T031 repository-only README reviewer walkthrough after T038, using only `README.md`, linked repository guides and stated external prerequisites. Account for all FR-021 through FR-025 topics and executable examples; verify clean setup, model/label preparation, one saved request and safe corrective actions for the documented setup/uncertainty matrix. Fix contradictions or copy-invalid guidance and record command, environment/image identity, expected/observed outcome, cleanup and unmet prerequisites in `specs/005-deployment-ci-documentation/quickstart.md`. Distinguish this reviewer evidence from participant/accessibility checks and hosted CI; if the licensed walkthrough or reviewer is unavailable, retain explicit pending status instead of inferred success per US3/AC1-3, SC-001, SC-004, SC-008 and T026/T031 (partial).
- [X] T040 Close the remaining final dependency/evidence gates T032-T034 after T035-T039, rerunning the combined Ruff lint/format, strict mypy, deterministic unit/smoke/concurrency and eligible container/storage checks and inspecting the resulting feature-scoped deliverables. Reconcile all 25 FRs, 13 acceptance scenarios, eight success criteria and ten constitution principles against actual outcomes in `specs/005-deployment-ci-documentation/quickstart.md` and task completion in this file. Resolve T030's checked status against its explicitly listed pending T017 prerequisite without treating an earlier documentation draft as completed walkthrough evidence; retain any blocked original or convergence tasks until their actual obligations are met. Preserve the permitted missing-license integration skip/local alternative, distinguish local checks from hosted-job execution, revalidate documentation commands/links and sentinel exclusion, and clean only exact owned disposable resources. Do not claim feature convergence while T017/T031 or their required evidence remains pending per FR-025, SC-005 through SC-008, plan: requirement and acceptance traceability, and T030/T032-T034 (partial).

## Phase 8: Convergence

This reassessment found no additional code contradiction in scope. T035-T037's resulting behavior was inspected and nine read-only in-memory uncertainty/diagnostic/cleanup checks passed. The three remaining findings continue the pending evidence chains below, rather than replacing their earlier tasks. This phase supersedes earlier task-count snapshots: **43 tasks, 31 checked and 12 pending**. Missing authorized external prerequisites remain blockers, not permission to substitute mocks, borrow an operator's service or claim completion.

**Supplied-license follow-up**: The isolated complete-record test passed, then passed again with the app durability regression (2 passed, 2 deselected). The first attempt exposed the image's anonymous `/data` volume; the fixture now distinguishes engine-created anonymous volumes from unowned explicit mounts and uses owned-container anonymous-volume cleanup. Two focused regressions pass; the 51-case diagnostic/reporting unit selector passed with four Linux-only skips. Captured container-mount events confirmed all six MinIO test volumes from three attempts were removed, including the first failed attempt's exact two volumes. This is actual local service-backed coverage, not the full-model/UI or reviewer walkthrough. No further task is checked off solely for this subset.

- [X] T041 Complete the still-unrun T017/T038 licensed local deployment walkthrough using `README.md` and `specs/005-deployment-ci-documentation/quickstart.md`. Require an explicitly supplied AIStor license authorized for this compute resource, external credentials, available documented loopback ports and intentional full-model preparation; the supplied license has now passed isolated storage validation, but the broader walkthrough remains unrun. Observe automatic saved completion from one submission, privately verify exactly one complete matching prediction record, and verify ready-model reuse, provenance, all configured caches, labels/initialization/coordination sidecars and prediction objects through the actual documented stop/start, force-recreation and non-volume-deleting down/up commands. Exercise safe failure/recovery cases without blind uncertain-write retries, retain only non-sensitive version/request/outcome metadata, and distinguish unrun real-data restore/transfer checks. Mark T017/T038 complete only after their actual evidence exists; otherwise keep this chain pending with exact prerequisites per FR-001, FR-003, FR-007, FR-009, FR-012 through FR-014, US1/AC1-6, SC-001 through SC-004 and T017/T038 (partial).
- [X] T042 After T041 establishes the licensed walkthrough evidence, finish T030's guide/evidence reconciliation and perform the still-unrun T031/T039 repository-only reviewer walkthrough using `README.md` and its linked repository guides. Verify clean setup, model/label preparation, one saved request, authorized record inspection and the documented setup/uncertainty recovery matrix; account for every FR-021 through FR-025 topic and executable example. Record environment/image identity, command, expected/observed result, cleanup and unmet prerequisites in `specs/005-deployment-ci-documentation/quickstart.md`, fixing only contradictory or copy-invalid guidance. Complete T030 before T031 as its existing dependency requires. Do not substitute syntax/link checks, authored documentation, participant/accessibility claims or prior chat knowledge for reviewer evidence; if prerequisites or a reviewer remain unavailable, retain pending status per US3/AC1-3, SC-001, SC-004, SC-008 and T030/T031/T039 (partial).
- [X] T043 After T041-T042 and their existing prerequisite chains are complete, finish T032-T034/T040 by running the final applicable Ruff lint/format, strict mypy, deterministic unit/smoke/concurrency and eligible container/storage checks; inspect the resulting feature-scoped deliverables and update `specs/005-deployment-ci-documentation/quickstart.md` and this task file with actual outcomes. Reconcile all 25 FRs, 13 acceptance scenarios, eight success criteria and ten constitution principles; retain safe failure-report/sentinel exclusion and exact owned-resource cleanup evidence. T030 is already correctly unchecked, so do not treat that resolved bookkeeping discrepancy as a new defect or mark its pending prerequisite satisfied. Preserve the permitted missing-license integration skip/local alternative, separate local execution from unrun hosted/reviewer/accessibility evidence, revalidate links and shell commands, and leave every genuinely blocked gate pending rather than declaring convergence per FR-025, SC-005 through SC-008, plan: requirement and acceptance traceability, and T030/T032-T034/T040 (partial).

## Phase 9: Convergence

The supplied-license storage validation and anonymous-volume cleanup correction are supported by actual passing service tests and inspected behavior. Eleven current read-only in-memory checks also passed. T041-T043 still cover the full-model/UI, reviewer and final-evidence gaps and are not duplicated here. One distinct executable-documentation defect remains: the guide's embedded quoted Docker label key is not preserved by Windows PowerShell 5.1 native argument handling. A read-only Docker inspect reproduction with that quoted key failed with exit 64 and `function "com" not defined`; PowerShell parser success alone did not catch it. This phase supersedes earlier task-count snapshots: **44 tasks, 31 checked and 13 pending**.

- [X] T044 Correct Windows PowerShell native-argument handling in the ownership-check and directly dependent backup/restore commands in `specs/005-deployment-ci-documentation/quickstart.md`, updating linked `README.md` guidance only if needed. The current `docker volume inspect ... --format '{{ index .Labels "com.docker.compose.project" }}'` pattern loses its embedded quotes in Windows PowerShell 5.1. Prefer a simple shell-safe approach such as parsing Docker JSON metadata and then looking up the exact label; do not weaken ownership checks, ignore nonzero exits, print resolved credentials/configuration, or proceed to backup/restore after failed ownership verification. Audit the other documented native-command argument boundaries and execute the corrected copied checks against read-only metadata or exact owned disposable fixtures under Windows PowerShell 5.1 and every additionally claimed/tested shell; record unavailable shell coverage explicitly rather than inferring it from syntax parsing. Verify both matching and mismatched/missing ownership safely, preserve quiesced-writer checks, persistent data and unrelated resources, and record command, shell version, actual result and cleanup in `specs/005-deployment-ci-documentation/quickstart.md`. This correction can proceed independently of full-model preparation, but it does not replace T042's reviewer or T043's final gates per FR-022, FR-025, SC-008, plan: executable PowerShell documentation, and T016/T031/T042 (partial).

**T044 implementation follow-up**: Ten executed Windows PowerShell 5.1 checks
passed, including matching/mismatched/missing and case-sensitive ownership,
native inspection failure, running-writer refusal, and copied backup/restore
commands through a spaced Windows path. Both restored fixture byte hashes,
UIDs/modes and UID-10001 readability matched. All exact disposable volumes,
helpers and archives were removed. PowerShell 7 was unavailable, not inferred
to pass. See [quickstart evidence](quickstart.md#t044-powershell-command-validation-2026-11-15).
This supersedes earlier completion snapshots: **32 checked, 12 pending**.
T041-T043 and their prerequisite chains remain pending; no full-model/UI,
reviewer or final approval is claimed.

## Phase 10: Convergence

The current assessment found no additional implementation contradiction in the
feature scope. Twenty-one read-only in-memory regression calls passed for probe
acknowledgement/uncertainty/cleanup, safe failure diagnostics and anonymous-volume
ownership. These are not new service-backed coverage. The supplied-license
complete-record validation and T044's actual Windows PowerShell command checks
remain supported by their recorded executed evidence and inspected behavior.
Three partial evidence gaps still prevent convergence. The tasks below continue
their existing prerequisite chains; they do not reopen T044, replace earlier
obligations or authorize access to operator resources. This phase supersedes
earlier task-count snapshots: **47 tasks, 32 checked and 15 pending**.

- [X] T045 Complete the remaining T017/T038/T041 full-model/UI and normal deployment durability evidence using `README.md` and `specs/005-deployment-ci-documentation/quickstart.md`. The supplied license already passed isolated complete-record storage validation; do not report licensing as still absent or substitute another isolated storage run for this walkthrough. Establish the stated compute/license authorization, intentional model preparation, external app/server credentials and available documented loopback ports without inspecting operator secrets or stopping unrelated services. Prepare one supported model and valid labels through existing workflows, observe one automatically displayed saved outcome, privately verify exactly one complete matching prediction/request ID, and verify ready-model reuse, provenance, all configured caches, label initialization/coordination evidence, model-parent locks and prediction objects through actual documented stop/start, force-recreation and down/up without volume deletion. Preserve uncertain-write inspection/no-blind-retry rules and native/Docker data separation; distinguish still-unrun real-data restore/transfer checks. Record only non-sensitive commands, identities, outcomes and cleanup in `specs/005-deployment-ci-documentation/quickstart.md`; retain this chain pending when its prerequisites are unavailable per FR-001, FR-003, FR-007, FR-012 through FR-014, US1/AC1-6, SC-001 through SC-004 and T017/T038/T041 (partial).
- [X] T046 After T045 and its earlier walkthrough obligations are complete, finish T030's guide/evidence reconciliation and T031/T039/T042's repository-only reviewer walkthrough using `README.md` and its linked repository guides. Verify clean setup, model/label preparation, one saved request and authorized record inspection, plus safe next actions for the documented setup/uncertainty matrix; account for every FR-021 through FR-025 topic and executable example. Retain T044's verified Windows PowerShell 5.1 backup/restore correction and explicitly untested PowerShell 7/Linux-host coverage, but do not count fixture command checks or syntax/link validation as the reviewer walkthrough. Record environment/image identity, command, expected/observed result, cleanup and unmet prerequisites in `specs/005-deployment-ci-documentation/quickstart.md`; correct only demonstrated contradictory/copy-invalid guidance. Complete T030 before T031 and leave reviewer/participant/accessibility claims unverified unless actually executed per US3/AC1-3, SC-001, SC-004, SC-008 and T030/T031/T039/T042 (partial).
- [X] T047 After T045-T046 and their existing prerequisite chains are complete, close T032-T034/T040/T043 with the final applicable Ruff lint/format, strict mypy, deterministic unit/smoke/concurrency and eligible container/storage checks; inspect the resulting feature-scoped deliverables and reconcile actual outcomes in `specs/005-deployment-ci-documentation/quickstart.md` and task completion in this file. Cover all 25 functional requirements, 13 acceptance scenarios, eight success criteria and ten constitution principles, retaining exact owned-resource cleanup and safe reporting/sentinel exclusion evidence. Preserve T044's actual command results and distinguish local execution, permitted prerequisite skips, executed failures and unrun hosted/reviewer/accessibility checks. Do not waive pending walkthrough dependencies, convert an available-service failure into a skip, or infer convergence from the current 21 in-memory calls or previously passed subsets per FR-025, SC-005 through SC-008, plan: requirement and acceptance traceability, and T032-T034/T040/T043 (partial).

**Full-model implementation follow-up**: T017/T038/T041/T045 passed with the
supplied license, generated external credentials and a fresh owned normal-port
deployment. One full configured model became ready; one browser submission
automatically displayed saved completion and matched one privately inspected
prediction. Exact runtime hashes/UIDs and prediction bytes survived stop/start,
force-recreation and down/up without volume deletion. Cold inference with
network connections forbidden confirmed ready-model reuse. Six actual safe
failure checks passed before PUT; uncertainty, real-data restore and transfer
limits are recorded rather than manufactured. Exact test resources and generated
secrets were cleaned after verification. T030 is reconciled against that evidence.
See [the full-model evidence](quickstart.md#full-model-and-normal-deployment-walkthrough-2026-11-15).
This supersedes prior snapshots: **37 checked, 10 pending**. Separate
repository-only reviewer and dependent final gates remain pending.

## Phase 11: Convergence

The current assessment accepts the recorded and inspected full-model/browser
classification, exact normal deployment lifecycle durability, offline ready-model
reuse, six safe setup-failure checks and exact cleanup as completed operator
validation. T017/T030/T038/T041/T045 are not reopened. Twenty-one current
read-only in-memory regression calls also passed; no new implementation defect
was found. Two partial evidence gaps remain: the separate repository-only
reviewer walkthrough and its dependent final gates. These continuation tasks
retain the earlier obligations rather than treating another storage/model test
or a task checkbox as reviewer evidence. This phase supersedes earlier task-count
snapshots: **49 tasks, 37 checked and 12 pending**.

- [X] T048 Complete the separate T031/T039/T042/T046 repository-only reviewer walkthrough now that T045 and T030 are complete, using `README.md`, its linked repository guides and explicitly stated external prerequisites, without relying on prior chat setup or relabeling the completed operator walkthrough as reviewer evidence. Verify clean supported setup, existing model/label preparation, one automatically displayed saved classification with authorized matching-record inspection, and safe next actions for the documented setup/uncertainty matrix; account for every FR-021 through FR-025 topic and every executable example used in the review. Record command, supported shell/runtime/image identity, expected/observed outcome, prerequisite gaps and exact owned-resource cleanup in `specs/005-deployment-ci-documentation/quickstart.md`, fixing only demonstrated contradictory or copy-invalid guidance in that guide or `README.md`. Preserve T044's actual Windows PowerShell 5.1 evidence, explicit untested-shell limits, autonomous native/Docker data separation and the completed full-model evidence. Do not borrow operator services/secrets, repeat a model download merely to restate existing operator evidence, substitute syntax/link checks for the reviewer walkthrough, or claim participant/accessibility/hosted execution that did not occur. Leave the reviewer chain pending if the review cannot actually be executed per FR-021 through FR-025, US3/AC1-3, SC-001, SC-004, SC-008 and T031/T039/T042/T046 (partial).
- [X] T049 After T048 and its earlier reviewer obligations are complete, finish T032-T034/T040/T043/T047 with the final applicable Ruff lint/format, strict mypy, deterministic unit/smoke/concurrency and eligible container/storage checks, followed by feature-scoped deliverable and evidence reconciliation in `specs/005-deployment-ci-documentation/quickstart.md` and this task file. Map actual outcomes to all 25 functional requirements, 13 acceptance scenarios, eight success criteria and ten constitution principles; retain safe diagnostics/sentinel exclusion and exact owned-resource cleanup evidence, and resolve any directly coupled regression before completion. Preserve the verified full-model/UI, normal lifecycle, offline reuse and PowerShell command results without manufacturing another runtime gap. Distinguish local checks from hosted jobs, missing-prerequisite skips from executed failures, and completed operator evidence from separate reviewer approval; retain explicit unrun physical MinIO restore, real-model transfer, accessibility and participant limits rather than implying those checks passed. Do not waive the pending reviewer prerequisite or declare convergence from the current in-memory calls or previously passed subsets per FR-025, SC-005 through SC-008, plan: requirement and acceptance traceability, and T032-T034/T040/T043/T047 (partial).

**Final implementation follow-up (2026-11-15)**: The separate fresh-context
repository-only reviewer passed actual model/label preparation, one automatic
saved classification and exact private matching-record inspection, then cleaned
its owned resources. Final sequential native gates passed (229 tests, four
Linux-only skips); complete container/licensed-storage gates passed (four tests),
including network-disabled Linux regressions (234 tests, four opt-in skips).
Earlier concurrent Windows readiness failures are recorded, not hidden or
converted to skips. All 25 functional requirements, 13 acceptance scenarios,
eight success criteria and ten constitution principles are reconciled in
[the final evidence](quickstart.md#final-local-gates-and-reconciliation-2026-11-15).
This supersedes historical completion counts: **49 checked, zero pending**.
Hosted CI, accessibility/participants, physical MinIO restore and real-model
transfer remain explicitly unrun, not inferred successes. No application
contract change, commit, push or unrelated destructive cleanup occurred.

## Phase 12: Local launch usability

- [X] T050 Add a Windows PowerShell first-run/full-start, stop, status, explicit readiness check, and app-only launcher that reuses `.env`, preflight, and Compose, preserves existing configuration, prompts for app credentials without saving them, and retains volumes.
- [X] T051 Add launcher regression tests for setup, existing configuration, failure handling, non-destructive lifecycle, app-only startup, and real dotenv/preflight compatibility; update the README and feature guidance with the concise workflow and honest readiness limits.
