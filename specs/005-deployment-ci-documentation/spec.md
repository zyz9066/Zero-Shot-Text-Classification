# Feature Specification: Deployment, CI, and Developer Documentation

**Feature Branch**: `005-deployment-ci-documentation`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: Make the existing zero-shot classification platform reproducibly deployable through Docker and Docker Compose, extend existing CI validation, and provide complete developer documentation without changing the established application workflows.

## Clarifications

### Session 2026-11-14

- Q: Should the native Windows app and the Docker app be allowed to use the same model and label files at the same time? -> A: Keep runtime data separate; transfer data only after stopping all writers. This is an autonomous default because the user was unavailable, not a user-confirmed choice.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the platform locally (Priority: P1)

As a developer, I want a documented container-based local setup for the application and prediction storage, so that I can classify sample text, inspect its saved record, and safely stop and restart the platform.

**Why this priority**: Deployment must make the existing platform usable without losing its data or relying on undocumented setup from prior conversations.

**Independent Test**: Starting with the documented prerequisites and externally supplied credentials and license where required, run the local deployment, prepare a model and labels through existing workflows, classify non-sensitive sample text, inspect its stored record, and verify persistence after non-destructive restart and container recreation.

**Acceptance Scenarios**:

1. **Given** a developer with the documented prerequisites and external configuration, **When** they follow the local setup instructions, **Then** the application and storage start, their readiness can be checked, and browser access is limited to the local machine by default.
2. **Given** a running deployment, a ready local model, valid saved labels, and usable storage, **When** the developer submits non-sensitive sample text, **Then** the page automatically displays the completed outcome without another submission, and one matching prediction record can be inspected by request identifier in the configured bucket.
3. **Given** downloaded models, caches, saved label configuration and its required sidecars, and saved predictions, **When** services are stopped and restarted or containers are recreated using documented non-destructive commands, **Then** these durable resources remain available and an already-ready model is reused without downloading it again.
4. **Given** missing credentials, a rejected bucket name, missing or invalid license material including a directory supplied instead of a file, an unreachable endpoint, or mismatched TLS settings, **When** readiness or setup is checked, **Then** safe diagnostics distinguish the problem and explain a corrective action without claiming successful prediction storage.
5. **Given** storage credentials or the storage service are unavailable, **When** the application is started independently, **Then** its shell and existing independent management workflows remain usable, and classification cannot claim a successful save.
6. **Given** a write has an uncertain outcome, **When** the developer follows recovery or shutdown guidance, **Then** an authorized operator inspects the request identifier, does not resubmit if a matching record exists, and permits a new submission only after both absence and non-completion of the original write are established; otherwise retry is deferred.

---

### User Story 2 - Validate changes automatically (Priority: P1)

As a contributor, I want existing quality gates and meaningful persistence and concurrency validation to run reproducibly, so that regressions are visible before changes are accepted.

**Why this priority**: Packaging and configuration changes can break existing behavior even when the application appears to start successfully.

**Independent Test**: Run automated validation on a supported runner, verify the existing quality checks and cooperating-process tests execute, introduce a representative failing check to confirm the job fails, and exercise service-backed persistence with isolated test resources or inspect an explicit prerequisite-based skip.

**Acceptance Scenarios**:

1. **Given** a normal contribution, **When** CI runs, **Then** existing lint, formatting, type, unit, and smoke checks remain present, cooperating-process concurrency tests execute on supported runners, and results are visible.
2. **Given** a lint, formatting, type, or test regression, **When** the affected required check executes, **Then** the job fails with useful non-sensitive diagnostics rather than reporting success.
3. **Given** CI supports the runtime and licensing prerequisites for an isolated storage service, **When** persistence integration validation runs, **Then** it writes and reads back a complete prediction record and cleans up only its own test resources, leaving unrelated objects and buckets untouched.
4. **Given** service-backed validation cannot run because documented prerequisites are unavailable, **When** validation finishes, **Then** the result explicitly identifies the skip and its reason, makes no service-backed coverage claim, and provides a reproducible local alternative. An available service with a failing test is not treated as a prerequisite-based skip.

---

### User Story 3 - Understand and operate the project (Priority: P2)

As a new developer, I want a complete, accurate README and troubleshooting guide, so that I can configure, run, test, and understand the platform without previous chat sessions.

