# Quickstart: Application Foundation and Configuration

## Prerequisites

- Python 3.11 or later.
- `uv` installed and available on `PATH`.
- No Hugging Face token or MinIO service credentials are required to start the application shell.
- The commands below select Python 3.12, which is within the project's supported Python 3.11+ range.

## Sync the locked environment

From the repository root. On Windows, place the virtual environment on a local drive if the repository is on a network or quota-limited drive:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:LOCALAPPDATA "uv\venvs\zero-shot-text-classification"
uv sync --python 3.12 --locked
```

Expected result: the project environment is synchronized from `pyproject.toml` and the committed `uv.lock`. The command fails rather than silently changing the lock if the files disagree.

## Start the application shell

```powershell
uv run --python 3.12 --locked streamlit run app/streamlit_app.py
```

Open the local address printed by Streamlit. The initial page must render without model or MinIO credentials.

## Validate configuration behavior

Run the deterministic foundation tests:

```powershell
uv run --python 3.12 --locked pytest tests/unit tests/smoke
```

Expected coverage includes environment-over-YAML-over-default precedence, documented defaults, missing and malformed settings, deferred service validation, and safe errors/logs. These tests must not download models or contact MinIO.

Run static checks:

```powershell
uv run --python 3.12 --locked ruff check .
uv run --python 3.12 --locked ruff format --check .
$env:MYPY_CACHE_DIR = Join-Path $env:LOCALAPPDATA "mypy-cache\zero-shot-text-classification"
uv run --python 3.12 --locked mypy --cache-dir $env:MYPY_CACHE_DIR app
```

## Configuration inputs

The default non-secret YAML file is `configs/app.yaml`; `APP_CONFIG_FILE` can select another path. Environment variables override matching YAML values. Example non-secret local values include `APP_VERSION`, `MODEL_DIR`, `HF_HOME`, `TRANSFORMERS_CACHE`, and `MINIO_BUCKET`. The bucket defaults to `zeroshot_learning_output`.

Do not put credentials in the YAML file. Supply `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, or an optional `HF_TOKEN` through the process environment or an approved secret manager. MinIO endpoint and transport settings are validated when the storage service is used, not when the shell starts.

## Expected outcomes

- A valid shell-level configuration opens the initial page.
- Environment values override YAML values; documented defaults apply only when neither source provides a value.
- Invalid YAML or a malformed shell-level value produces a safe, actionable error.
- Missing MinIO credentials do not prevent shell startup; using MinIO without its required settings produces a service-scoped configuration error.
- Logs contain no credential values, tokens, raw user text, or absolute local paths.
