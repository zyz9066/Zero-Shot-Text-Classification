# Deployment and Operational Contracts

These contracts define implementation interfaces, not existing delivered deployment commands.

## 1. Compose topology

| Address | Consumer | Purpose |
|---|---|---|
| `http://localhost:8501` | local browser | Streamlit |
| `http://localhost:9000` | native app/operator | S3 API |
| `http://localhost:9001` | local browser/operator | MinIO Console, not S3 API |
| `minio:9000`, secure false | Compose app | internal S3 API |

All published host ports explicitly bind `127.0.0.1`. Containers use Linux absolute paths, not Windows paths. DNS `minio` exists only when the storage overlay is running in the same Compose project/network.

Base `compose.yaml` must validate/start app without any storage license or root-credential files. Storage overlay requires valid file inputs; it does not gate app health. App environment variables retain existing names/precedence. `.env.example` is non-secret; real `.env` files are untracked and are not preferred for secrets.

The existing app launcher remains `uv run --locked streamlit run app\streamlit_app.py` on native PowerShell. Container runtime invokes the installed Streamlit command against `app/streamlit_app.py`, without unlocked startup installation.

## 2. File and secret provisioning

Deployment-only host variables identify license and root-credential files. The license bind uses `create_host_path: false`; both file secrets must exist. The server receives `MINIO_ROOT_USER_FILE=/run/secrets/minio-root-user` and `MINIO_ROOT_PASSWORD_FILE=/run/secrets/minio-root-password`.

Credentials never appear in build args, Dockerfile, image layers, test reports, or source. App credentials are supplied explicitly as existing environment variables; they are not server variables and not automatically copied. Docker inspection is a trusted-administrator boundary, not secret isolation from the host administrator.

Both targets build from the root context using one root `.dockerignore`; no additional named test context is supplied. Start deny-by-default, allow necessary directory ancestors and explicitly approved app/test Python source, manifests, selected non-secret configuration, Dockerfile and diagnostic tooling, and retain exclusions for generated/secret sidecars. Never broadly admit an entire tests directory or unlisted source file. Exclude model weights, caches/bytecode, catalogs, `.env` files, licenses, secret files, logs, runtime/backups and specs. Only the validation target copies approved tests and installs dev tools; runtime COPY inputs exclude tests.

Context tests must use generated forbidden sentinels in a disposable context copy, including under `tests/`, and inspect actual filtered build inputs as well as both final targets. Runtime image contents alone do not prove what was sent to the builder. Do not pass real credentials/license contents to any build or commit secret-like sentinel values into test source.

## 3. Diagnostic CLI

Planned command: `python scripts/check_deployment.py <subcommand>`.

| Subcommand | Inputs | Observable contract |
|---|---|---|
| `preflight` | deployment file-input environment | offline validation of required readable regular files; no contents/path disclosure or claim of license authenticity |
| `health --component app` | optional `--url`, default local app health | bounded GET to `/_stcore/health`; app shell only |
| `health --component minio` | optional `--url`, default local API | bounded HEAD to `/minio/health/live` and `/minio/health/ready`; reports process/node scope, not S3 permission |
| `storage --write-probe` | existing MinIO app settings | explicit one-write exact-readback/owned-key-delete probe |

URLs are operator-supplied trusted inputs with HTTP/HTTPS validation. Health network requests have a 5-second timeout and no retries. Storage uses the existing no-retry client (5-second connect/30-second read timeouts); no polling loop or indefinite recovery wait. CLI input validation is typed and tested independently.

Output is safe structured JSON: `component`, `operation`, `outcome`, `reason_code`, `next_action`, optional `probe_id`/`object_key`. No resolved secrets, raw exception strings, license contents, internal paths, input, or prediction payload. Invalid CLI syntax uses argparse nonzero behavior. Operational result exits: 0 ready, 1 failed/indeterminate/cleanup-failed, 2 invalid invocation/configuration.

Reason codes/actions include:

| Condition | Safe next action |
|---|---|
| Docker unavailable/port occupied | start supported runtime or release the local port; preserve volumes |
| missing/unreadable/directory license input | obtain readable regular license file, fix external mount, rerun preflight |
| license rejection/operation denial | inspect authorized Console/license status; obtain valid license; do not infer usability from port response |
| missing app credential | supply named app environment setting in launch terminal, recreate app |
| credential rejection | verify credentials and app/server variable distinction; do not print values |
| unreachable endpoint | start server and verify native/container/API address |
| TLS mismatch | align secure setting with actual API scheme/certificates; no TLS-validation bypass |
| invalid bucket | explicitly configure a valid bucket, retain original/default otherwise |
| permission denied | grant authorized least-privilege bucket/object rights or pre-provision bucket |
| write uncertainty | inspect exact key; no blind retry or routine cleanup |
| cleanup failure | inspect/remove only acknowledged probe key when authorized; report failure |

S3 access-denied alone may not distinguish credential policy from license denial. Report the evidence-supported category and direct authorized license/permission inspection; never guess a definitive license cause from an ambiguous response.

### Storage probe identity and cleanup

Use new UUID `probe_id` and key `healthchecks/<probe_id>.json`; JSON has only that ID and fixed purpose text. Never use user content or prediction keys. Preserve exact configured bucket; no underscore correction. If bucket is absent, explicitly attempt authorized creation using the same bucket and report rejection; never remove the bucket.