**Why this priority**: A working deployment is not reproducible for new contributors unless its configuration, data handling, and recovery rules are explained.

**Independent Test**: Have a reviewer follow the README using only the repository and stated external prerequisites, perform a sample classification and authorized storage inspection, and locate safe recovery instructions for the documented setup failures.

**Acceptance Scenarios**:

1. **Given** only the repository, README, and documented external prerequisites, **When** a developer follows the quickstart, **Then** they can start the platform, prepare its model and labels, classify sample text, and verify persistence without relying on previous conversations.
2. **Given** an unavailable server, invalid license, incorrect endpoint, missing process environment, rejected bucket, or uncertain write, **When** the developer consults troubleshooting, **Then** they can distinguish that condition and find a safe next action without exposing credentials or sensitive records.
3. **Given** a contributor reviewing architecture, configuration, and tests, **When** they consult the documentation, **Then** it explains actual component responsibilities, supported models and provenance, persistence and retention, validation commands, and known limitations, clearly separating verified results from unrun checks.

### Edge Cases

- Docker or its service is unavailable, required ports are occupied, or storage locations are unwritable or lack capacity; startup must report an actionable failure without deleting existing data.
- A license path is absent, unreadable, expired or otherwise rejected, or is a directory instead of a file; an open port alone must not be treated as proof that prediction storage is usable.
- The developer confuses the storage API with its web console, uses a host endpoint from inside the deployment, or chooses a TLS setting inconsistent with the server.
- Environment variables are set in a different terminal or after the application starts; instructions must explain process inheritance and the restart needed for changes to take effect.
- The mandated default bucket is rejected by the selected service; operators must explicitly configure a valid alternative, with no automatic substitution.
- A container is recreated but the persisted model or label location, initialization evidence, or coordination sidecars are missing; configuration must preserve their relationships rather than silently initializing over existing state.
- Storage becomes unavailable after startup, or shutdown interrupts a download or write; existing safe failure and uncertain-outcome rules still apply. Restart alone is not proof of a failed write.
- CI lacks external license material or cannot start an isolated service; skipped validation must be distinguishable from failed validation and from executed coverage.
- Test cleanup or routine shutdown runs near unrelated resources; it must not remove an operator's buckets, objects, catalogs, models, or durable volumes.
- Administrators modify local files outside cooperating application processes; documentation must require quiescing writers and must not promise unsupported multi-host or network-filesystem coordination.
- A developer switches between native Windows and Docker execution; each environment must use separate model, cache, and label data locations. Transfers require stopping all writers and preserving provenance and initialization evidence. Simultaneous cross-environment access to those files is unsupported.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST provide Docker-based application packaging and Docker Compose orchestration for a single-host local development deployment of the existing application and MinIO storage.
- **FR-002**: Deployment MUST preserve the mandated Python, PyTorch, Transformers, Streamlit, and MinIO stack, Python 3.11+ support, and the existing uv lock-based dependency workflow. Runtime dependencies and deployment versions MUST be reproducibly selected and documented; building the application image MUST NOT download full models.
- **FR-003**: The deployed MinIO distribution MUST be supported at implementation time. Required registration and licensing, obtaining and supplying valid license material, and the selected distribution's limitations MUST be documented. Distribution, versions, and packaging details remain planning decisions requiring verification.
- **FR-004**: Credentials, tokens, license material, local model artifacts, runtime caches, and sensitive local data MUST remain outside committed source and application images and MUST be excluded from application build contexts. Non-secret examples MUST clearly distinguish placeholders from real credentials.
- **FR-005**: Configuration guidance MUST distinguish host-facing storage API and browser console endpoints from the endpoint used by the deployed application, explain HTTP/TLS settings, and explain which process receives each environment value.
- **FR-006**: The default local deployment MUST expose browser and storage endpoints only to the local machine. Documentation MUST identify it as trusted local development, not production security or public hosting; navigation visibility MUST NOT be described as access control.
- **FR-007**: Downloaded models and provenance, Hugging Face caches, saved label configuration and its required initialization and coordination sidecars, and MinIO prediction records MUST survive documented ordinary service stops, restarts, and container recreation. Their persistent locations and lifecycle MUST be documented.
- **FR-008**: Deployment MUST preserve existing cooperating single-host locking and availability guarantees, with consistent persisted configuration and coordination locations. Native Windows and Docker application environments MUST use separate model, cache, and label data locations; documented transfers MUST require stopping all writers and preserving model provenance and label initialization evidence. Simultaneous cross-environment access to those files is unsupported. Deployment MUST NOT imply multi-host or network-filesystem safety or introduce new model or label management workflows.
- **FR-009**: Startup and readiness checks MUST provide safe, actionable diagnostics for unavailable components, invalid configuration, unusable storage, and missing or invalid license material. Storage readiness MUST distinguish a responding service from one that denies required storage operations.
- **FR-010**: Application-shell startup and existing independent management workflows MUST remain possible without prediction-storage credentials or service availability. Storage readiness MUST NOT become a new prerequisite for these independent capabilities.
- **FR-011**: The existing configurable bucket and default `zeroshot_learning_output` MUST be preserved. Documentation MUST explain naming rejection and show an explicit valid test-bucket override. Deployment MUST NOT silently select another bucket or prediction store.
- **FR-012**: The deployed classification flow MUST preserve automatic completed-outcome display, request identity, provenance, and the existing JSON record contract. A prediction MUST be presented as successful only after a confirmed MinIO write.
- **FR-013**: Shutdown, restart, backup, and recovery guidance MUST distinguish transient state from durable resources. Routine shutdown MUST NOT delete durable data; destructive reset or cleanup MUST be separate and explicitly warned about, not routine recovery.
- **FR-014**: Uncertain-write guidance MUST give authorized operators a request-identifier-based inspection procedure, prohibit resubmission when a matching record exists, and permit resubmission only after both absence and non-completion of the original write are established. Otherwise retry MUST be deferred; elapsed time or restarting alone MUST NOT be represented as sufficient proof.
- **FR-015**: The existing `.github/workflows/ci.yml` MUST be reused and extended without unnecessarily replacing working gates. CI MUST execute Ruff lint and format checks, strict mypy, deterministic unit and smoke tests, and existing cooperating-process concurrency tests on supported runners.
- **FR-016**: Ordinary automated tests MUST NOT download full models or contact external model services. CI dependencies and service versions MUST be reproducibly selected; secrets and sensitive payloads MUST NOT appear in logs or artifacts.
- **FR-017**: The existing service-backed prediction write/read integration test MUST run against an isolated MinIO-compatible service and bucket when CI supports the necessary runtime and licensing prerequisites. Validation MUST inspect a complete saved record, not count mocks as service-backed evidence.
- **FR-018**: When service-backed integration prerequisites are unavailable, validation MUST report an explicit skip reason and documentation MUST supply a reproducible local command. A failing executed test MUST NOT be converted into a successful result or prerequisite skip.
- **FR-019**: Integration cleanup MUST affect only resources created for the test and leave unrelated objects, buckets, and durable application resources untouched.
- **FR-020**: Every failed required quality or test check MUST fail its CI job and expose useful non-sensitive diagnostics.
- **FR-021**: The existing README MUST be expanded with purpose, architecture, actual directory structure and major module responsibilities, prerequisites, all supported environment settings and precedence, supported models and provenance, model caching and deletion, label management, classification, and the actual MinIO output contract.
- **FR-022**: Documentation MUST provide copyable Windows PowerShell and supported container-environment setup, run, readiness, stop, restart, and validation commands with expected outcomes, clearly distinguishing host/container paths and shell syntax.
- **FR-023**: Troubleshooting MUST cover server availability, licensing and file mounts, API versus console endpoints, process environment inheritance, invalid credentials, TLS mismatch, bucket naming and permissions, automatic status refresh, and confirmed versus uncertain storage failures.
- **FR-024**: Documentation MUST explain sensitive input and prediction handling, storage location and retention, authorized record inspection, backups, least-privilege credentials, TLS for production where supported, and known access and concurrency limitations. Examples MUST be non-sensitive and MUST NOT instruct readers to share secrets, license contents, raw input, or prediction payloads in support channels.
- **FR-025**: Validation guidance MUST include unit, smoke, concurrency, and service-backed integration commands and MUST distinguish observed outcomes from unrun integration, accessibility, and participant usability checks. It MUST NOT claim unverified success.
- **FR-026**: The Windows local workflow MUST offer an interactive first-time setup and concise start, stop, and status commands. It MUST reuse existing configuration, validate supplied external files, preserve any existing `.env`, prompt for application credentials without saving them, retain named volumes on stop, and distinguish container status from storage readiness. It MUST preserve the existing bucket default unless the operator explicitly supplies an override and retain the independent app-only workflow.

