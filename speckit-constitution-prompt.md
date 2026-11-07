# Spec Kit Constitution Prompt

Use this after initializing Spec Kit in the repository. Invoke `/speckit.constitution` with the following input:

```text
Establish or update this project's constitution using the active Spec Kit constitution template. Treat the homework02 MLOps brief and the decisions below as project context, but include only enduring rules that govern all features. Do not turn feature requirements, acceptance criteria, example models, labels, page behavior, object schemas, or implementation tasks into constitutional principles. Keep each principle concise, normative, testable, and include its rationale. Include governance and concrete compliance checks. Preserve the Spec Kit command's scope: update the constitution only; do not implement features or modify unrelated artifacts.

Project purpose
Build a reproducible Python zero-shot text-classification platform that demonstrates sound MLOps engineering practices.

Principles

1. Mandated technology stack
The application MUST use Python, PyTorch, Hugging Face Transformers, Streamlit, and MinIO as its core technologies. A replacement or additional core platform technology requires an approved, documented architecture decision describing the rationale, trade-offs, and impact on reproducibility. Supporting configuration and deployment formats may use their customary languages.
Rationale: These choices are project constraints from the assignment and preserve a coherent platform.

2. Python quality and dependency management
The project MUST support Python 3.11 or later, use an isolated environment and a reproducible dependency workflow with committed dependency constraints or lock data, and apply Ruff formatting/linting. Public interfaces and non-trivial service boundaries MUST have useful type annotations. CI MUST run automated type checking using the project's configured checker.
Rationale: A consistent, reproducible Python baseline reduces setup drift and catches errors early without prescribing feature implementation details.

3. Reproducible model use
Model loading and inference MUST use the PyTorch backend. Model identifiers and revisions MUST be explicit in configuration or runtime metadata so an inference can be reproduced. Model loading MUST NOT enable Hugging Face `trust_remote_code` unless the remote code has been reviewed and the exception is documented. Heavy models MUST NOT be downloaded during ordinary unit tests.
Rationale: Backend consistency, traceable revisions, and controlled remote code reduce supply-chain and reproducibility risk.

4. Modular boundaries
Streamlit pages MUST remain presentation and interaction layers. Model lifecycle operations, inference, configuration access, and MinIO persistence MUST be implemented behind separately testable service boundaries. Dependencies MUST flow through explicit interfaces rather than UI code reaching into unrelated implementation details.
Rationale: These boundaries make core behavior testable and prevent framework-specific concerns from spreading through the application.

5. Streamlit lifecycle and state
The UI MUST follow Streamlit's rerun and session model. Multipage routing SHOULD use `st.Page` and `st.navigation` for new multipage structure. Large model objects and reusable connections MUST be cached as resources where appropriate, keyed by relevant model/configuration identity, and treated as shared state that requires thread-safe use. Per-user transient state MUST remain session-scoped; cached resources MUST NOT be used as a substitute for durable storage.
Rationale: Correct lifecycle handling avoids repeatedly loading large models and prevents state leakage or mutation races between sessions.

6. Configuration and secrets
Environment-specific settings MUST come from environment variables or an established secret manager. Non-secret model and label configuration MUST live in explicit configuration files, not be scattered through source code. Credentials, tokens, `.env` files, downloaded model artifacts, and runtime caches MUST NOT be committed. Production MinIO connections MUST use TLS when supported, and credentials MUST follow least privilege.
Rationale: Externalized configuration improves portability while reducing credential exposure and accidental data loss.

7. Prediction persistence and data handling
MinIO MUST be the system of record for successful classification outputs, using the configurable bucket whose default is `zeroshot_learning_output`. A local file or database MUST NOT silently replace MinIO as the authoritative prediction store. Input text and prediction data MUST be treated as potentially sensitive: collect and persist only what the product requires, avoid logging raw text by default, and document where data is stored and any retention behavior.
Rationale: This preserves the assignment's storage contract while making privacy and operational expectations explicit.

8. Security and safe failure
Inputs and configuration MUST be validated at trust boundaries. Errors shown to users MUST be actionable without exposing credentials, tokens, internal paths, or sensitive payloads. Administrative operations MUST be limited to local or otherwise trusted environments unless real authentication and authorization are implemented; hiding a page from navigation MUST NOT be treated as access control. Model download or storage failures MUST leave the application in a recoverable, clearly reported state.
Rationale: The platform handles user-supplied text, credentials, model artifacts, and destructive administration actions.

9. Testing and quality gates
Core service behavior MUST have automated unit tests. Tests MUST be deterministic, avoid unnecessary network access and large model downloads, and cover meaningful error paths. MinIO persistence MUST have integration coverage against MinIO or a compatible service; test doubles MAY be used for isolated unit tests. CI MUST run formatting/lint checks, type checking, and unit tests, and MUST run service-backed integration tests when its environment supports them. Any integration test not run in CI MUST have a documented reproducible command. A change is not complete until relevant checks pass or an exception is recorded.
Rationale: Layered tests provide fast feedback while retaining evidence that the object-storage contract works.

10. Observability and documentation
Operationally significant model, inference, and storage events MUST be logged with useful non-sensitive metadata. Logs MUST NOT contain secrets or raw user text by default. Setup, configuration, model provenance, data handling, testing, and known security limitations MUST be documented and kept consistent with the implementation.
Rationale: Useful diagnostics and accurate documentation are necessary for reproducible local operation and responsible maintenance.

Governance
The constitution applies to all feature specifications, plans, tasks, implementation, and reviews. Compliance MUST be checked during implementation and in CI where automatable. A deliberate exception MUST be recorded in an architecture decision record with its reason, scope, risks, and approval by the project maintainer. If the exception changes a standing principle, amend the constitution before applying it more broadly. Constitution amendments MUST include a version/date update consistent with the active Spec Kit template and explain their impact. Feature-specific behavior belongs in feature specifications, design choices belong in plans, and acceptance criteria belong in specifications or tests, not in this constitution.

After updating the constitution, summarize the principles and explain briefly why each belongs in the project constitution. Report any unresolved information or compliance checks that could not be completed.
```

