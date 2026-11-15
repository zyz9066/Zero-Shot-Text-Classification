# Zero-Shot-Text-Classification
Spec Kit-guided MLOps platform for zero-shot text classification with Hugging Face Transformers, Streamlit model management, local caching, and MinIO-backed prediction storage.

Inference runs locally through PyTorch. A result is successful only after MinIO
acknowledges its prediction write. This is a **trusted single-host development
application**, not authenticated public hosting or a production security setup.

## Prerequisites

- Python 3.11+; the container uses pinned Python 3.13 on Linux amd64.
- uv **0.13.5**, installed using the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).
  Use the committed universal lock, not an unlocked pip install.
- For containers: supported [Docker Desktop/WSL 2 on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
  with virtualization and Linux containers, or Linux amd64 Docker and Compose.
  ARM/native Windows containers are not validated.
- Network/disk capacity for dependencies and intentional model preparation.
  No full models are downloaded during image builds or ordinary tests.
- For saved classification: a supported MinIO service, authorized app
  credentials, and any required active license.

## Native Windows quickstart

Run PowerShell from the checkout root:

```powershell
uv sync --locked --all-groups
$env:MINIO_ENDPOINT = 'localhost:9000'
$env:MINIO_SECURE = 'false'
$env:MINIO_BUCKET = 'zeroshot-learning-test'
$appCredential = Get-Credential -Message 'Application MinIO access key and secret'
$env:MINIO_ACCESS_KEY = $appCredential.UserName
$env:MINIO_SECRET_KEY = $appCredential.GetNetworkCredential().Password
uv run --locked streamlit run app\streamlit_app.py --server.address 127.0.0.1
```

Start storage separately using the next section; app environment settings do
not start a server. Open <http://localhost:8501>. Without storage credentials,
omit the credential settings: the shell, model and label management remain
usable, but classification cannot report a successful save. Stop native
Streamlit with **Ctrl+C** in its launch terminal. Set environment changes in
that terminal and relaunch; another terminal does not modify an existing process.

## Docker application and MinIO

[Dockerfile](Dockerfile) packages runtime and validation targets.
[compose.yaml](compose.yaml) starts app only;
[compose.minio.yaml](compose.minio.yaml) adds supported MinIO AIStor.
All normal publications bind host loopback: app 8501, storage API 9000,
console 9001. Port availability does not prove licensed writes are permitted.
Never stop an unrelated service to free these ports; defer the normal walkthrough.

### License and server credentials

Follow the current [official AIStor container installation](https://docs.min.io/aistor/installation/container/install/)
and [licensing guide](https://docs.min.io/aistor/operations/licenses/).
Obtain a valid license through the vendor/SUBNET or Free Tier registration.
Free Tier is single-compute and has support limitations; authorization for an
additional CI instance is an operator responsibility. Archived community
downloads are not this recipe's supported default.

Store the downloaded license and root-credential files outside the checkout.
Protect their OS permissions/ACLs; root files are UTF-8 credential values only,
without extra whitespace or newlines. Do not commit, bake into images, or paste
their contents into commands, logs, screenshots or support tickets.

In a **separate Docker launch PowerShell**, replace these example paths:

```powershell
$env:MINIO_LICENSE_FILE = 'C:\external-secrets\minio.license'
$env:MINIO_ROOT_USER_FILE = 'C:\external-secrets\minio-root-user'
$env:MINIO_ROOT_PASSWORD_FILE = 'C:\external-secrets\minio-root-password'
uv run --locked python scripts\check_deployment.py preflight
if ($LASTEXITCODE -ne 0) { throw 'Fix external file inputs before starting storage' }
```

Preflight checks readable, nonempty regular files and credential whitespace,
not license authenticity/expiry. A directory named `minio.license` is invalid;
the bind mount also disables automatic host-path creation.
The server receives `/run/secrets/minio-root-user` and
`/run/secrets/minio-root-password` through its `_FILE` variables, **not host paths**.
Root credentials are not copied into the app. Provide a separately authorized
app identity; only for trusted local development may you explicitly choose
the corresponding root credentials.

### Start, check, stop and restart

Supply app credentials and a valid explicit bucket in that Docker terminal:

```powershell
$appCredential = Get-Credential -Message 'Application MinIO access key and secret'
$env:MINIO_ACCESS_KEY = $appCredential.UserName
$env:MINIO_SECRET_KEY = $appCredential.GetNetworkCredential().Password
$env:MINIO_ENDPOINT = 'minio:9000'
$env:MINIO_SECURE = 'false'
$env:MINIO_BUCKET = 'zeroshot-learning-test'
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration validation failed' }
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml up -d --build
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml ps
uv run --locked python scripts\check_deployment.py health --component app
uv run --locked python scripts\check_deployment.py health --component minio
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml exec app python scripts/check_deployment.py storage --write-probe
```

Browser: <http://localhost:8501>. Host/native S3 API: `localhost:9000`.
Browser console: <http://localhost:9001> (**not the API**).
The container app uses `minio:9000`, not host localhost.
HTTP/`MINIO_SECURE=false` is only this loopback development recipe;
production requires supported TLS, trusted certificates and least privilege.
Do not disable certificate validation to fix a TLS mismatch.

The explicit probe performs one PUT, bounded exact readback and acknowledged
own-key deletion under `healthchecks/<UUID>.json`. It never writes predictions
or retries an uncertain PUT. Its credentials need GET/DELETE for its owned probe
key, in addition to bucket access/PUT; use an authorized probe identity if the
app's production write-only policy lacks these rights. Failed cleanup is failure.
`config` without `--quiet` can disclose resolved credentials; do not publish it.
Docker administrators can inspect process environment: this is not secret
isolation from the host administrator.

To start only the shell, no license/root files are required:

```powershell
docker compose -p zeroshot-local -f compose.yaml up -d --build app
```

After safely finishing/deferring in-flight work, ordinary lifecycle commands are:

```powershell
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml stop
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml start
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml up -d --force-recreate
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml down
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml up -d
```

These retain named volumes. Use the same project identity/file flags: a different
project discovers different empty volumes, not the original data.
Environment changes require `up -d --force-recreate app`; plain start/restart
does not replace a container's configured environment.
Never use `down --volumes` or global prune as routine recovery.

## Prepare a model, labels and classification

In Model Management, intentionally download one configured model and wait for
ready status. [configs/models.yaml](configs/models.yaml) currently includes:

- [MoritzLaurer/deberta-v3-base-zeroshot-v2.0](https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0)
- [facebook/bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli)

Review each model's upstream license/model card. The adapter resolves and records
the actual revision; downloaded artifacts and `.model-manifest.json` preserve
provenance. Loading is local-only PyTorch, without unreviewed `trust_remote_code`.
Use existing model deletion/cache-preview/cleanup workflows, not manual deletion
during inference. Busy operations are blocked; interrupted files without a valid
completion manifest are not silently treated as ready.

Create a reusable set with at least two distinct valid labels. Classify
non-sensitive text, for example a fictional sports/news sentence, **once**.
While active, the page polls completion and reruns automatically when finished;
the draft remains available. Do not submit again to refresh processing status.
Record the request UUID only. An authorized operator can privately inspect
`predictions/<request_id>.json` in the exact configured bucket through the console.

The complete JSON contract has `request_id`, `input_text`, `predicted_class`,
`predicted_score`, `candidate_labels`, `ranked_results`, `model_name`,
`model_identifier`, `model_revision`, `timestamp`, and `application_version`.
Successful UI output requires a confirmed MinIO write, not a local fallback.

## Candidate-label management

Run `uv sync --locked` and `uv run --locked streamlit run app\streamlit_app.py --server.address 127.0.0.1`.
Open Candidate-Label Management to create and maintain reusable label sets. This
administrative workflow is for local or trusted environments only; navigation
visibility is not access control. No model or service credentials are required.

The default catalog is `configs/labels.yaml`; set `LABEL_CONFIG_FILE` to use
another local path. Keep its initialization marker and lock file alongside it,
and do not commit local configuration or credentials. If configuration is
missing or invalid, stop writers and restore a valid catalog and marker from a
backup rather than overwriting them. If both catalog and marker are lost, prior
data loss cannot be detected automatically. See the [feature quickstart](specs/003-candidate-label-management/quickstart.md)
for validation, supported concurrency, recovery, and tests.

## Configuration and precedence

[configs/app.yaml](configs/app.yaml) supports only `app.version`,
`model.model_dir`, `model.hf_home`, `model.transformers_cache`,
`minio.endpoint`, `minio.secure`, and `minio.bucket`.
App environment overrides YAML, then defaults. Explicit empty required values
are errors, not silent fallback. Explicit missing/invalid configuration fails
safely; default config absence uses existing loader defaults.
Native relative paths resolve from the launch working directory.
Label configuration has an independent resolver, not an app YAML section.

| Setting | Native meaning/default | Docker recipe |
|---|---|---|
| `APP_CONFIG_FILE` | `configs/app.yaml`; explicit paths must exist | Optional container-visible file, not a Windows host path |
| `APP_VERSION` | YAML/default `0.1.0`, nonempty | Pass through only when supplied |
| `MODEL_DIR` | `./models` | `/runtime/models` |
| `HF_HOME` | `./.cache/huggingface` | `/runtime/hf-home` |
| `TRANSFORMERS_CACHE` | `./.cache/huggingface/transformers` | Explicit adapter cache `/runtime/hub-cache` |
| `HF_HUB_CACHE` | Upstream library override/default | `/runtime/hf-home/hub` |
| `XDG_CACHE_HOME` | Upstream library override/default | `/runtime/xdg-cache` |
| `HF_TOKEN` | Optional environment-only secret | Optional pass-through, never a build input |
| `LABEL_CONFIG_FILE` | `configs/labels.yaml`, separately resolved | `/runtime/labels/catalog.yaml` |
| `MINIO_ENDPOINT` | Required for storage, scheme-free host:port | Default `minio:9000`, explicit override allowed |
| `MINIO_SECURE` | Required Boolean for storage | Default `false` for local HTTP |
| `MINIO_BUCKET` | Exact default `zeroshot_learning_output` | Environment pass-through or existing YAML/default |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | Required on storage use, not shell startup | Explicit app process inputs |
| `MINIO_LICENSE_FILE` | External host license path for Compose | Read-only `/minio.license` mount |
| `MINIO_ROOT_USER_FILE`, `MINIO_ROOT_PASSWORD_FILE` | External host credential-file paths | Server-only `/run/secrets/...` settings |
| `RUN_DEPLOYMENT_TESTS` | Test-only; `1` explicitly opts in | Isolated fixture execution |
| `MINIO_TEST_BUCKET` | Explicit direct-integration opt-in | Fixture selects its own valid UUID-scoped bucket |

Library cache variables are not recognized as extra app YAML keys.
The Docker layout intentionally overrides native model/cache/label paths.
`.env.example` is non-secret; Compose can load an untracked real `.env`,
but prefer secure process provisioning. Native uv/Streamlit does not automatically
load that Compose file. Built-in `COMPOSE_PROJECT_NAME`/`-p` controls resource and
image names; keep `zeroshot-local` stable for ordinary deployment.

To load a private `.env` explicitly with uv, use
`uv run --env-file .env --locked python scripts\check_deployment.py preflight`
or add `--env-file .env` to the native launch command. Single-quote Windows
paths in `.env`, for example `MINIO_LICENSE_FILE='C:\external-secrets\minio.license'`;
unquoted or double-quoted backslashes can cause uv parsing warnings. Existing
process environment values take precedence over the file.

Some services reject underscores in `zeroshot_learning_output`. Explicitly set
a valid override such as `zeroshot-learning-test`; the application never renames
the configured bucket silently.

## Durability, backup, transfer and privacy

| Resource | Docker durable location |
|---|---|
| Model artifacts/manifests/interrupted files | `app-runtime:/runtime/models` |
| Model-use coordination files | `/runtime/.<model-directory-name>.use.lock`, **outside** the model directory |
| All configured Hugging Face caches | `/runtime/hf-home`, `/runtime/hub-cache`, `/runtime/hf-home/hub`, `/runtime/xdg-cache` |
| Catalog, initialization marker, lock/temp sidecars | `/runtime/labels/catalog.yaml` and its parent |
| Prediction objects | `minio-data:/mnt/data`, in the exact bucket |

Container roots, browser session state and worker futures are disposable.
Volumes preserve data, not in-flight completion evidence. Neither catalog nor
initialization marker being present cannot prove no prior label data existed.
Restore initialized catalogs with their marker; do not overwrite recovery errors.

Keep native Windows and Docker model/cache/label data separate. This is the
recorded autonomous default, not a user-confirmed sharing guarantee. Transfers
require stopping **all** native/container writers and preserving provenance,
initialization evidence, cache relationships and parent locks. Revalidate ready
models at the destination; never rewrite manifests to force readiness.
No automatic migration/merge, multi-host or network-filesystem locking is provided.

See [the quiesced backup/restore and transfer guide](specs/005-deployment-ci-documentation/quickstart.md#9-quiesced-backup-restore-and-transfer).
It uses exact verified owned volumes and the pinned Python utility image.
Restore compatible server/image identities and permissions before enabling writers.
Do not assume physical MinIO backups work across unsupported downgrades.
Destructive reset is separate, confirmed and irreversible, never troubleshooting.

Input and predictions may be sensitive. Store only required data; avoid secrets in
input, restrict bucket access, protect backups (including possible HF token-home
files), and choose operator-controlled retention/backups before using real data.
There is no automatic retention management or prediction-history feature.
Inspect payloads privately with authorized access; support evidence contains
request UUID, safe error category, versions and host/container context only.

## Troubleshooting and uncertain writes

| Symptom | Safe next action |
|---|---|
| Docker/server unavailable or port occupied | Start the supported runtime/owned service or defer; do not delete volumes or stop unrelated services |
| License path is a directory/missing/unreadable | Correct the external regular file; rerun preflight; never create an empty placeholder |
| Healthy port/console but operations denied | Inspect authorized license status and bucket policy; health does not prove S3 permission |
| Wrong API/console/internal address | Native `localhost:9000`, container `minio:9000`, console 9001; never pass a URL scheme to `MINIO_ENDPOINT` |
| Missing/stale app credentials | Set app variables in its launch terminal and relaunch/recreate; server `_FILE` variables are not app credentials |
| Credentials/access denied | Verify authorized identity/policy and license status without printing values; ambiguous denial is not a proven license cause |
| TLS mismatch | Match secure setting/API scheme and trusted certificates; do not bypass validation |
| Invalid bucket | Explicit valid override; preserve the configured/default name otherwise |
| Unwritable/full runtime/storage | Check owned volume permissions/capacity; preserve initialization/provenance before repair |
| Processing status remains visible | Allow automatic polling; inspect safe request-ID diagnostics, not a second submit |
| Confirmed storage failure | Correct the reported condition; distinguish it from an uncertain PUT |
| Indeterminate PUT/disconnect | Inspect exact request key using authorized access; defer blind resubmission |

A matching complete record means **no resubmission**. Authenticated `NoSuchKey`
from the correct endpoint/bucket is not enough alone: separately establish the
original worker and issued remote write cannot still complete. If that evidence
is unavailable, defer/escalate to an authorized operator. Restart, elapsed time,
an empty console filter or a failed GET is not proof of non-completion.

## Architecture and developer validation

| Module | Responsibility |
|---|---|
| [app/streamlit_app.py](app/streamlit_app.py), [pages](app/pages) | Streamlit navigation, session interaction, automatic completion display |
| [app/config](app/config) | Scoped app/model/storage configuration; model and label validation |
| [model manager](app/services/model_manager.py), [Hub adapter](app/services/huggingface_hub_adapter.py) | Intentional download/delete/cache lifecycle, provenance and cooperating model locks |
| [label manager](app/services/label_manager.py) | Canonical catalog, initialization evidence and atomic coordinated edits |
| [model provider](app/services/model_provider.py), [inference](app/services/inference.py) | Local cached PyTorch model resources and classification |
| [classification coordinator](app/services/classification.py) | Request identity, background state, label/model guards and confirmed save |
| [prediction store](app/services/prediction_store.py) | Complete record validation and no-retry MinIO writes |
| [logging](app/utils/logging_config.py) | Structured non-sensitive operational events |
| [scripts/check_deployment.py](scripts/check_deployment.py) | Safe file/health checks and explicit owned-key probe |
| [tests](tests), [CI](.github/workflows/ci.yml), [specs](specs) | Unit/smoke/concurrency/integration gates and design/evidence |

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app scripts\check_deployment.py
uv run --locked pytest tests\unit tests\smoke tests\integration\test_classification_concurrency.py tests\integration\test_label_concurrency.py -q
$env:RUN_DEPLOYMENT_TESTS = '1'
uv run --locked pytest tests\integration\test_deployment.py -k 'not isolated_prediction_storage' -q -rs
```

Expected: required gates pass; ordinary tests do not download models/contact model
services. Container tests inspect actual filtered inputs and both targets, use
unique owned resources, publish **no host ports**, and preserve lightweight
model/cache/label/lock artifacts through recreation.

For real isolated storage, explicitly supply an authorized `MINIO_LICENSE_FILE`
then run:

```powershell
uv run --locked pytest tests\integration\test_deployment.py -k isolated_prediction_storage -q -rs
```

The fixture generates its own test-only credentials/bucket and executes the
existing complete-record integration test inside validation on its verified
network. It does not inherit operator storage settings or borrow a host server.
Missing external prerequisites yield named skips; supplied-invalid licenses,
executed failures and cleanup errors fail. Failed/uncertain service cases may
retain stopped owned resources for private diagnosis; inventory their exact
project-labelled IDs before cleanup, never global prune.

Deployment failures report the operation, validation gate, approved failing
test identity when available, and safe corrective categories. Raw Docker/nested
test output is withheld on failure. Rerun the named test with non-sensitive
fixtures; do not publish environment dumps, raw inspection output or private
debugger/full-trace reports. Default and verbose/locals-enabled pytest reports,
including JUnit artifacts, are tested with generated credential sentinels.

The explicit storage probe treats a PUT's S3 5xx or unknown response status as
indeterminate, not proof of rejection. Its exact probe key remains available for
authorized inspection; neither retry nor deletion is attempted.

CI preserves gates, tests Python 3.11/3.13 on Ubuntu 24.04, pins action commits/uv,
and adds license-independent packaging plus eligible real storage validation.
Repository secret `AISTOR_TEST_LICENSE` must be explicitly authorized for CI;
fork PRs do not receive it. Missing licensing produces a visible skip/local
alternative, not service-backed coverage. No failed required command is hidden.

[Feature 005 quickstart/evidence](specs/005-deployment-ci-documentation/quickstart.md)
records passing local licensed storage, full-model/browser classification and
non-destructive deployment lifecycle checks, plus a separate fresh-context
repository-only reviewer walkthrough. Hosted checks remain unrun; final local
gate reconciliation is recorded separately in that guide.
Packaging tests are not screen-reader or participant-usability evidence.
Earlier guides: [foundation](specs/001-application-foundation-config/quickstart.md),
[model lifecycle](specs/002-model-lifecycle-management/quickstart.md),
[labels](specs/003-candidate-label-management/quickstart.md),
[classification/persistence](specs/004-classification-persistence/quickstart.md).
