# Feature 2: Model Lifecycle Management Plan

Use this as the `/speckit.plan` input after feature 002 has been clarified:

```text
/speckit.plan Create the technical implementation plan for the Model Lifecycle Management feature in the current specification, `specs/002-model-lifecycle-management/spec.md`.

Implement it in the existing Python 3.11+ project using the constitution's required stack. Reuse the centralized model and cache settings from feature 001 (`app.config.settings.ModelRuntimeSettings` and `app.config.loader.load_model_settings`) rather than defining duplicate configuration or reading environment variables throughout the UI.

Architecture and technology decisions

- Keep the existing Streamlit application and add a dedicated model-management page. Use `st.Page` and `st.navigation` for new multipage routing. Keep page code focused on presentation and delegate catalog, download, availability, deletion, and cache operations to separately testable services.
- Store the non-secret model catalog in configuration. Include the two required model identifiers and the zero-shot classification task. Preserve catalog extensibility and allow an optional requested revision.
- Use the Hugging Face Hub Python client for model metadata, revision resolution, and downloads. When the catalog omits a revision, download the upstream default and retain the resolved immutable revision when available. Do not enable `trust_remote_code`.
- Keep app-managed model artifacts under the configured model directory and Hugging Face's download cache under its existing configured cache location(s). They are distinct storage scopes and must not be conflated.
- Model operations must expose clear configured, missing, downloading, ready, and failed/incomplete states. Concurrent requests for the same model and revision must share/report the active operation rather than start duplicate downloads.
- Plan a recoverable download lifecycle: stage downloads so partial results are not visible as ready, verify successful completion, and promote completed artifacts safely. Preserve an already complete model if a replacement or retry fails. Resolve an appropriate atomicity and metadata strategy in `research.md`.
- Model deletion must require an explicit UI confirmation, resolve the selected target beneath the configured model directory, and never delete arbitrary paths or Hugging Face cache contents as a side effect.
- Cache cleanup must require a separate explicit confirmation. In `research.md`, define exactly which configured cache paths are cleared and how credentials, tokens, unrelated files, and app-managed model artifacts are preserved. Do not recursively clear a broad home directory without a bounded, user-visible scope.
- Keep administrative actions limited to the local/trusted environment described by the spec. Do not add authentication, authorization, candidate-label management, inference, or MinIO prediction persistence.

Configuration and dependencies

- Extend the existing model configuration contract without changing feature 001's application startup behavior or requiring a Hugging Face token to start the shell.
- Add only dependencies needed by this feature; use `huggingface_hub` for Hub operations. Defer PyTorch/Transformers runtime loading to the later inference feature unless research demonstrates that this feature needs them.
- Update `pyproject.toml` and `uv.lock` reproducibly. Preserve the existing Python minimum and lint/type-check conventions.
- Confirm `.gitignore` excludes model artifacts, Hugging Face caches, and local secret files; do not commit downloaded weights or credentials.

Testing and validation

- Add deterministic unit tests for catalog validation, revision handling, availability, duplicate in-flight requests, deletion path safety, cache cleanup scope, and failure recovery.
- Use temporary directories, mocks, or lightweight fixtures. Tests must not require network access, credentials, or full model downloads.
- Add integration coverage only where it meaningfully verifies the configured local model/cache boundaries; document any environment-dependent manual smoke test in `quickstart.md`.
- Provide a quickstart that describes catalog configuration, local model/cache locations, download/status behavior, deletion, cache cleanup consequences, relevant environment variables, tests, and expected outcomes without documenting out-of-scope inference workflows.

Generate the plan and the normal Spec Kit design artifacts (`research.md`, `data-model.md`, any justified contracts, and `quickstart.md`). Map each acceptance scenario and functional requirement to design elements and validation. Recheck all constitution principles before and after design. Keep all work within the scope of the current model lifecycle specification; do not modify application implementation, generate `tasks.md`, or implement the feature in this planning step.
```
