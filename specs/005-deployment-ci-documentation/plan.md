# Implementation Plan: Deployment, CI, and Developer Documentation

**Branch**: `005-deployment-ci-documentation` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: `specs/005-deployment-ci-documentation/spec.md`

**Status**: Deployment, CI and documentation implementation delivered. Native
quality gates, Linux offline regression tests and owned-container layout,
filtering, restart/recreation and lightweight backup/restore checks passed.
Licensed full-model/browser classification, cold offline ready-model reuse and
normal loopback deployment lifecycle checks also passed. A separate fresh-context
repository-only reviewer walkthrough passed, including one automatically saved
classification and private matching-record inspection. Final local quality,
container/storage gates and requirement reconciliation passed; all 49 tasks
are complete. Hosted CI has not been run.

**Re-plan**: U1 (test host-port isolation) and U2 (test-source filtering) were
resolved, the tasks subsequently regenerated, and read-only analysis completed
before implementation.

## Summary

Package the existing application for Linux amd64 CPU execution, add an independently startable application Compose file and optional licensed AIStor overlay, extend existing CI, and expand the README. Preserve features 001-004 without new management or inference workflows. Persist one application runtime parent covering model locks, model provenance, caches, and label sidecars; use a separate MinIO data volume.

See [research.md](research.md), [data-model.md](data-model.md), [deployment contract](contracts/deployment.md), and [quickstart.md](quickstart.md).

## Technical Context

**Language/Version**: Preserve Python >=3.11. Container baseline: verified Python 3.13.18 slim-trixie amd64 image; CI now selects Python 3.11 and 3.13.

**Primary Dependencies**: Current lock: Streamlit 1.67.0, Transformers 5.23.0, PyTorch 2.15.0, Hugging Face Hub 2.4.0, MinIO client 7.2.20, filelock 4.2.10, urllib3 2.8.0. Use uv 0.13.5. During implementation add an explicit CPU torch source scoped to Linux and regenerate the universal lock; preserve Windows resolution, declared runtime constraints, Hub 2.x, and the Python floor. No unlocked torch replacement inside the image.

**Storage**: Project-scoped `app-runtime` named volume at `/runtime`, `minio-data` at `/mnt/data`, external read-only license and root-credential files. MinIO remains authoritative for successful predictions.

**Testing**: Existing pytest unit/smoke and cooperating-process concurrency tests, existing opt-in prediction write/read test, focused deployment diagnostics/packaging tests, separate container persistence and browser walkthroughs. Ordinary tests do not download models.

**Target Platform**: Linux amd64 Docker/Compose on Windows Docker Desktop's WSL 2 Linux-container backend and supported Linux amd64 hosts/CI. ARM and native Windows containers are unvalidated; native Windows application use remains separate.

**Project Type**: Existing multipage Streamlit application plus minimal deployment tooling.

**Performance Goals**: No invented throughput, model-download, or inference latency SLA. Diagnostic operations have explicit finite network timeouts.

**Constraints**: Loopback host publication; immutable image identities; external secrets; no build-time models; independent app startup; local cooperating-process locks; no silent bucket changes, automatic uncertain-write retries, or false success.

**Scale/Scope**: One local Compose project and single AIStor compute resource. No auth feature, public hosting, production certification, multi-host coordination, retention management, or prediction history.

## Constitution Check

| Principle | Before research | Post-design |
|---|---|---|
| 1: mandated stack | Pass: existing stack | Pass: Docker supports it; AIStor is MinIO |
| 2: typed reproducible Python | Pass: retain floor/lock | Pass: pinned images, CPU universal lock, Ruff/mypy |
| 3: model reproducibility | Pass: no new inference | Pass: provenance/local loading unchanged; no ordinary test/image downloads |
| 4: modular boundaries | Pass: existing services | Pass: operational CLI reuses loaders/client; no new settings framework |
| 5: Streamlit lifecycle | Pass: preserve state | Pass: timed completion refresh and session identity unchanged |
| 6: external secrets | Pass: none in source | Pass: external secrets and one explicit source-context allowlist; no secondary filtering assumption |
| 7: MinIO persistence | Pass: default/schema retained | Pass: confirmed-write success; no substitute bucket/store |
| 8: safe failure | Pass: trusted local scope | Pass: loopback ports, safe diagnostics, uncertainty/reset warnings |
| 9: quality gates | Pass: extend existing CI | Pass: concurrency, port-independent eligible service tests, explicit prerequisite skips |
| 10: observability/docs | Pass: safe metadata | Pass: complete entry point, diagnostics, honest evidence statuses |

No exception is proposed. Registry/source verification is not proof of image execution, license usability, accessibility, or participant usability. External licensing and implementation runtime tests remain named execution prerequisites, not unresolved architecture decisions.

