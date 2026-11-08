# Data Model: Model Lifecycle Management

This feature adds no database and does not persist predictions. It introduces a non-secret model catalog, an app-managed model installation manifest, and transient operation/cleanup state.

## ConfiguredModel

A non-secret entry in the configured model catalog.

| Field | Meaning | Validation |
|---|---|---|
| `model_id` | Hugging Face model repository identifier | Required, non-empty repository ID; unique in the catalog |
| `display_name` | Human-readable catalog label | Required, non-empty |
| `task` | Model task | Required; the initial catalog uses `zero-shot-classification` |
| `requested_revision` | Optional branch, tag, or commit requested by the catalog | Optional non-empty string |

Initial entries are `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` and `facebook/bart-large-mnli`.

## ModelInstallationManifest

Non-secret metadata written only after a model snapshot is completely materialized in the app-managed model directory.

| Field | Meaning |
|---|---|
| `model_id` | Configured Hub repository identifier |
| `requested_revision` | Catalog revision, or null when the default was requested |
| `resolved_revision` | Immutable commit SHA actually downloaded |
| `completed_at` | UTC timestamp for completed installation |

The manifest is not committed to Git. An installation is considered ready only when its app-managed directory contains a valid manifest for the configured model. An incomplete staging directory never counts as an installation.

## ModelAvailability

An observable status for a configured model, derived from catalog configuration, local model files/manifest, and any active operation.

| State | Meaning |
|---|---|
| `configured` | Catalog entry is valid; local installation has not yet been checked |
| `missing` | No complete app-managed installation exists |
| `downloading` | A download/materialization operation is active for this model |
| `ready` | Complete app-managed model and valid manifest exist |
| `failed` | The most recent operation failed; partial artifacts are not ready |

The exact in-memory representation is an implementation detail. Refreshing status must not require a Hub request for already installed models.

## ModelOperation

Transient, in-process state for a download, deletion, or cache-cleanup request.

| Field | Meaning |
|---|---|
| `operation_id` | Unique identifier for this operation |
| `kind` | `download`, `delete`, or `cache_cleanup` |
| `model_id` | Model identifier for model-scoped operations; absent for whole-cache cleanup |
| `requested_revision` | Requested revision for a download, if any |
| `resolved_revision` | Immutable revision resolved for the operation, if available |
| `state` | `queued`, `running`, `succeeded`, `failed`, or `cancelled` |
| `progress` | Optional progress fraction/count when available from the download operation |
| `safe_message` | User-facing status that excludes credentials, tokens, and sensitive local paths |

The operation registry is process-local and thread-safe. A second request for the same model while it is downloading reports the existing operation instead of starting another download.

## CacheCleanupPreview

Ephemeral preview data shown before the administrator confirms cache cleanup.

| Field | Meaning |
|---|---|
| `cache_scope` | The configured `TRANSFORMERS_CACHE` target, displayed to the trusted administrator |
| `repository_count` | Number of cached repositories in scope when discoverable |
| `revision_count` | Number of cached revisions in scope when discoverable |
| `expected_freed_bytes` | Estimated freed space when available |
| `incomplete_download_count` | Number of leftover partial downloads when discoverable |

The preview contains no token or secret. Executing cleanup requires separate explicit confirmation and uses Hugging Face cache-management APIs rather than deleting arbitrary files.

## State and lifecycle rules

- A catalog entry begins as `configured` and resolves to `missing` or `ready` after local inspection.
- A download transitions `missing` -> `downloading` -> `ready` only after a complete app-managed copy and manifest are in place; failure transitions to `failed` and leaves no ready marker for partial content.
- A repeated request for the same model while `downloading` returns/reports the active operation and does not create another download.
- A confirmed deletion removes only the selected app-managed model directory and its manifest; the Hub cache remains separate.
- A confirmed cache cleanup removes cached Hub revisions/partials in the configured cache target; it does not remove app-managed installations or the broader `HF_HOME` root/token.
