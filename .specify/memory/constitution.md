<!--
Sync Impact Report
Version change: unratified scaffold -> 1.0.0
Modified principles: None; this is the initial adoption.
Added principles: Mandated Technology Stack; Python Quality and Dependency Management;
Reproducible Model Use; Modular Boundaries; Streamlit Lifecycle and State;
Configuration and Secrets; Prediction Persistence and Data Handling;
Security and Safe Failure; Testing and Quality Gates; Observability and Documentation.
Added sections: Compliance Checks; Development Workflow.
Removed sections: Unfilled scaffold placeholders and example text.
Follow-up TODO: Confirm the original ratification date and replace its TODO marker.
This impact report is temporary and should be removed before this file is committed.
-->

# Zero-Shot Text Classification Constitution

This project builds a reproducible Python zero-shot text-classification platform that demonstrates sound MLOps engineering practices.

## Core Principles

### 1. Mandated Technology Stack
The application MUST use Python, PyTorch, Hugging Face Transformers, Streamlit, and MinIO as its core technologies. Replacing or adding a core platform technology requires an approved, documented architecture decision describing the rationale, trade-offs, and impact on reproducibility. Supporting configuration and deployment formats may use their customary languages.

Rationale: These choices are project constraints and preserve a coherent platform.

### 2. Python Quality and Dependency Management
The project MUST support Python 3.11 or later, use an isolated environment and a reproducible dependency workflow with committed dependency constraints or lock data, and apply Ruff formatting and linting. Public interfaces and non-trivial service boundaries MUST have useful type annotations. CI MUST run automated type checking using the project's configured checker.

Rationale: A consistent, reproducible Python baseline reduces setup drift and catches errors early.

### 3. Reproducible Model Use
Model loading and inference MUST use the PyTorch backend. Model identifiers and revisions MUST be explicit in configuration or runtime metadata so an inference can be reproduced. Model loading MUST NOT enable Hugging Face `trust_remote_code` unless the remote code has been reviewed and the exception is documented. Heavy models MUST NOT be downloaded during ordinary unit tests.

Rationale: Backend consistency, traceable revisions, and controlled remote code reduce supply-chain and reproducibility risk.

### 4. Modular Boundaries
Streamlit pages MUST remain presentation and interaction layers. Model lifecycle operations, inference, configuration access, and MinIO persistence MUST be implemented behind separately testable service boundaries. Dependencies MUST flow through explicit interfaces rather than UI code reaching into unrelated implementation details.

Rationale: These boundaries make core behavior testable and prevent framework-specific concerns from spreading through the application.

### 5. Streamlit Lifecycle and State
The UI MUST follow Streamlit's rerun and session model. New multipage structures SHOULD use `st.Page` and `st.navigation`. Large model objects and reusable connections MUST be cached as resources where appropriate, keyed by relevant model or configuration identity, and treated as shared state requiring thread-safe use. Per-user transient state MUST remain session-scoped. Cached resources MUST NOT substitute for durable storage.

Rationale: Correct lifecycle handling avoids repeatedly loading large models and prevents state leakage or mutation races between sessions.

### 6. Configuration and Secrets
Environment-specific settings MUST come from environment variables or an established secret manager. Non-secret model and label configuration MUST live in explicit configuration files, not be scattered through source code. Credentials, tokens, `.env` files, downloaded model artifacts, and runtime caches MUST NOT be committed. Production MinIO connections MUST use TLS when supported, and credentials MUST follow least privilege.

Rationale: Externalized configuration improves portability while reducing credential exposure and accidental data loss.

### 7. Prediction Persistence and Data Handling
MinIO MUST be the system of record for successful classification outputs, using the configurable bucket whose default is `zeroshot_learning_output`. A local file or database MUST NOT silently replace MinIO as the authoritative prediction store. Input text and prediction data MUST be treated as potentially sensitive: collect and persist only what the product requires, avoid logging raw text by default, and document storage location and retention behavior.

Rationale: This preserves the project's storage contract while making privacy and operational expectations explicit.

### 8. Security and Safe Failure
Inputs and configuration MUST be validated at trust boundaries. Errors shown to users MUST be actionable without exposing credentials, tokens, internal paths, or sensitive payloads. Administrative operations MUST be limited to local or otherwise trusted environments unless real authentication and authorization are implemented. Hiding a page from navigation MUST NOT be treated as access control. Model download or storage failures MUST leave the application in a recoverable, clearly reported state.

Rationale: The platform handles user-supplied text, credentials, model artifacts, and administrative actions.

### 9. Testing and Quality Gates
Core service behavior MUST have automated unit tests. Tests MUST be deterministic, avoid unnecessary network access and large model downloads, and cover meaningful error paths. MinIO persistence MUST have integration coverage against MinIO or a compatible service; test doubles MAY be used for isolated unit tests. CI MUST run formatting and lint checks, type checking, and unit tests, and MUST run service-backed integration tests when its environment supports them. Any integration test not run in CI MUST have a documented reproducible command. A change is not complete until relevant checks pass or an exception is recorded.

Rationale: Layered tests provide fast feedback while retaining evidence that the object-storage contract works.

### 10. Observability and Documentation
Operationally significant model, inference, and storage events MUST be logged with useful non-sensitive metadata. Logs MUST NOT contain secrets or raw user text by default. Setup, configuration, model provenance, data handling, testing, and known security limitations MUST be documented and kept consistent with the implementation.

Rationale: Useful diagnostics and accurate documentation are necessary for reproducible operation and responsible maintenance.

## Compliance Checks

- CI MUST run Ruff formatting and lint checks, the configured type checker, and the unit test suite.
- Unit tests MUST use mocks or lightweight fixtures instead of downloading large models or requiring network access.
- Integration coverage MUST verify that prediction data can be written to MinIO or a compatible service. When this does not run in CI, its documented command MUST be reproducible by a developer.
- Repository changes MUST NOT add credentials, `.env` files, model artifacts, or runtime caches.
- Reviews MUST verify that prediction outputs remain persisted through MinIO and that logs and user-facing errors do not expose secrets or raw input text by default.
- Documentation MUST explain how to configure and run the project, test it, and understand its data handling and security limitations.

## Development Workflow

Feature-specific behavior and acceptance criteria MUST be defined in feature specifications. Design and implementation choices MUST be captured in plans. Tasks and tests MUST be consistent with those artifacts and this constitution. Reviews MUST check constitutional compliance. Deliberate exceptions MUST follow the architecture-decision process in Governance; they MUST NOT be introduced silently.

## Governance

This constitution governs project specifications, plans, tasks, implementation, and reviews. Compliance MUST be checked during implementation and in CI wherever it can be automated. A deliberate exception MUST be recorded in an architecture decision record with its reason, scope, risks, and approval by the project maintainer. If an exception changes a standing principle, amend this constitution before applying that change more broadly.

Constitution amendments MUST be reviewed and documented. Use semantic versioning: MAJOR for backward-incompatible principle removals or redefinitions, MINOR for new principles or materially expanded rules, and PATCH for non-semantic clarifications. Update the last-amended date for each amendment. Compliance gaps or checks that cannot be automated MUST be reported for maintainer review.

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): confirm original adoption date | **Last Amended**: 2026-11-01
