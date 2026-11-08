# Implementation Plan: Application Foundation and Configuration

**Branch**: `001-application-foundation-config` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-application-foundation-config/spec.md`

## Summary

Establish a runnable Streamlit application shell, centralized typed configuration, and safe structured logging. Use explicit configuration merging with environment variables taking precedence over non-secret YAML settings, then documented defaults. Load and validate shell-level configuration at startup; defer model and MinIO service-specific validation until those services are initialized or used. Keep later model-management, classification, candidate-label, and prediction-storage implementations outside this feature.

## Technical Context

**Language/Version**: Python 3.11 or later

**Primary Dependencies**: For this feature, Streamlit and PyYAML, plus Python standard-library dataclasses and logging. The project-wide required stack also includes PyTorch, Hugging Face Transformers, and the MinIO Python client; add each to the same project manifest and lock through the feature that first uses it. This feature does not initialize model inference or MinIO operations.

**Storage**: Non-secret application settings in YAML; model and Hugging Face artifacts in configured local directories when later features use them; MinIO remains the system of record for predictions in the later storage feature. This feature adds no database or prediction storage.

**Testing**: pytest unit tests and a local Streamlit shell smoke check; no network, model download, or running MinIO required for this feature's tests.

**Target Platform**: Local Python 3.11+ developer environment; avoid platform-specific assumptions in the application configuration layer.

**Project Type**: Single Python Streamlit application with separately testable configuration and logging modules.

**Performance Goals**: Configuration parsing and initial shell rendering must remain lightweight; the specification defines no numeric latency or throughput target.

**Constraints**: Environment > YAML > documented defaults; no secrets in committed YAML; shell startup does not require model or MinIO credentials; service settings are validated on service use; production MinIO connections use TLS when supported; no model downloads in unit tests.

**Scale/Scope**: One local application shell and shared configuration contract for the later model-management, classification, and storage features; no availability or concurrent-user target is defined for this feature.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Mandated Technology Stack**: PASS. Retain the Python, PyTorch, Transformers, Streamlit, and MinIO project stack; this feature does not replace any technology.
- **Python Quality and Dependency Management**: PASS. Support Python 3.11+, use an isolated environment and committed dependency lock data, configure Ruff and a type checker, and type public configuration boundaries.
- **Reproducible Model Use**: PASS / NOT IMPLEMENTED HERE. The configuration contract reserves model identifier and revision settings for later features; this feature does not load models, enable remote code, or download artifacts.
- **Modular Boundaries**: PASS. Keep UI startup, configuration resolution, logging, model lifecycle, inference, and MinIO persistence as distinct responsibilities; implement only the foundation boundaries in this feature.
- **Streamlit Lifecycle and State**: PASS. Keep the shell compatible with reruns and session state. Do not cache resolved secrets or configuration in shared Streamlit caches. Later model and connection resources must use identity-keyed resource caching and be safe for shared access.
- **Configuration and Secrets**: PASS. Merge environment variables, non-secret YAML, and defaults in the specified order; keep credentials in environment variables or an approved secret manager; do not commit secrets, `.env` files, models, or caches.
- **Prediction Persistence and Data Handling**: NOT APPLICABLE TO THIS FEATURE. Prediction persistence is explicitly out of scope and remains assigned to the MinIO storage feature; this plan does not introduce an alternate store.
- **Security and Safe Failure**: PASS. Validate effective settings at the appropriate boundary and ensure errors/logs omit credentials, tokens, internal paths, and raw user text.
- **Testing and Quality Gates**: PASS FOR THIS FEATURE. Test configuration and logging deterministically without network or large model downloads. MinIO-backed integration coverage belongs to the later storage feature.
- **Observability and Documentation**: PASS. Define structured, non-sensitive log events and document configuration sources, precedence, required service settings, and launch/validation steps in the feature quickstart.

**Pre-research gate**: PASS. No constitutional exception is required. Items marked not applicable are explicitly outside this feature's scope and remain governed by subsequent feature specifications.

**Post-design gate**: PASS. The research, data model, configuration/shell contract, and quickstart preserve the same boundaries and constraints. No unapproved technology, secret source, alternative prediction store, model-loading behavior, or out-of-scope service implementation was introduced.

## Project Structure

### Documentation (this feature)

```text
specs/001-application-foundation-config/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/
├── streamlit_app.py          # Runnable shell and navigation entry point
├── config/
│   ├── settings.py           # Typed application and service settings
│   └── loader.py             # YAML, environment, defaults, and validation
└── utils/
    └── logging_config.py     # Structured, secret-safe logging setup
configs/
└── app.yaml                  # Committed non-secret defaults and configuration example
tests/
├── unit/
│   ├── test_config_loader.py
│   └── test_logging_config.py
└── smoke/
    └── test_app_startup.py
pyproject.toml                # Project metadata and tool configuration
uv.lock                       # Reproducible dependency lock
```

**Structure Decision**: Use a single root-level `app/` package, matching the Streamlit-oriented project structure in the homework brief. Keep configuration models separate from source loading and logging. Future feature specifications may add `app/pages/` and `app/services/` modules for model management, classification, and MinIO storage; this feature must not implement those services. Keep only non-secret defaults in `configs/app.yaml`. Use `pyproject.toml` with a committed `uv.lock` for reproducible dependencies and Ruff/type-checker settings.
