# Configuration and Application Shell Contract

## Configuration sources

Configuration resolution order is:

1. Explicitly supported environment variable.
2. Corresponding non-secret value in the selected YAML file.
3. Documented default, when one exists.

Environment variables override YAML values. Secret values are accepted only from environment variables or an approved secret manager; committed YAML must not contain credentials or tokens. The loader maps supported variables explicitly and does not dump the process environment into logs.

The default YAML path is `configs/app.yaml`. `APP_CONFIG_FILE` may select another path. If the default file is absent, configuration may resolve from environment values and defaults. If a path was explicitly selected and does not exist, report a configuration error. Invalid YAML syntax or a non-mapping document prevents startup with an error that omits absolute paths and sensitive values.

## Supported settings

| Setting | YAML key | Environment variable | Default / validation time |
|---|---|---|---|
| Application version | `app.version` | `APP_VERSION` | `0.1.0`; application scope |
| Model directory | `model.model_dir` | `MODEL_DIR` | `./models`; validate when model service is used |
| Hugging Face cache root | `model.hf_home` | `HF_HOME` | `./.cache/huggingface`; validate when model service is used |
| Transformers cache | `model.transformers_cache` | `TRANSFORMERS_CACHE` | `./.cache/huggingface/transformers`; validate when model service is used |
| Hugging Face token | Not permitted in committed YAML | `HF_TOKEN` or approved secret manager | Optional future service secret; never required for shell startup |
| MinIO endpoint | `minio.endpoint` | `MINIO_ENDPOINT` | No default; required when MinIO is used |
| MinIO secure transport | `minio.secure` | `MINIO_SECURE` | No default; explicit when MinIO is used; production uses TLS when supported |
| MinIO bucket | `minio.bucket` | `MINIO_BUCKET` | `zeroshot_learning_output`; MinIO scope |
| MinIO access key | Not permitted in committed YAML | `MINIO_ACCESS_KEY` or approved secret manager | Required when MinIO is used; secret |
| MinIO secret key | Not permitted in committed YAML | `MINIO_SECRET_KEY` or approved secret manager | Required when MinIO is used; secret |

Boolean environment values must accept only documented true/false spellings; malformed values are rejected rather than silently coerced. Unknown YAML keys are reported as configuration errors to catch misspellings.

## Application shell behavior

- The application starts and renders its initial Streamlit page without model or MinIO credentials.
- Application-level configuration is validated at startup. Model and MinIO settings are validated only when their respective service is initialized or used.
- A configuration failure identifies the setting and corrective action without showing secret values, raw user text, or absolute local paths.
- The shell uses the centralized configuration boundary; UI pages do not read environment variables directly.
- This feature exposes no public HTTP API and performs no inference or prediction write.

## Logging behavior

Logs use stable event names and an allow-list of non-sensitive structured fields. They must not include credentials, tokens, raw user text, full configuration objects, or absolute paths. Configuration values are not emitted merely to aid debugging.