One PUT, no automatic retry. Only an acknowledged exact object is eligible for routine cleanup. Read back with a limit of expected content length plus one byte, reject extra/different content, compare full probe JSON, and release response resources. Readback failures after acknowledged write still permit exact-key cleanup, with the original failure retained. A cleanup failure remains nonzero. An indeterminate PUT must not trigger unconditional DELETE or a second PUT.

## 4. Request recovery and authorized inspection

Record the request UUID from the UI, and inspect `predictions/<request_id>.json` in the explicitly configured bucket through the authorized Console/API. Do not change or delete it while resolving uncertainty. Matching complete record means no resubmission.

NoSuchKey must be an authenticated, authoritative response from the correct bucket/endpoint, not an access-denied response, UI filter mistake, TLS/connectivity failure, or wrong credentials. Absence alone is insufficient: separately establish the original worker/request cannot still finish and any issued storage operation has reached a definitive outcome. Process restart alone does not establish remote non-completion. If no definitive evidence exists, defer retry and escalate to an authorized operator. Do not prescribe a universal timeout.

Authorized payload inspection is local and private. Logs/support reports contain request UUID, safe category, and version/context only, never text, credentials, or JSON records.

## 5. Non-destructive lifecycle and backup

Local project identity is `zeroshot-local`. Ordinary operations use the same two file flags and project identity. `stop` preserves containers/volumes; `start` restarts them; `up --force-recreate` recreates with the same volumes; `down` removes containers/network, not named volumes. Never include `--volumes` in routine commands.

Before stopping writers, let acknowledged work finish where possible and resolve/defer uncertain writes as above. After shutdown, quiesced backup exports the entire app-runtime and MinIO data volumes using a reviewed pinned utility image, preserves directory relationships/metadata, stores archives outside source, and records image identities. Use `docker compose ... run --rm --no-deps` or a dedicated helper with explicitly resolved volume mounts only after confirming writers are stopped. Restore into new verified local volumes on a compatible image/server version, verify ownership and provenance/markers, then enable writers. Do not promise live physical MinIO backups.

Cross-environment transfers stop all native/container writers, preserve model manifests and catalog initialization evidence, and never enable concurrent sharing. Ready-model usability must be revalidated at the destination. Do not automatically merge catalogs or claim stale cross-platform locks are usable as native live locks.

Destructive reset requires an explicit warning, resource inventory and operator confirmation of the exact project-owned volumes. It is not a recovery instruction. No global prune, wildcard resource deletion, or bucket deletion.

## 6. CI execution contract

Quality checks: locked dependency install; `ruff check`; `ruff format --check`; `mypy app scripts/check_deployment.py`; pytest unit/smoke and both concurrency files. Failed required commands fail the job. No full models/external model-service traffic.

Storage job: unique CI project, isolated selected AIStor instance/volume, external permitted license, generated test-only credentials and valid test bucket. Use the isolation fixture in `tests/integration/test_deployment.py:test_isolated_prediction_storage`, which executes the existing `tests/integration/test_prediction_storage.py` in the validation image on the owned network. Observe a complete saved record and exact cleanup. Do not address the developer's local port/service or reuse a preexisting bucket.

Missing runtime/license eligibility yields visible `SKIPPED: <specific prerequisite>` and the quickstart's local alternative. A configured-invalid license or executed failure is nonzero failure, never skip. CI should not expose secrets to untrusted forks; lack of those secrets is an explicit eligibility reason. Container/image build checks do not require a license.

Validate skip/failure branches, normal fail propagation, and cleanup with unrelated sentinel resources. Record test outcomes and actual selected server/client identities. Service-backed integration and full browser/model walkthrough are distinct evidence.

## 7. Automated test isolation (U1)

Fixtures in `tests/integration/test_deployment.py` and CI use a new UUID-scoped project/container/image/bucket identity per run. The fixture chooses the app-only base file or base-plus-MinIO overlay according to the case; it does not cause server secret interpolation for app-only tests.

Start each required service with `docker compose run -d --no-deps --use-aliases --name <owned-name> SERVICE`, without `--service-ports` or `--publish`. Normal service volumes/configuration are retained but no host ports are published. Capture exact container IDs; verify `com.docker.compose.project` labels, the actual attached network's ownership and empty port bindings before connecting. Permit one owned live container per service alias. Ownership mismatch or failed startup is a failure, never a reason to connect to an existing service.

Attach the uniquely tagged validation image only to that verified network. Health URLs are `http://app:8501` and `http://minio:9000`; storage uses `MINIO_ENDPOINT=minio:9000`, explicit local HTTP, explicit test credentials and `MINIO_TEST_BUCKET`. Pass secret values through scoped process environment, not logged command arguments, and do not inherit the operator's endpoint/credential mapping accidentally. No host-service fallback is allowed.

The same fixture runs the existing complete-record integration test for CI/local opt-in. No-port lifecycle checks use captured owned container IDs for stop/start/removal/recreation while preserving their volumes. Normal deployment configuration checks separately assert loopback publications; the actual documented normal `up --force-recreate` lifecycle remains covered by the authorized full-model walkthrough.

The full-model browser walkthrough requires the normal local ports to be available. If occupied, report the conflict and defer that walkthrough; do not stop an unrelated server, silently change addresses or treat inability to run it as passing evidence.