## Why These Rules

- **Mandated stack:** Preserves the assignment's technology constraints while allowing a reviewed path for future architectural change.
- **Python quality and dependency management:** Makes the project installable and maintainable across developers and CI.
- **Reproducible model use:** Records the model inputs to inference and avoids executing unreviewed code from the Hub.
- **Modular boundaries:** Keeps UI, model, configuration, and storage independently understandable and testable.
- **Streamlit lifecycle and state:** Applies current guidance for model caching and avoids unsafe cross-session state.
- **Configuration and secrets:** Supports deployment portability without committing credentials or large artifacts.
- **Prediction persistence and data handling:** Retains MinIO as the durable record while recognizing that text inputs can be sensitive.
- **Security and safe failure:** Sets recurring safeguards around user input, administration, credentials, and recoverable errors.
- **Testing and quality gates:** Establishes practical automated checks without imposing strict TDD or an arbitrary coverage percentage.
- **Observability and documentation:** Keeps failures diagnosable and the project reproducible for a new developer.

## Documentation Reviewed

- [GitHub Spec Kit command reference](https://github.github.io/spec-kit/reference/agentic-sdd.html)
- [Hugging Face Transformers pipelines](https://huggingface.co/docs/transformers/main/en/main_classes/pipelines)
- [Hugging Face Transformers installation and cache guidance](https://huggingface.co/docs/transformers/main/en/installation)
- [Hugging Face Hub token security](https://huggingface.co/docs/hub/en/security-tokens)
- [Streamlit caching](https://docs.streamlit.io/develop/concepts/architecture/caching)
- [Streamlit multipage apps](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- [Streamlit secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [MinIO Python SDK](https://docs.min.io/aistor/developers/sdk/python/)
- [MinIO Python API reference](https://docs.min.io/aistor/developers/sdk/python/api/)