### Key Entities *(include if feature involves data)*

- **Local Deployment Configuration**: External settings identifying application and storage connections, persistent resources, and required credential and license inputs; distinguishes host and deployed-process contexts.
- **Persistent Resource**: Existing model and cache contents, label catalog and its sidecars, or prediction objects whose lifetime is independent of disposable containers.
- **Readiness Result**: A safe indication of whether a component is available and usable, with an actionable reason when required configuration or operations are rejected.
- **Validation Result**: An executed check's pass or failure, or an explicit prerequisite-based skip, associated with the tested environment and versions.
- **Developer Guide**: Repository-based instructions explaining setup, architecture, operations, validation, and recovery using non-sensitive examples.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a documented clean-environment walkthrough, a reviewer using only repository guidance and stated external prerequisites can start the platform, prepare a model and labels, submit non-sensitive text, and inspect one matching saved record without consulting earlier conversations.
- **SC-002**: In every tested successful request in the deployment walkthrough, the completed outcome appears without resubmission and corresponds to exactly one stored record with the existing required metadata.
- **SC-003**: In all tested non-destructive stop/restart and recreation cases, existing models and provenance, caches, labels and their required sidecars, and predictions remain available; ready models are not downloaded again.
- **SC-004**: Every tested setup failure in the documented diagnostic matrix has a safe corrective next step, and no failure is represented as a successful save or usable storage when operations are denied.
- **SC-005**: Every required automated check has an observable result; representative lint, formatting, type, and test failures each produce a failed job.
- **SC-006**: Every eligible service-backed validation run verifies a complete record through write/read operations. Every ineligible run reports a prerequisite-based skip and a local alternative; no unrun test is reported as executed coverage.
- **SC-007**: Across all tested shutdown and integration-cleanup cases, zero unrelated resources are deleted. Representative logs, artifacts, and packaged contents contain none of the test's sentinel credentials, license contents, or sensitive payloads.
- **SC-008**: A documentation reviewer can locate instructions for every topic in FR-021 through FR-025, and all executable validation examples used in the walkthrough have recorded outcomes or explicit unmet prerequisites.

