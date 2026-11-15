# Data Model: Deployment Configuration and Operational Evidence

This feature introduces deployment metadata and validation outcomes, not a new prediction schema or application data store.

## Local Deployment Configuration

| Field | Context/source | Validation and meaning |
|---|---|---|
| image identities/platform | reviewed deployment files | immutable digests from research; Linux amd64 |
| project identity | Compose `-p` | stable for local persistence; unique per CI execution |
| APP_CONFIG_FILE | app environment or default | existing explicit-path/YAML validation |
| APP_VERSION | app environment > YAML > default | existing non-empty value rule |
| MODEL_DIR | app environment > YAML > default | Docker `/runtime/models`; native root remains separate |
| HF_HOME | app environment > YAML > default | Docker `/runtime/hf-home` |
| TRANSFORMERS_CACHE | app environment > YAML > default | Docker `/runtime/hub-cache`; preserve existing adapter usage |
| HF_TOKEN | app environment only | optional secret; absent from image/logs |
| HF_HUB_CACHE / XDG_CACHE_HOME | Hugging Face/library environment | Docker `/runtime/hf-home/hub` and `/runtime/xdg-cache`; not extra app YAML keys |
| LABEL_CONFIG_FILE | independently resolved app environment/default | Docker `/runtime/labels/catalog.yaml`; canonical parent/sidecars |
| MINIO_ENDPOINT | app environment > YAML | scheme-free host:port; container `minio:9000`, native `localhost:9000` |
| MINIO_SECURE | app environment > YAML | explicit Boolean; false only for local HTTP, true for TLS |
| MINIO_BUCKET | app environment > YAML > mandated default | exact `zeroshot_learning_output`; rejected names need explicit override |
| MINIO_ACCESS_KEY / MINIO_SECRET_KEY | app environment only | optional for shell; required and validated on storage use |
| MINIO_LICENSE_FILE | deployment host file input | existing readable regular file; mounted `/minio.license` read-only |
| MINIO_ROOT_USER_FILE / MINIO_ROOT_PASSWORD_FILE | deployment host secret-file inputs | external regular files; service receives `/run/secrets/...` paths, not host paths |
| MINIO_TEST_BUCKET | test process environment only | explicit opt-in; isolated valid bucket identity |
| RUN_DEPLOYMENT_TESTS | deployment test process only | `1` explicitly enables container lifecycle validation |
| approved context inputs | root `.dockerignore` source allowlist | one filtered context; approved non-sensitive Python test source copied only into validation target |

Relative native configuration paths resolve from the launch working directory. Empty explicitly provided values do not silently fall through to YAML/defaults. Labels have their own resolver, not an `app.yaml` label section. Library-level cache variables are explicitly located inside Docker's durable runtime; native overrides outside that tree require separately documented backups. The adapter's explicit cache argument remains authoritative for its calls. Do not imply the project loader recognizes every library setting.

Server root secret files must contain only their credential value, without extra whitespace/newlines, per AIStor docs. App inputs are not populated automatically from server settings. No application secret value belongs in the configuration example entity.

## Persistent Resource

| Resource | Docker location | Evidence preserved |
|---|---|---|
| model artifacts/staging/manifests | `/runtime/models` | model ID, revision, ready/interrupted status and provenance |
| model-use locks | `/runtime/.<model-directory-name>.use.lock` | canonical cooperating-process lock identity |
| Hugging Face home | `/runtime/hf-home` | library cache/token-home state; treat token files as secret if created |
| explicit adapter cache | `/runtime/hub-cache` | cached model content/references |
| library hub/XDG caches | `/runtime/hf-home/hub`, `/runtime/xdg-cache` | any additional effective library cache locations |
| label catalog | `/runtime/labels/catalog.yaml` | saved labels and revisions |
| label initialization marker | `/runtime/labels/catalog.yaml.initialized` | first-use vs initialized-loss distinction |
| label lock/temp replacement sidecars | catalog parent | native coordination and atomic update relationships |
| prediction objects | `minio-data` backing `/mnt/data` | configured bucket, `predictions/<request_id>.json` |
| operational probe object | configured bucket, `healthchecks/<probe_id>.json` | temporary fixed-purpose content; exact-key cleanup |