## Project Structure

### Documentation created by this command

```text
specs/005-deployment-ci-documentation/
├── plan.md
├── research.md
├── data-model.md
├── contracts/deployment.md
└── quickstart.md
```

### Implementation targets at repository root

```text
Dockerfile                         # pinned runtime and validation targets
.dockerignore                      # deny-by-default context
compose.yaml                       # app only, independently startable
compose.minio.yaml                 # optional licensed MinIO service
.env.example                       # non-secret settings/placeholders
.gitignore                         # local secrets/licenses/data exclusions
scripts/check_deployment.py         # typed preflight/health/opt-in storage probe
pyproject.toml                     # Linux CPU source, tooling coverage
uv.lock                            # updated universal lock
.github/workflows/ci.yml            # extend working gates
README.md                          # expand existing developer entry point
app/                               # preserve existing workflows/services
tests/
├── unit/test_deployment_checks.py
├── integration/test_deployment.py
├── integration/test_prediction_storage.py
├── integration/test_classification_concurrency.py
├── integration/test_label_concurrency.py
└── smoke/
```

**Structure Decision**: Remain in the existing repository and service boundaries. One operational CLI is justified for safe file validation and bounded probes. Include it in strict mypy and Ruff coverage. No public HTTP API, deployment framework, parallel app configuration system, or additional ML backend.

## Phase 0: Research

[research.md](research.md) resolves distribution/licensing, immutable images, CPU dependencies, real persistence/lock locations, independent startup, safe operability checks, port-independent test networking and a single filtered build context. Image execution and license provisioning are verification prerequisites; do not disguise them as already-run checks.

## Phase 1: Design

### Packaging

Use research.md's immutable Python, uv, and AIStor references, with `platform: linux/amd64`. Build a non-root app runtime with a pre-created writable `/runtime` tree, CA certificates, and locked runtime dependencies without dev groups. A validation target adds dev tools/tests, not to the runtime image. Never re-resolve on startup or download models during build.

Set the container Streamlit bind address to `0.0.0.0`, headless mode, and usage telemetry off. Publish only host loopback for normal local deployment.

Both Dockerfile targets use the same root build context and root `.dockerignore`; there is no secondary named test context or context-staging helper. Begin with a deny-all rule, allow only required directory ancestors and explicitly reviewed source paths, and keep generated/secret exclusions effective after allow rules. Approved inputs are manifests, Dockerfile, app Python source, selected non-secret configuration, the diagnostic script, and an explicit list of approved Python test-source files. Do not broadly include everything under `tests/`: unlisted files, bytecode, caches, generated catalogs/sidecars, logs, credentials, licenses and backups remain excluded even there. New source-file allowlist entries require review.

The runtime target copies only app/config/manifest/diagnostic inputs, never tests. The validation target copies the approved `tests` subtree from that already-filtered context and installs locked dev tools. Approved non-sensitive test source is intentionally present in the shared context, not in the runtime image; this replaces the previous design-only exclusion of all tests from the runtime build context. No application secret or runtime payload is permitted in either context or image.

Implement exclusion tests in `tests/integration/test_deployment.py` against a disposable copy of the context with runtime-generated forbidden sentinels, including an unlisted file inside `tests/`. Inspect the actual filtered context through a temporary inspection build, not merely the runtime image's selected COPY results, then inspect runtime/validation contents separately. Verify approved tests are available only in the validation image and forbidden sentinels never reach the builder/context or either image. No real credentials/license material are used in these checks. Validate ownership, tiny CPU inference/imports, cp311/cp313 resolution and Hub cache-prune compatibility. Re-lock through uv, preserving the universal lock and Windows behavior.

### Configuration, topology, and durability

`compose.yaml` contains only `app`, publishes `127.0.0.1:8501:8501`, and mounts `app-runtime:/runtime`. It supplies existing path settings and optional storage credentials through environment variables. Internal defaults: `MINIO_ENDPOINT=minio:9000`, `MINIO_SECURE=false`, and the exact mandated bucket. No storage `depends_on` health gate.

`compose.minio.yaml` adds `minio`, loopback API 9000/console 9001, and `minio-data:/mnt/data`. Command: `minio server /mnt/data --license /minio.license --console-address :9001`. Use a read-only long-form license bind with `create_host_path: false`; Compose secrets supply root files through AIStor's `_FILE` settings. Required server-only interpolation must not occur in the app-only file. Never activate default root credentials.

App credentials remain existing `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` environment inputs, not an added app secret loader. Root credentials are not silently copied into the app. Trusted local operators may explicitly supply corresponding credentials; document Docker-admin environment visibility and production least privilege/TLS responsibilities.

