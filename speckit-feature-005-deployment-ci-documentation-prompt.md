# Feature 5: Deployment, CI, and Developer Documentation

Current feature sequence: (1) application foundation and configuration;
(2) model lifecycle management; (3) candidate-label management;
(4) text classification and prediction persistence; (5) deployment, CI,
and complete developer documentation. Classification and MinIO persistence
were combined in feature 004, so do not create a separate persistence feature.

Use the following as the `/speckit-specify` input:

```text
/speckit-specify Create a specification for Deployment, CI, and Developer Documentation, the fifth feature of this zero-shot text classification platform.

Follow `.specify/memory/constitution.md` and preserve the behavior established in:
- `specs/001-application-foundation-config/`
- `specs/002-model-lifecycle-management/`
- `specs/003-candidate-label-management/`
- `specs/004-classification-persistence/`

The existing application already manages local models and saved labels, classifies text through PyTorch and Transformers, and persists successful predictions in MinIO. This feature makes those workflows reproducibly deployable, automatically validated, and understandable to a developer who has never used the project. Inspect the existing CI workflow and developer guides before specifying remaining work; do not duplicate completed capabilities.

User Story 1, priority P1: Run the platform locally.

As a developer, I want a documented container-based local setup for Streamlit and MinIO, so that I can start the platform, classify sample text, verify its saved prediction, and safely stop and restart it.

Business Rules

- Provide Docker-based application packaging and Docker Compose orchestration for a single-host local development deployment. These are supporting deployment technologies, not replacements for the mandated application stack.
- Preserve Python 3.11+ and the existing uv lock-based dependency workflow. The application image must use compatible, reproducibly selected runtime dependencies; it must not download full models during image construction.
- Use a currently supported MinIO server distribution. Document required licensing or registration and how to provide a valid license when needed; do not assume historical community images or binaries remain supported. Leave the distribution, versions, and detailed packaging decisions to planning after verification.
- Keep credentials and license material external to version control and images. Provide non-secret configuration examples, explain how to supply secrets, and exclude local artifacts and sensitive material from build contexts.
- Distinguish the host-facing storage API endpoint from the browser console endpoint and from the application-to-storage endpoint inside the deployment. Explain HTTP versus TLS settings and which process receives environment variables.
- Local development services must not be exposed beyond the local machine by default. Document that this setup is not a production security configuration; real authentication, authorization, TLS, and least-privilege credentials remain operator responsibilities.
- Preserve downloaded models, Hugging Face caches, saved label configuration and its required sidecars, and MinIO prediction objects across ordinary service stops, restarts, and container recreation. Document each persistence location and distinguish disposable container state from durable data.
- Preserve the existing cooperating single-host locking guarantees. Do not imply multi-host or network-filesystem safety, and do not introduce new model or label management workflows.
- Provide readiness checks and actionable diagnostics for startup, unavailable storage, invalid credentials, invalid bucket names, and missing or invalid licenses. The application shell must remain usable without storage credentials; classification cannot claim success without a confirmed MinIO write.
- Preserve the configured bucket and mandated default `zeroshot_learning_output`. Explain that some services reject the underscores and show an explicit valid test-bucket override; never silently rename the bucket.
- Document safe shutdown and restart. Stopping services must not delete durable data. Destructive reset or cleanup must be separate, explicitly warned about, and never used as routine recovery.

Acceptance Scenarios

1. Given a developer with the documented prerequisites and external credentials/license, when they follow the local setup instructions, then Streamlit and MinIO start, readiness can be checked, and the application is accessible locally.
2. Given a running deployment, when the developer prepares a model and label set and classifies non-sensitive sample text, then the page automatically displays the completed outcome and one matching prediction record can be inspected by request ID in the configured bucket.
3. Given existing models, labels, and predictions, when services are stopped and restarted or containers recreated using the documented non-destructive commands, then those resources remain available without redownloading a ready model or losing saved data.
4. Given missing credentials, a rejected bucket name, an invalid license file or directory mount, or an unreachable endpoint, when the developer follows troubleshooting guidance, then the problem can be identified without exposing secrets or falsely claiming a successful save.
5. Given an uncertain write, when recovery instructions are followed, then the operator inspects its request ID and does not resubmit unless both absence and non-completion of the original write are established.

User Story 2, priority P1: Validate changes automatically.

As a contributor, I want CI to run the project's quality gates and meaningful persistence integration coverage, so that regressions are detected reproducibly before changes are accepted.

Business Rules

- Reuse and extend `.github/workflows/ci.yml`; do not replace working gates unnecessarily.
- Run Ruff lint and formatting checks, strict mypy, deterministic unit and smoke tests, and the existing cooperating-process concurrency tests on supported CI runners.
- Ordinary tests must not download full models or contact external model services.
- Run the existing MinIO-compatible write/read integration test against an isolated service and bucket when CI supports its runtime and licensing prerequisites. Do not claim service-backed coverage when only mocks ran.
- If service-backed integration cannot run in CI, show an explicit skip reason and provide a reproducible local invocation. Never hide a skipped required check behind a success claim.
- Use reproducibly selected CI dependencies and service versions. Keep secrets out of source, logs, and artifacts. Integration cleanup must affect only resources created for that test.
- A failed required check must fail the CI job.

Acceptance Scenarios

6. Given a normal contribution, when CI runs, then the configured quality gates and deterministic regression tests execute and their results are visible.
7. Given a lint, type, or test regression, when CI runs, then the relevant job fails with actionable diagnostics.
8. Given an available isolated storage service, when integration validation runs, then a complete prediction record is written and read back, and cleanup leaves unrelated objects and buckets untouched. If prerequisites are unavailable, the skip and local alternative are documented explicitly.

User Story 3, priority P2: Understand and operate the project.

As a new developer, I want a complete, accurate README and troubleshooting guide, so that I can configure, run, test, and understand the platform without relying on previous chat sessions.

Business Rules

- Expand the existing README rather than replacing useful guidance with disconnected feature-only documentation.
- Cover purpose, architecture, actual directory structure and major module responsibilities, prerequisites, all supported environment settings and precedence, supported models and provenance, model caching/deletion, label management, classification, and MinIO record format.
- Provide copyable Windows PowerShell setup/run/stop commands and appropriate commands for the supported container environment. Do not mix host paths, container paths, or shell syntax.
- Explain starting MinIO, providing its license when required, choosing a valid bucket, supplying app credentials in the correct terminal, and restarting the app after environment changes.
- Explain background request status and automatic refresh, confirmed versus uncertain storage failures, authorized object inspection by request ID, sensitive data handling, retention, backups, and known security/concurrency limits.
- Include unit, smoke, concurrency, and service-backed integration commands and expected results. Clearly distinguish verified outcomes from unrun integration, accessibility, or participant usability checks.
- Use non-sensitive examples. Never instruct readers to paste credentials, license contents, raw user input, or prediction payloads into logs or support tickets.

Acceptance Scenarios

9. Given only the repository and its README, when a new developer follows the documented prerequisites and quickstart, then they can reach the application, prepare its prerequisites, classify sample text, and verify persistence.
10. Given a developer encountering a common setup failure, when they consult troubleshooting, then they can distinguish an unavailable server, invalid license, wrong endpoint, missing process environment, bucket rejection, and uncertain write, and find a safe next action.

Out of Scope

- New inference behavior, prediction history, analytics, export, or retention management.
- New model or label management workflows.
- Authentication, authorization, roles, public hosting, production certification, Kubernetes, or multi-host coordination.
- Replacing MinIO, the Python/PyTorch/Transformers stack, or the existing prediction schema.
- Creating a separate prediction-persistence feature already covered by feature 004.

Define measurable user-observable success criteria and relevant edge cases. Keep configuration and deployment constraints that are explicitly requested here, but leave detailed architecture, image selection, resource sizing, workflow design, and file changes to `/speckit-plan`.

Use reasonable assumptions and limit NEEDS CLARIFICATION markers to decisions materially affecting behavior or scope. Create only this feature's specification through the normal Spec Kit workflow; do not plan, generate tasks, implement, deploy services, or commit changes in this step.
```