All app file/cache rows live in `app-runtime`; storage data lives in `minio-data`. Container image/root filesystem and session futures are disposable. Secret/license files are external operator-managed resources, not application-volume backups.

**Lifecycle**: initial empty volume -> existing intentional management initialization -> durable operation -> quiesced stop/backup -> restart/recreation with same volume. Removing volume/project identity or changing canonical paths is not a routine lifecycle transition.

Missing catalog with initialization marker remains a recovery error. Neither file nor marker cannot establish that no prior data ever existed; retain existing first-use warning. Backups preserve the whole runtime tree and MinIO's complete data volume while writers are stopped. Restore to the same compatible server/image identities first; do not mix a physical-volume restore with unsupported downgrade assumptions.

## Readiness Result

Fields: component, operation, outcome, safe reason code, safe corrective instruction, optional probe UUID/key, duration, tested endpoint context. Never include secrets, internal filesystem paths, input text, or prediction payload.

Outcomes: `ready`, `unavailable`, `configuration_error`, `rejected`, `indeterminate`, `cleanup_failed`. Node `ready` is scoped to node readiness only. Storage `ready` requires acknowledged PUT, exact readback, and successful owned-key cleanup.

Probe transitions: configuration validated -> unique key allocated -> one write attempted -> acknowledged -> readback verified -> own-key removed -> ready. Rejection terminates with failure. A timeout/disconnect during write becomes indeterminate, not absent. Cleanup failure fails and retains inspection metadata.

## Validation Result

Fields: check ID, environment/runner, image/lock identities, command, eligibility, prerequisite reason, executed Boolean, pass/fail/skip outcome, safe evidence reference, cleanup outcome.

Test execution resources: unique project identity, captured owned container IDs, verified owned network ID/aliases, project-scoped volume IDs, unique helper image tags, and explicitly selected valid test bucket. These are fixture/CI metadata, not new application environment settings. Host port bindings must be empty for automated service fixtures; clients use `app:8501`/`minio:9000` only on the owned network. Runtime and validation image identities share the same controlled source-context policy but different COPY/dependency targets.

Transitions: allocate test identity -> create owned no-port service containers -> verify project/network/port ownership -> run internal probes/record test -> capture outcome -> clean exact owned resources. Startup/ownership verification failure must terminate before a write; never resolve it by probing host localhost or stopping a preexisting service. Lifecycle fixtures preserve owned volumes when recreating owned containers; cleanup never changes operator volumes.

Constraints: skip requires an identified missing external prerequisite before execution; configured-invalid prerequisites or executed failures are failures. Required failed checks propagate nonzero exit. Mock checks cannot be labeled service-backed. Record unrun reviewer/accessibility/full-model checks distinctly. Context exclusion evidence must inspect the actual filtered inputs as well as runtime/validation image contents; image COPY selection alone is not context-exclusion evidence.

## Developer Guide

Fields: topic, existing module/config contract, supported environment, runnable command, expected result, safe recovery instruction, actual validation reference/status. The README is the primary entry point; feature quickstarts supply detailed validation contracts.

Required topics are FR-021 through FR-025. Commands distinguish PowerShell host syntax from Linux container paths. No guide instructs publishing secrets, license contents, raw text, or prediction records in support channels.

## Unchanged Prediction Contract

Continue feature 004's `predictions/<UUID>.json` and complete record fields: request ID, input text, predicted class/score, candidate labels, ranked results, model name/identifier/revision, timestamp, and application version. Its potentially sensitive content is inspected only by authorized operators. Operational probes are not predictions and cannot satisfy classification success.