## Assumptions

- Features 001 through 004 supply the existing application, configuration, management, classification, and persistence behavior. This feature packages and validates those capabilities rather than redefining them.
- Existing CI already runs unit and smoke tests, lint, formatting, and type checks. Remaining work extends coverage and deployment guidance rather than duplicating those gates.
- Developers install and start a supported container runtime and supply external credentials and any required valid license. Network access is available for dependencies and intentional first-time model downloads; download time is not assigned an invented latency target.
- The supported deployment is a trusted single-host environment with cooperating application processes and local persistent storage. Manual file changes require stopping cooperating writers.
- Native Windows and Docker environments keep model, cache, and label data separate. Cross-environment transfer is an operator-controlled, quiesced procedure, not concurrent sharing or an automatic migration feature.
- Ordinary shutdown preserves durable data. In-flight session work is not promised to survive process loss; existing uncertain-outcome recovery applies.
- Storage lifecycle policy and authorized operator actions govern retention. Backup and recovery procedures are documented without adding in-app retention or backup management.
- Planning verifies supported distribution, licensing, versions, persistence layout, and readiness mechanisms before implementation. No historical image or universal license availability is assumed.
- CI may lack external runtime or licensing prerequisites. Only explicit prerequisite-based skips are allowed; available-service failures remain failures.

## Out of Scope

- New inference behavior, prediction browsing, analytics, export, or retention management.
- New model or label management workflows or a separate persistence feature already covered by feature 004.
- Authentication, authorization, role management, public hosting, production certification, Kubernetes, and multi-host coordination.
- Replacing the mandated application stack, MinIO system of record, bucket default, or existing prediction schema.
- Planning, generating tasks, implementing deployment or CI changes, starting services, or committing changes during this specification step.
