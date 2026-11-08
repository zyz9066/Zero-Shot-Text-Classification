# Quickstart: Model Lifecycle Management

## Prerequisites

- Python 3.11 or later and `uv` available on `PATH`.
- Feature 001 application foundation configured and runnable.
- Network access to the Hugging Face Hub for first-time public model downloads.
- Sufficient free disk space for the Hub cache and a separate app-managed model copy. A download stages a copy before marking the model ready.
- No Hugging Face token is required for the two initial public models. Configure `HF_TOKEN` externally only when accessing a restricted model.

## Sync the locked environment

From the repository root, synchronize the environment after planning implementation dependencies:

```powershell
uv sync --python 3.13 --locked
```

## Configure the model catalog and storage locations

The model catalog is `configs/models.yaml`. It contains non-secret model identifiers, display names, task, and optional revision. The initial catalog includes:

- `MoritzLaurer/deberta-v3-base-zeroshot-v2.0`
- `facebook/bart-large-mnli`

Runtime paths continue to come from feature 001's centralized settings. Defaults are `MODEL_DIR=./models`, `HF_HOME=./.cache/huggingface`, and `TRANSFORMERS_CACHE=./.cache/huggingface/transformers`; environment variables override documented YAML values. Keep model files, caches, tokens, and credentials out of Git.

## Start the application

```powershell
uv run --python 3.13 --locked streamlit run app/streamlit_app.py
```

Open the local URL printed by Streamlit and navigate to Model Management. Application startup must not contact the Hub or require a token.

## Verify model lifecycle behavior

1. Inspect both configured models and their local availability/revision information.
2. Request a missing public model and verify that progress is shown and the model is marked ready only after completion.
3. Refresh the catalog and request the same ready model again; it must not start another download.
4. Exercise interrupted/failed download handling with automated tests; partial contents must not appear ready.
5. Request deletion of a selected local model, cancel once to verify no change, then confirm and refresh availability.
6. Request cache cleanup and review the preview/scope. Cancel once to verify no change. After confirmation, verify that app-managed models and HF authentication state remain intact while the configured Hub cache is cleaned.

## Run automated checks

Tests must use mocks or temporary directories and must not download full models or contact the Hub:

```powershell
uv run --python 3.13 --locked pytest tests/unit tests/smoke
uv run --python 3.13 --locked ruff check .
uv run --python 3.13 --locked ruff format --check .
$env:MYPY_CACHE_DIR = Join-Path $env:LOCALAPPDATA "mypy-cache\zero-shot-text-classification"
uv run --python 3.13 --locked mypy --cache-dir $env:MYPY_CACHE_DIR app
```

## Expected outcomes

- Model catalog configuration is validated without requiring Hub access at application startup.
- Model state is derived from the app-managed model directory and completion manifest.
- A missing model can be downloaded at its resolved immutable revision; repeated requests reuse an active/completed operation.
- Interrupted/failed downloads are recoverable and never shown as ready.
- Model deletion and Hub-cache cleanup are separate, explicitly confirmed operations with distinct effects.
- Cache cleanup uses the configured Hub cache only; it does not remove `MODEL_DIR`, the broader `HF_HOME` directory, or credentials.
- Errors are actionable and do not expose tokens or sensitive paths.