Persist `/runtime/models`, `/runtime/hf-home`, `/runtime/hub-cache`, and `/runtime/labels/catalog.yaml`. Set library cache variables `HF_HUB_CACHE=/runtime/hf-home/hub` and `XDG_CACHE_HOME=/runtime/xdg-cache` explicitly so library defaults also stay durable; the existing adapter's explicit cache argument remains authoritative for its operations. Model-use locks are under `/runtime`; label marker/lock/temp sidecars are beside the catalog. First-use volume ownership must be verified with the actual non-root user. Do not recursively alter arbitrary host permissions.

Native Windows/Docker data separation remains an **autonomous, not user-confirmed default**. Quiesced transfer/backup must preserve manifests, all caches, catalog initialization evidence, and directory relationships. Do not transfer live locks between running environments or promise network-filesystem safety. Volumes do not preserve session futures or guarantee interrupted writes failed.

### Readiness and lifecycle

Use the CLI contract for static file checks, bounded health checks, and explicitly requested storage write/read probes. Existing config/client boundaries remain authoritative. A license file's existence is not signature validation; a healthy port/node is not licensed write permission.

The operational probe writes fixed non-sensitive JSON under `healthchecks/<uuid>.json`, never a prediction key; performs one PUT without retries; reads back exact content; removes only its confirmed exact key. Configuration errors, authoritative rejection, transport uncertainty, and cleanup failure are distinct failures. Uncertain writes retain key/ID inspection guidance and no blind retries.

Routine commands use `stop`, `start`, `up --force-recreate`, or `down` without volume deletion. Document quiescing and uncertain-write inspection before stopping. Destructive reset is separate, explicitly warned, and limited to verified project-owned resources; never routine recovery.

### CI and tests

Retain existing locked installation, Ruff lint/format, strict mypy, and unit/smoke selectors. Add both existing concurrency files. Fix the uv version and reviewed action commit identities during implementation; record supported runner identity.

Use a unique CI Compose project/network/volumes, image tags, container names and test bucket, never the developer's existing service. A unique project does not isolate fixed host ports by itself. For automated fixtures, start app/server service containers with `docker compose run -d --no-deps --use-aliases --name <owned-name>` and never request `--service-ports` or `--publish`. Compose run retains service volumes/configuration without publishing their configured ports. App-only fixtures use only `compose.yaml`, so storage interpolation remains absent.

Implement this isolation fixture and a `test_isolated_prediction_storage` case in `tests/integration/test_deployment.py`; reuse it for CI and the reproducible local alternative. The fixture builds the runtime/validation targets with the single filtered context, verifies exact container/project/network ownership and empty host port bindings, and runs probes and the existing `tests/integration/test_prediction_storage.py` inside the validation image attached only to the owned network. `app:8501` and `minio:9000` are test-network endpoints, not host URLs. Resolve the actual network ID from the owned container and verify Compose project labels; do not guess or attach to a preexisting network. Use test-scoped environment mappings rather than inherited host credentials/endpoints, and never fall back to localhost or an operator's server.

For fixture lifecycle checks, stop/start only the captured owned container IDs, recreate them through the same no-port Compose run command with the same owned volumes, and compare the durable data. Validate the normal deployment's loopback publications through configuration assertions separately; the authorized full-model walkthrough still exercises its actual documented `up --force-recreate`/`down` commands. Do not bind default host ports or stop an unrelated service merely to make automated tests pass.

CI secrets supply the permitted license; fork PRs do not receive secrets. Eligibility is decided from explicit runtime/license availability before execution. Missing prerequisites produce a visible named skip and local command. A supplied-invalid license, service startup failure after eligibility, or failed executed test fails the job; never substitute a historical image or convert failures to skips.

Reuse the existing complete-record prediction integration test. Its UUID object cleanup must remain exact; do not delete an existing bucket. Isolated deployment cleanup only targets resources created by that run, preserving unknown writes for inspection if the service is retained for diagnosis. Record cleanup failure, not unconditional success.

New focused fixtures cover deployment file/credential checks, safe output, bounded transport/TLS errors, bucket rejection, license-denied operations, unknown PUT outcomes, own-key cleanup, persistence layout, ownership, and context exclusions. Container lifecycle tests in `tests/integration/test_deployment.py` require explicit `RUN_DEPLOYMENT_TESTS=1` and available Docker; service cases additionally require authorized license-file provisioning. Missing external prerequisites are named skips before execution, while failures after eligibility fail. Container recreation tests use lightweight artifacts; real ready-model reuse is additionally validated in the separate full-model walkthrough. Ordinary tests never contact model services.

