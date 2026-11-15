# Feature 5: Deployment, CI, and Developer Documentation Plan

Use this as the `/speckit-plan` input for feature 005:

```text
/speckit-plan Create the technical implementation plan for Deployment, CI, and Developer Documentation in `specs/005-deployment-ci-documentation/spec.md`. Follow `.specify/memory/constitution.md`, preserve features 001 through 004, and treat the current specification as the source of intent.

Honor the clarification that native Windows and Docker application environments use separate model, cache, and label data locations. Transfers require stopping all writers and preserving provenance and initialization evidence. This is currently an explicitly recorded autonomous default, not a user-confirmed choice; do not imply cross-platform concurrent file sharing is supported.

Baseline and scope

- Inspect the actual application, configuration loaders, model and label persistence/locking, prediction storage, pyproject.toml, uv.lock, existing CI workflow, tests, README, and feature quickstarts before proposing changes.
- Identify existing working capabilities and only plan the remaining deployment, validation, and documentation work. Preserve local-only PyTorch inference, model provenance, label validation, automatic completion refresh, request identity, safe failure, and confirmed-MinIO-write success semantics.
- Keep Python 3.11+ and the existing uv dependency workflow. Preserve separately testable service boundaries and avoid introducing a second configuration system, ML backend, or prediction store.

Container packaging and orchestration

- Design a reproducible application image and single-host Docker Compose setup for Streamlit and MinIO. Research compatible base images, CPU inference dependencies, locked dependency installation, and runtime versions. Pin or otherwise record immutable version identities and explain how future updates are validated.
- Verify a currently supported MinIO distribution using official sources. Evaluate its licensing, registration, image availability, startup flags, and supported platform requirements; cite verified sources in research.md. Do not assume archived community images or old download instructions are suitable.
- Design external secret and license provisioning without baking credentials or license contents into images or source. Define non-secret examples, prerequisite validation, and build-context exclusions for secrets, licenses, local model artifacts, caches, catalogs, and prediction data.
- Do not download models during image construction. Preserve intentional model preparation through the existing management workflow.
- Specify host-loopback port bindings, the host API and console addresses, the application-to-storage address inside the deployment, and TLS settings. Explain Docker Desktop prerequisites for Windows and the supported Linux container/runtime and CI environments without promising untested platforms.
- Keep the shell and independent management workflows usable without MinIO credentials or availability. Separate application startup health, storage liveness, and verification that storage operations are permitted; do not make storage readiness a mandatory dependency for independent app startup.
- Plan explicit, bounded readiness diagnostics for invalid license mounts, missing or rejected credentials, unavailable servers, TLS mismatch, invalid bucket names, and permission failures. A listening port is not proof that writes are allowed. Any operational probe must avoid sensitive data, prediction-key collisions, silent retries, and removal of unrelated objects.

Durability, coordination, and lifecycle

- Map each persistent resource to its actual location: app-managed models and manifests, all configured Hugging Face cache locations, label catalog and initialization/lock sidecars, model-use coordination sidecars, and MinIO objects. Inspect sidecar locations rather than assuming every lock is inside a model directory.
- Select a persistence layout that survives ordinary stops, restarts, and container recreation. Preserve directory relationships, canonical lock identities, permissions, and cooperating single-host behavior. Keep native Windows and Docker file data separate.
- Describe operator-controlled transfer and backup/restore procedures with all writers stopped; do not add automatic migration, concurrent host/container sharing, or unsupported network-filesystem guarantees.
- Preserve the configured bucket and default `zeroshot_learning_output` exactly. Explain service rejection of underscores and demonstrate an explicit valid test-bucket override rather than silently renaming it.
- Define non-destructive startup, shutdown, restart, and recreation commands. Distinguish these from explicitly warned destructive reset commands; routine recovery must not delete volumes or saved data.
- Preserve interrupted-download and uncertain-write behavior. An operator must inspect the request key; a matching record means no resubmission, and retry is permitted only after both absence and non-completion of the original write are established. Do not invent a universal timeout or imply restart proves a write failed.

CI and test design

- Extend `.github/workflows/ci.yml` without unnecessarily replacing existing gates. Retain locked installation, Ruff lint/format checks, strict mypy, unit tests, and smoke tests; include existing cooperating-process concurrency tests on supported runners.
- Plan isolated service-backed validation using the existing prediction storage integration test. Verify the actual selected server/client combination and license prerequisites. Define test configuration, unique resource identity, safe cleanup, and observable results without touching the developer's existing storage service or data.
- Specify how CI distinguishes unavailable external prerequisites from executed test failures. Missing prerequisites require an explicit skip reason and a reproducible local command; available-service failures must fail the job. Never turn a failing test into a skip or claim mocks provide service-backed coverage.
- Ordinary tests must not download models or contact external model services. Plan lightweight fixtures for packaging, configuration, readiness, persistence layout, and failure diagnostics; use full models only in explicitly separate end-to-end validation.
- Include validation for container recreation without data loss, reuse of ready models, preservation of label initialization evidence, app startup without storage, automatic completed-result display, sensitive-data exclusions, and cleanup restricted to test-owned resources.
- Explain how representative lint, formatting, type, and test regressions demonstrate that required jobs fail without committing deliberately broken code.

Developer documentation and design deliverables

- Plan expansion of the existing README into a complete developer entry point, preserving useful prior guidance and linking feature-specific details rather than duplicating contradictory instructions.
- Cover architecture and actual module responsibilities, supported models/provenance, all environment settings and precedence, model/cache and label lifecycle, MinIO setup/licensing, prediction schema and retention, secrets, trusted-environment limits, backups, and safe recovery.
- Provide copyable Windows PowerShell and supported container-environment commands with expected results. Clearly distinguish host/container paths, API/console addresses, app versus server credential variables, and process environment inheritance/restart requirements.
- Include common setup failures encountered in this project: server not started, a directory mounted as a license file, storage denying operations despite responding, invalid bucket names, missing app credentials, and stale/background request status.
- Map all 25 functional requirements, all acceptance scenarios, and all 8 success criteria to design components and validation evidence. Record limitations and unmet external prerequisites explicitly; do not claim unrun service, accessibility, or reviewer walkthrough checks have passed.
- Generate the normal plan artifacts: plan.md, research.md, data-model.md for deployment configuration/persistent resources/readiness and validation outcomes, justified deployment/operational contracts, and quickstart.md. Keep quickstart as a runnable validation guide, not full implementation code.
- Recheck Constitution gates before and after design. Resolve research unknowns with verified evidence; report blockers rather than guessing or relaxing the specification.

Stop after planning and Phase 1 design. Do not modify application code, Docker/Compose configuration, CI workflows, dependency manifests, README, or existing specs in this step. Do not generate tasks.md, start or stop services, implement the feature, or commit changes.
```
