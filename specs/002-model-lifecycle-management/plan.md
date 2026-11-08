# Implementation Plan: Model Lifecycle Management

**Branch**: `002-model-lifecycle-management` | **Date**: 2026-11-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-model-lifecycle-management/spec.md`

## Summary

Add a configuration-driven model catalog and a trusted-environment administration workflow for inspecting local model state, downloading complete snapshots, safely deleting app-managed model copies, and clearing Hub cache revisions. Reuse feature 001 settings and keep the catalog, model-operation service, Hub adapter, and Streamlit page in separate testable boundaries. Resolve Hub revisions to immutable commits, stage and verify each download, and only then promote its independent copy into `MODEL_DIR`.

## Technical Context

**Language/Version**: Python 3.11 or later.

**Primary Dependencies**: Existing Streamlit, PyYAML, pytest, Ruff, and mypy; add `huggingface_hub` as the feature's direct Hub API dependency. Do not add PyTorch or Transformers until a later feature loads or runs a model.

**Storage**: Non-secret model catalog in `configs/models.yaml`; completed app-managed model copies and provenance manifests under the configured `MODEL_DIR`; Hub snapshots under the configured `TRANSFORMERS_CACHE`; no database or prediction storage.

**Testing**: pytest unit tests and Streamlit AppTest smoke coverage. Use mocked Hub operations and temporary directories; no full model downloads, credentials, or network access in automated tests.

**Target Platform**: Local Python 3.11+ development environments, including Windows.

**Project Type**: Single-package Streamlit application with internal configuration and service boundaries; no public HTTP API.

**Performance Goals**: Keep application startup independent of the Hub and model downloads. Downloads may take substantial time and must report meaningful progress; no fixed download-duration target is specified.

**Constraints**: Reuse `load_model_settings`; maintain distinct app-managed model and Hub-cache locations; resolve and retain immutable revisions; avoid duplicate in-flight downloads for a model; do not load models or require MinIO credentials at startup; never enable `trust_remote_code`; preserve the local/trusted admin boundary.

**Scale/Scope**: Two initial configured public models with a catalog extensible by configuration; one local application process and trusted administrator; no multi-process coordination, production availability, or concurrent-user service-level target is specified.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Mandated Technology Stack**: PASS. Retain the Python and Streamlit application and use Hugging Face Hub APIs for model repository operations. PyTorch and Transformers model loading remain with the later inference feature; MinIO prediction persistence is outside this scope.
- **Python Quality and Dependency Management**: PASS. Keep Python 3.11+, the isolated uv environment and lock, Ruff, mypy, and type annotations at service boundaries; add only the Hub dependency required here.
- **Reproducible Model Use**: PASS. Resolve a requested or default revision to an immutable commit and retain it with the installed model. Never enable `trust_remote_code`; do not download full models in unit tests.
- **Modular Boundaries**: PASS. Keep Streamlit presentation, catalog validation, model lifecycle orchestration, Hub operations, and configuration as distinct boundaries.
- **Streamlit Lifecycle and State**: PASS. Add routing through `st.Page` and `st.navigation`. Any globally shared model-operation manager must be thread-safe; do not cache mutable progress/results with `st.cache_data`.
- **Configuration and Secrets**: PASS. Reuse feature 001 model/cache settings. Keep the model catalog non-secret, use external HF credentials only when needed, and preserve local artifacts, caches, and tokens from Git.
- **Prediction Persistence and Data Handling**: NOT APPLICABLE. This feature creates no classification predictions and introduces no alternate prediction store.
- **Security and Safe Failure**: PASS. Validate model identifiers and paths, constrain deletion to the app-managed model root, require separate confirmation for destructive operations, and keep tokens and sensitive paths out of logs/errors.
- **Testing and Quality Gates**: PASS. Cover state transitions, duplicate requests, path safety, cache cleanup, and failure paths with deterministic tests; run the existing lint, formatting, typing, unit, and smoke gates.
- **Observability and Documentation**: PASS. Log operation names, safe identifiers/outcomes, and non-sensitive metadata. Document setup, model provenance, cache behavior, destructive-operation impact, tests, and known local-admin limitations.

**Pre-research gate**: PASS. No constitutional exception is required. Prediction persistence, authentication, and inference are expressly out of scope.

## Project Structure

### Documentation (this feature)

```text
specs/002-model-lifecycle-management/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── spec.md
```

No `contracts/` directory is planned: this feature exposes no public service/API contract; its user interaction is an internal Streamlit workflow.

### Source Code (repository root)

```text
app/
├── streamlit_app.py                 # Register and run the model-management page
├── config/
│   ├── loader.py                    # Reuse model runtime settings from feature 001
│   └── model_catalog.py             # Parse and validate non-secret catalog entries
├── pages/
│   └── model_management.py          # Admin-only-by-trust-boundary management UI
└── services/
    ├── model_manager.py             # Availability, operation state, install/delete/cache workflows
    └── huggingface_hub_adapter.py    # Revision lookup, snapshots, cache inspection/deletion
configs/
└── models.yaml                      # Initial configured model catalog
tests/
├── unit/
│   ├── test_model_catalog.py
│   ├── test_model_manager.py
│   └── test_huggingface_hub_adapter.py
└── smoke/
    └── test_model_management.py
pyproject.toml                       # Add Hub dependency if needed
uv.lock                              # Resolve and commit updated dependency lock
```

**Structure Decision**: Extend the existing single `app/` package. The entry point owns one `st.navigation` call; a page handles user interaction; a manager coordinates safe operations; a Hub adapter isolates external API and cache behavior. Keep the catalog in a separate YAML file because feature 001's application YAML loader intentionally rejects unknown root keys. Load runtime directories and optional token through the existing `load_model_settings` API.

Downloads use `huggingface_hub` to resolve the requested/default revision and download a full snapshot into the configured Hub cache. The application then copies that complete snapshot into a staging directory beneath `MODEL_DIR`; after verification, it atomically promotes the staging directory and writes a non-secret provenance manifest. This deliberate copy keeps app-managed models available when the Hub cache is cleared, at the cost of temporary extra disk space. Existing complete models are not replaced by a failed operation.

The manager keeps an in-process, thread-safe operation registry keyed by model identity/revision so concurrent Streamlit sessions can observe one in-progress download instead of starting duplicates. Progress callbacks feed status to the page. Catalog and ready state are derived from validated configuration and local manifests, not a Hub request on every page rerun.

Cache cleanup scans only the configured `TRANSFORMERS_CACHE` repository cache and uses Hugging Face cache deletion strategies to preview and safely remove its revisions/shared blobs. It does not recursively remove `HF_HOME`, the external token, or `MODEL_DIR`. If the configured cache path is missing or unreadable, cleanup reports an actionable cache-availability error and does not broaden its target; if the path exists but contains no entries, it reports that nothing needs clearing. The model-directory deletion path is independently validated to remain under `MODEL_DIR`.

The existing `.gitignore` already excludes `models/`, `.cache/huggingface/`, and `.env*`; implementation must verify these rules remain sufficient. Do not add persistence or a public API.

**Post-design gate**: PASS. The research, data model, and quickstart preserve the Constitution's stack, revision provenance, service boundaries, cache/secret safeguards, trusted-environment limitation, and deterministic testing requirements. Cache cleanup is bounded to configured Hub repository cache locations and uses cache-aware deletion; app-managed model copies and HF authentication state remain separate. No unapproved technology, alternate prediction store, model inference, authentication system, or constitution exception is introduced.