Exercise representative lint/format/type/test regressions with disposable validation fixtures and normal job exit propagation; never commit deliberately broken source. Record actual results, not just the presence of commands.

### Documentation

Expand README with purpose, actual architecture/module roles, all app/Hugging Face/server/deployment settings and precedence, model provenance/cache/deletion, label initialization/recovery, classification schema, license acquisition, endpoints, process inheritance, safe shutdown/uncertainty, retention/privacy, backups, and trusted-local limitations. Link existing feature guides rather than repeating conflicting advice.

Every walkthrough records tested versions, commands, outcomes, and unmet prerequisites. Do not count packaging tests as feature 004 participant usability or screen-reader evidence.

## Requirement and Acceptance Traceability

| Requirement | Design | Required evidence |
|---|---|---|
| FR-001 | image, base Compose, storage overlay | clean setup and full local deployment |
| FR-002 | pinned stack/uv, universal CPU source lock | locked build, imports, cp311/cp313; no model build downloads |
| FR-003 | supported licensed AIStor | official sources, file checks, actual licensed write |
| FR-004 | single deny-by-default context/external secrets | direct filtered-context inspection and runtime/validation sentinel scans |
| FR-005 | endpoint/process/TLS contract | native/container connectivity and TLS failure |
| FR-006 | loopback publications/trusted-local docs | rendered ports and host exposure check |
| FR-007 | full runtime and MinIO volumes | stop/restart/recreate resource comparison |
| FR-008 | model-parent locks, label sidecars, separate environments | concurrency regression; quiesced transfer review |
| FR-009 | preflight, node health, write/read probe | complete setup-failure matrix |
| FR-010 | independent base Compose | shell/management without storage credentials/service |
| FR-011 | exact default and explicit override | omitted, valid, and rejected bucket cases |
| FR-012 | unchanged UI/request/record semantics | existing smoke plus real saved-record walkthrough |
| FR-013 | durable volumes and separate reset | non-destructive lifecycle/backup checks |
| FR-014 | inspection before uncertain retry | late-write fixtures and recovery review |
| FR-015 | extend current CI selectors/gates | visible quality and concurrency runs |
| FR-016 | pinned tools, offline ordinary tests | network guards and safe artifact scan |
| FR-017 | no-port owned test network and eligible real service | fixture ownership/port assertions and existing full-record write/read test |
| FR-018 | eligibility distinct from failure | missing prerequisite skip; invalid supplied license fails |
| FR-019 | owned-key/project cleanup | unrelated sentinel objects/buckets remain |
| FR-020 | required nonzero exit propagation | lint/format/type/test regression fixtures |
| FR-021 | expanded actual README coverage | module/config/schema review |
| FR-022 | PowerShell/container runnable guide | recorded commands/expected outcomes |
| FR-023 | diagnostic and safe recovery matrix | common setup-failure walkthrough |
| FR-024 | privacy/retention/backup/TLS limits | sensitive-data sentinel/operator review |
| FR-025 | explicit pass/fail/skip evidence | all commands accounted for; no unrun claims |

| Acceptance scenarios / success criteria | Evidence |
|---|---|
| US1/AC1, US3/AC1, SC-001 | clean reviewer setup with external prerequisites |
| US1/AC2, SC-002 | automatic completion and exactly one matching actual record |
| US1/AC3, SC-003 | durable data/model reuse across stop/restart/recreation |
| US1/AC4, US3/AC2, SC-004 | safe diagnostics and corrective steps |
| US1/AC5 | app-only startup and management |
| US1/AC6 | uncertainty inspection before retry/shutdown |
| US2/AC1-2, SC-005 | visible gates and representative failed jobs |
| US2/AC3-4, SC-006 | real eligible storage run or explicit prerequisite skip |
| US2/AC3, SC-007 | no unrelated deletions and no sentinel leaks |
| US3/AC3, SC-008 | complete documentation and honest recorded outcomes |

These are validation obligations, not execution claims. All 25 FRs, 13 acceptance scenarios, and 8 SCs are mapped. No tasks or implementation changes are produced by planning.

## Analysis Finding Resolution and Task Handoff

| Finding | Resolved design | Required task synchronization |
|---|---|---|
| U1 | No-port Compose run fixtures; validation client on a verified owned network; no host-service fallback | T007, T015, T021, T022, T024 and their evidence/dependencies |
| U2 | One explicit root source allowlist shared by both targets; runtime excludes test COPY; direct context inspection | T007, T012, T014, T021 and build/evidence examples |

These choices do not alter the specification or normal local deployment defaults.
No new application settings, Compose override files, context helper or test
framework are introduced. Task synchronization and analysis are complete; retain
these decisions during implementation and regenerate tasks if the design changes.
