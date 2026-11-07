# Data Model: Application Foundation and Configuration

This feature introduces no persistent business records or database. The following are in-memory configuration and diagnostic concepts.

## ConfigurationSource

Represents a value supplied to the configuration resolver.

| Attribute | Meaning |
|---|---|
| `kind` | `environment`, `yaml`, or `default` |
| `setting_name` | Canonical setting key, such as `model_dir` or `minio.bucket` |
| `value` | Candidate value; sensitive values are never included in diagnostic representations |
| `precedence` | Environment first, then YAML, then documented default |

## EffectiveApplicationSettings

Validated settings required to render the initial application shell.

| Attribute | Meaning |
|---|---|
| `app_version` | Version displayed or included in non-sensitive diagnostics; default `0.1.0` |
| `config_file` | Selected YAML path; never exposed as an absolute path in user-facing errors or logs |

The shell must not require model or MinIO credentials. This group may be created even when service-specific credentials are absent.

## ModelRuntimeSettings

Configuration consumed by the future model lifecycle and inference services.

| Attribute | Meaning |
|---|---|
| `model_dir` | Local model directory; default `./models` |
| `hf_home` | Hugging Face cache root; default `./.cache/huggingface` |
| `transformers_cache` | Transformers cache location; default `./.cache/huggingface/transformers` |
| `hf_token` | Optional external secret for future model access; excluded from representations and logs |

These values are resolved centrally and validated when the model service is initialized or used, not to render the shell.

## MinIOServiceSettings

Configuration consumed by the future MinIO storage service.

| Attribute | Meaning |
|---|---|
| `endpoint` | MinIO endpoint; required when the service is used |
| `secure` | Explicit transport-security choice; production uses TLS when supported |
| `bucket` | Bucket name; default `zeroshot_learning_output` |
| `access_key` | External secret; required when the service is used and excluded from representations/logs |
| `secret_key` | External secret; required when the service is used and excluded from representations/logs |

MinIO settings are not required to render the shell. No MinIO client or prediction persistence is implemented by this feature.

## ConfigurationValidationIssue

A safe diagnostic produced when a source or effective setting is invalid.

| Attribute | Meaning |
|---|---|
| `setting_name` | Name of the missing or invalid setting |
| `source_kind` | Source that supplied the invalid value, when known |
| `message` | Correction-oriented text with no secret value, raw input, or absolute path |
| `scope` | `application`, `model`, or `minio`; identifies when validation applies |

## OperationalLogEvent

A structured diagnostic event emitted by the foundation.

| Attribute | Meaning |
|---|---|
| `event_name` | Stable event identifier, such as application startup or configuration validation failure |
| `severity` | Standard logging severity |
| `setting_name` | Optional non-sensitive configuration key |
| `source_kind` | Optional environment/YAML/default origin |
| `outcome` | Success or failure category without sensitive payloads |

Raw user text, credentials, tokens, complete configuration objects, and absolute local paths are excluded.

## Relationships and lifecycle

- A `ConfigurationSource` contributes candidate values to one `EffectiveApplicationSettings`, `ModelRuntimeSettings`, or `MinIOServiceSettings` object.
- Each effective setting retains its source only as non-sensitive diagnostic metadata; the resolved values themselves remain in process memory and are not persisted by this feature.
- `ConfigurationValidationIssue` is returned or raised at the validation boundary for its scope and is converted to a safe UI message or `OperationalLogEvent`.
- `OperationalLogEvent` may reference a setting name and source kind, but never its value.
