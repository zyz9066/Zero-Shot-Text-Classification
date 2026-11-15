# Quickstart Validation: Feature 005

**Implementation guide**: Deployment files and diagnostics are present.
Executed evidence is recorded below. Licensed storage and one full-model/browser
classification and normal deployment lifecycle walkthrough passed locally.
The repository-only reviewer walkthrough passed; hosted checks remain unrun.
The interactive launcher added later has separate validation evidence below.

**Re-plan note**: U1/U2 use port-independent automated fixtures and a single
filtered root build context. Tasks were regenerated and analyzed before
implementation.

## Interactive Windows launcher

The main [README quickstart](../../README.md#quickstart-full-local-application)
offers `.\scripts\local.ps1` for interactive setup and full start,
`.\scripts\local.ps1 status` and `.\scripts\local.ps1 stop`, and
`.\scripts\local.ps1 app` for the independent shell. It reuses `.env`, the
existing preflight and Compose services. Credentials are requested for each full
start and are not written to `.env`. Container status alone is not storage
readiness; `.\scripts\local.ps1 check` runs the explicit write probe in section 3.

**Launcher validation (2026-11-15)**: On Windows PowerShell 5.1, the deployment
unit selector passed 55 tests with four Linux-only skips. Launcher tests exercised
setup, failures and lifecycle commands with Docker stubbed, and tested the
generated dotenv file with the real `uv` and preflight, including paths with
spaces and `$`. Ruff lint/format and strict mypy passed. Docker was unavailable,
so no live launcher, licensed storage probe, or new end-to-end deployment was
run; the earlier deployment walkthroughs predate the launcher.

**Implementation baseline (2026-11-15)**: Windows Python 3.13, uv 0.13.5,
Docker 29.9.3 on a local Linux x86_64 engine. The initial combined unit, smoke
and concurrency run produced 177 passes and one Windows spawned-worker
10-second readiness timeout. Both parameters of that unchanged test passed
on a focused rerun (2 passes). This is recorded as a baseline timing failure,
not hidden as a skip. No models or storage services were downloaded/started by
the baseline run. External license and storage credential inputs are absent.

## 1. Prerequisites

- Supported Windows Docker Desktop, WSL 2 Linux backend and virtualization, or a supported Linux amd64 Docker/Compose host. Verify vendor requirements linked in [research.md](research.md).
- Python >=3.11 and uv for native tests; intentional network/disk capacity for dependencies and first model preparation.
- Valid externally obtained AIStor license permitted for this compute resource, plus external root-credential files. Download the license through the documented vendor flow. Never create an empty placeholder and assume it licenses storage.
- Trusted local machine; this is not production access control/TLS configuration.

All following host commands use PowerShell from the repository root:

```powershell
docker version
docker compose version
uv sync --locked --all-groups
```

Expected: Docker Linux engine/Compose available and locked installation succeeds. A missing server, occupied port, or unavailable vendor dependency is an explicit prerequisite problem, not data-loss recovery.

## 2. Supply external files and app credentials

Store license/root-credential files **outside the repository** with restrictive OS access. Root files contain only their value, no added whitespace/newlines. Use your secret manager or secured editor; do not paste contents into logs/tickets.

The following file paths are examples to replace with your real external regular files:

```powershell
$env:MINIO_LICENSE_FILE = 'C:\local-secrets\minio.license'
$env:MINIO_ROOT_USER_FILE = 'C:\local-secrets\minio-root-user'
$env:MINIO_ROOT_PASSWORD_FILE = 'C:\local-secrets\minio-root-password'
uv run --locked python scripts\check_deployment.py preflight
if ($LASTEXITCODE -ne 0) { throw 'Fix external file inputs before starting storage' }
```

Expected: safe file-validation success. A directory mistakenly named `minio.license` fails. This does not verify authenticity/expiry; actual server license state and operations must be checked later.

Supply app credentials explicitly in this same launch terminal without printing them:

```powershell
$appCredential = Get-Credential -Message 'Enter the application MinIO access key and secret'
$env:MINIO_ACCESS_KEY = $appCredential.UserName
$env:MINIO_SECRET_KEY = $appCredential.GetNetworkCredential().Password
$env:MINIO_ENDPOINT = 'minio:9000'
$env:MINIO_SECURE = 'false'
$env:MINIO_BUCKET = 'zeroshot-learning-test'
```

For trusted local validation you may explicitly enter the corresponding server credentials; they are not copied automatically. Production requires an independently scoped least-privilege app identity.

The underscore-bearing mandated default remains `zeroshot_learning_output`; the explicit override above is a valid test example, not a silent rename. Host file variables feed Compose secret sources; server `_FILE` settings point inside its container. App settings feed the Streamlit process.

## 3. Start and check the full deployment

```powershell
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration validation failed' }
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml up -d --build
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml ps
uv run --locked python scripts\check_deployment.py health --component app
uv run --locked python scripts\check_deployment.py health --component minio
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml exec app python scripts/check_deployment.py storage --write-probe
```

Expected: browser app `http://localhost:8501`; S3 API `http://localhost:9000`; Console `http://localhost:9001`. Node health is not licensed write permission. Only the last command verifies storage PUT/readback/exact-key cleanup. It uses non-sensitive `healthchecks/<UUID>.json`, never a prediction key.

Never copy resolved `docker compose config` output without `--quiet` into reports: it may contain credentials. Inspect authorized Console license status if operations are denied despite healthy endpoints. Correct invalid licenses externally, then recreate/restart without deleting data.

Environment changes require recreating the app with `up -d --force-recreate app`; `start` or plain `restart` does not replace its configured environment.

## 4. Classify and inspect a real prediction

1. Open the local app. Use existing model management to intentionally download one supported model; verify ready/provenance status.
2. Use existing candidate-label management to save a valid label set.
3. Classify non-sensitive text such as a short fictional sports/news sentence. Submit once.
4. Observe processing followed automatically by saved result, without another submit. Record request UUID only.
5. In the authorized Console, inspect exactly `predictions/<request_id>.json` in `zeroshot-learning-test`. Privately verify the complete existing schema, model revision, ranked results, and matching request ID. Confirm one matching record.

Never publish input or prediction JSON as walkthrough evidence. Failed/uncertain storage must not display a successful save.

Console inspection does not require the optional `mc` client. Both Console
object views and `mc cat` can display sensitive payloads: use them only privately
with authorized access, never as support output. An SDK inspection is also a
private read of the same exact bucket/key and documented schema, not a second
submission or readiness probe. Release its response resources and report only
request identity and validation outcomes. The reviewer evidence below records
the temporary SDK alternative actually used; it is not an installed project CLI.

For uncertainty, follow [the inspection contract](contracts/deployment.md#4-request-recovery-and-authorized-inspection). Matching record means no retry; authoritative absence plus definitive non-completion are both required. Restart, elapsed time, or an empty Console filter is not proof.

## 5. Verify stop, restart, recreation, and data preservation

First quiesce/defer in-flight work safely. Record ready model/provenance, labels, caches, initialization marker/lock presence, and prediction UUID without publishing file contents.

```powershell
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml stop
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml start
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml up -d --force-recreate
```

Expected after each operation: same models/manifests/caches, labels/initialization evidence, parent model locks and saved object; ready model reuse without redownload. Verify actual volume mounts and non-root writability. Volumes are named by the stable project identity; do not switch project names and mistake new empty volumes for lost data.

Non-destructive removal/recreation is also tested:

```powershell
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml down
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml up -d
```

**Never use volume deletion or global prune for routine recovery.** Back up both complete volumes while all writers are stopped; restore compatible identities and ownership before enabling writers. Keep native Windows/Docker files separate. Transfer only quiesced data preserving provenance/initialization evidence; no concurrent sharing or automatic migration.

## 6. Verify independent app startup

Use a separate project with base Compose only:

```powershell
if (Test-Path Env:MINIO_ACCESS_KEY) { Remove-Item Env:MINIO_ACCESS_KEY }
if (Test-Path Env:MINIO_SECRET_KEY) { Remove-Item Env:MINIO_SECRET_KEY }
docker compose -p zeroshot-shell-check -f compose.yaml up -d --build app
```

If port 8501 is occupied, defer this manual check or stop only an app you own and
intend to stop. Automated checks below publish no ports. Expected: shell and
independent management work without storage inputs; classification cannot claim
success. This project has separate data, not the original deployment's volumes.

Finish this check non-destructively:

```powershell
docker compose -p zeroshot-shell-check -f compose.yaml down
```

## 7. Native tests and local service-backed alternative

```powershell
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app scripts\check_deployment.py
uv run --locked pytest tests\unit tests\smoke tests\integration\test_classification_concurrency.py tests\integration\test_label_concurrency.py
```

Expected: ordinary tests pass without model downloads/external model services.

Container-target and lifecycle validation commands. Both targets use the one
root source allowlist; only validation copies approved non-sensitive tests and
non-secret deployment/CI fixtures. There is no additional named context:

```powershell
docker build --target validation -t zeroshot-validation .
docker run --rm zeroshot-validation python -m pytest tests/unit tests/smoke tests/integration/test_classification_concurrency.py tests/integration/test_label_concurrency.py
$env:RUN_DEPLOYMENT_TESTS = '1'
uv run --locked pytest tests\integration\test_deployment.py -q -rs
```

Expected: direct filtered-context checks and separate runtime/validation image checks, plus isolated lightweight persistence/ownership/recreation tests, without downloading models. Generated forbidden sentinels under approved directory ancestors must not enter the context/images; approved test source must be available in validation, not runtime. Automated fixtures use unique image/container/project identities, unlike this optional manually named standalone validation image.

Deployment fixtures start app/server services through no-port `compose run --no-deps --use-aliases`, verify ownership/empty port bindings, and run clients in the validation image on the owned network. They do not bind host 8501/9000/9001, stop an existing developer service or fall back to host localhost. App-only cases do not load the server overlay. License-dependent cases require authorized external file provisioning; named missing-prerequisite skips are visible and executed failures fail.

### Port-independent local alternative to CI storage validation

Supply only an external license permitted for this isolated compute resource.
The fixture creates its own test-only server/app credentials; it does not borrow
step 2's root files, credentials or endpoint. Run:

```powershell
$env:RUN_DEPLOYMENT_TESTS = '1'
uv run --locked pytest tests\integration\test_deployment.py -k isolated_prediction_storage -q -rs
```

The `test_isolated_prediction_storage` fixture builds the single-context targets,
creates its own AIStor instance/project/volumes and UUID-scoped valid bucket,
verifies ownership and empty port bindings, and executes the existing complete
record test inside validation on the owned network. It requires that testcase
actually passed, not a zero exit containing skipped tests. It removes only
acknowledged test-owned prediction/sentinel objects. Absent external runtime or
license availability is a named pre-execution skip; supplied-invalid inputs,
license/permission rejection, ownership/startup/test/cleanup failures fail.
Failed or uncertain service cases retain stopped owned diagnostic resources;
inventory their exact project-labelled IDs before explicitly cleaning them.

This is the preferred local alternative when CI cannot receive a permitted
license. Its real-service outcome must be recorded separately from mocked or
license-independent checks.

### Optional direct test against an explicitly authorized development server

The existing direct integration command remains available if an operator explicitly authorizes testing an already-running development service/bucket. It is not the automated isolated-CI fixture and must never be an implicit fallback. Provide authorized app credentials in this test terminal, target the host API, and explicitly opt in:

```powershell
$appCredential = Get-Credential -Message 'Enter credentials for the isolated local test storage'
$env:MINIO_ACCESS_KEY = $appCredential.UserName
$env:MINIO_SECRET_KEY = $appCredential.GetNetworkCredential().Password
$env:MINIO_ENDPOINT = 'localhost:9000'
$env:MINIO_SECURE = 'false'
$env:MINIO_TEST_BUCKET = 'zeroshot-learning-integration-test'
uv run --locked pytest tests\integration\test_prediction_storage.py -q -rs
```

Expected: one real complete record written/read and own object removed; bucket and unrelated objects retained. Use only a development service/bucket explicitly authorized for this test, never production. Omitting `MINIO_TEST_BUCKET` explicitly skips, not passes service-backed coverage. Supplied but invalid credentials/license or a failed test must fail.

Before returning to Compose, restore container endpoint `minio:9000` and app credentials in the launch terminal. Before native Streamlit use, keep host `localhost:9000` and separate native data paths. Do not carry host endpoints into containers.

## 8. Failure matrix and evidence record

Exercise server stopped, directory/invalid/missing license, wrong API/console/internal endpoint, missing/stale app environment, rejected credentials, TLS mismatch, invalid bucket, denied permission, late/uncertain write, and cleanup failure. Each case has the contract's safe corrective action and no success-shaped fallback. Do not damage existing storage to manufacture failure tests; use fixtures or isolated deployment instances.

| Validation | Observed implementation status | Evidence / remaining limitation |
|---|---|---|
| Official distribution/health/index research | sources and immutable identities rechecked; actual supplied-license execution now passed | Pinned AIStor binary `RELEASE.2026-09-19T17-05-25Z`; see follow-up below |
| CPU dependencies and Python floor | locked 3.11/3.13 exports passed; Linux 3.13 CPU imports/tiny tensor passed | Runtime uses torch `2.15.0+cpu`; native Windows resolution preserved; no executed 3.11 hosted job |
| Native quality gates | Ruff lint/format and strict mypy passed; latest combined suite **227 passed, 4 Linux-only shell cases skipped** | Native Python 3.13; no model downloads; latest convergence evidence below |
| Linux offline regression suite | Repeated successfully inside the updated validation image; initial implementation run was **213 passed, 4 explicit opt-in integration/container skips** | Four CI shell cases execute, including absent/provided license and nonzero propagation; network disabled; latest outer command passed, but its captured nested count is not separately reported |
| Image/context/ownership/app-only checks | **3 passed, 1 licensed-prerequisite skip** | Actual filtered inputs and both targets; CPU/imports, UID 10001, no published test ports, owned network, startup without secrets, parent lock/label marker preservation, stop/start/recreation and lightweight stopped-volume SHA/UID restore |
| Representative gate failures | actual Ruff lint/format, mypy and pytest regressions returned 1 with expected diagnostics | Disposable fixtures only; not deliberately broken committed source; hosted job execution unrun |
| Licensed real persistence integration | **Passed with externally supplied license** | Complete record written/read, unrelated test sentinel preserved and exact cleanup verified; generated test credentials, no operator server borrowed; earlier missing-license skips remain historical, not coverage |
| Full model/browser/classification/recreation | passed locally; see full-model follow-up below | One automatically completed saved request, cold offline ready-model reuse and exact durable state across normal lifecycle commands; real physical MinIO restore/transfer remain unrun |
| README reviewer walkthrough | passed in a separate fresh context; see reviewer follow-up below | Fresh private setup, model/labels, automatic saved classification, private exact-record inspection and owned-resource cleanup; not inferred from syntax/link checks |
| Accessibility/participant usability | unrun in feature 005 | Earlier evidence limits retained; no inferred completion |

The initial baseline had 177 passes and one Windows spawned-worker readiness
timeout; both unchanged parameters passed on focused rerun. The final combined
native suite above passed. Initial container runs exposed and then corrected
Docker ancestor-negation filtering, a fixture factory import, and package
importability outside the checkout. Final container validation passed in
502.90 seconds; its nested Linux suite passed in 89.88 seconds.

Helper containers are created and ownership/network/publication checked before
starting their commands. Their captured IDs are removed even on a nonzero
command; an actual exit-7 fixture verified failure propagation and cleanup.
Only this run's owned images, containers, networks and volumes were removed.
User data and unrelated services were not stopped or reset.

The existing complete-record integration preserves a separately acknowledged
test-owned sentinel while removing its prediction, then removes only that exact
sentinel. This was initially unrun; the supplied-license follow-up below now
confirms actual server/client write/read execution, not mock or skip coverage.

A separate configured-invalid license-directory invocation failed with exit 1
before image/service execution, rather than being converted to a skip. Final
Ruff lint/format, strict mypy, focused CLI regressions and `git diff --check`
passed. Local README/plan/quickstart links and PowerShell syntax checks passed.
The scoped review found no application/schema/model/label contract edits or
credential/license contents in deliverables. Optional commit hooks were skipped;
no changes were committed. Final end-to-end approval remains pending.

All ten constitution gates were rechecked against the delivered stack, lock,
provenance, boundaries, Streamlit lifecycle, external secrets/context filtering,
MinIO schema/default/confirmed-write behavior, safe failures, executed quality
checks and truthful documentation. Execution evidence covers automated subsets
of the plan's 25 FR / 13 acceptance / 8 success-criteria mapping, **not** all
user-observable criteria: T017/T031 and their dependent final completion gates
remain open. No hosted CI, participant or accessibility success is claimed.

### Convergence implementation evidence (2026-11-15)

T035-T037 are complete. Credential-bearing deployment environments now have
value-withholding representations in caller frames; secret-bearing subprocess,
inspection and credential-provisioning frames are excluded from normal pytest
tracebacks. Safe `DeploymentError` messages retain the operation, gate, exit
category, known readiness reason and approved failing test identity, rather
than raw logs. Test identities are checked against the root source allowlist
and actual test functions; parameter values and unapproved names are never
copied. Failure plus cleanup failure retains both safe causes and remains
nonzero. This is report hygiene, not protection from an authorized debugger
or Docker administrator; do not publish private full-trace/inspection output.

The probe now treats only an S3 HTTP 4xx response as an authoritative PUT
rejection. XML HTTP 500/503 and unknown-status failures return `indeterminate`
with the exact probe ID/key and the absence-plus-definitive-non-completion
requirement. They trigger neither a second PUT nor DELETE. Existing acknowledged
readback/cleanup and credential/bucket rejection behavior remains covered.

| Executed command / check | Observed result |
|---|---|
| New disclosure/uncertainty regressions before fixes | 6 failures, 3 passes; verbose report disclosure and XML 500/503/unknown-status misclassification reproduced without emitting sentinel values |
| New Docker/helper diagnostic cases before fixes | 4 failures; missing category/recovery and nested gate identity reproduced |
| `uv run --locked pytest tests\unit\test_deployment_checks.py -q --tb=short` | 49 passed, 4 Linux-only skips in 44.76 seconds; includes 12 child-pytest default/verbose-with-locals reports and JUnit artifacts, credential provisioning, helper exit and cleanup failure boundaries |
| `uv run --locked ruff check .`; `uv run --locked ruff format --check .`; `uv run --locked mypy app scripts\check_deployment.py` | Passed; 108 files formatted, 22 typed source files |
| Combined native unit/smoke/concurrency selector from section 7 | First attempt alongside Docker: 226 passed, 4 skipped, one unchanged smoke test's 3-second timeout. That exact test passed unchanged in 4.98 seconds; sequential full rerun: **227 passed, 4 skipped** in 144.15 seconds |
| `RUN_DEPLOYMENT_TESTS=1` with `uv run --locked pytest tests\integration\test_deployment.py -q -rs --tb=short` | **3 passed, 1 explicit missing-license skip** in 483.24 seconds; actual filtered-context/both-image checks, network-disabled Linux regression suite, app-only health, durable lightweight state and backup/restore passed |
| Actual owned-helper exit 7 and deliberately failing nested pytest testcase | Both propagated nonzero with allowlisted diagnostics; exact helper cleanup succeeded and no project helper remained |
| Docker build/start and helper cleanup failures with generated sentinels | Simulated subprocess failures preserved safe reasons and nonzero status, including both primary/cleanup causes; not claimed as actual engine permission failures |
| Post-run read-only test container/volume inventory | No `zeroshot-test-` Compose-labelled containers or volumes remained; no operator service/data was borrowed, stopped or deleted |
| Final documentation/task checks | Local README/plan/quickstart/task links resolve; 22 README/quickstart PowerShell blocks parse; all 40 task IDs are unique, 31 checked and 9 pending. Final Ruff/format/mypy and diff-whitespace checks passed |

These are local results with the existing pinned Python/uv/CPU torch identities,
not hosted-job execution. No external `MINIO_LICENSE_FILE` is configured, so
T017/T038 remain pending an explicitly supplied license authorized for this
compute resource, external credentials, available normal loopback ports and
intentional full-model preparation. T031/T039 also need the repository-only
reviewer walkthrough. No actual licensed AIStor write, full-model reuse,
completed saved browser request, real storage backup/restore or cross-environment
transfer is inferred from fixtures. Use section 7's isolated storage invocation
after provisioning the authorized license; do not borrow an operator's server.

T030 was returned to unchecked because its explicit T017 prerequisite is
unfinished. Its authored guide is not walkthrough evidence. T032-T034/T040
remain pending their final dependency gates despite the available checks above;
current completion is **31/40**, not feature convergence.

The existing [plan traceability](plan.md#requirement-and-acceptance-traceability)
still maps every requirement and scenario. Current evidence reconciliation:

| Source obligations | Current evidence and remaining boundary |
|---|---|
| FR-001, FR-003, FR-007, FR-012; US1/AC1-3; US3/AC1; SC-001 through SC-003 | Packaging, lightweight persistence and UI smoke regressions pass; actual licensed full-model/browser/ready-model/object durability and clean reviewer walkthrough remain unrun |
| FR-002, FR-004, FR-006, FR-016; SC-007 | Locked CPU imports, filtered context/target checks, no-port isolation and default/verbose/JUnit credential-sentinel exclusion pass; initial 3.11 lock exports are not an executed hosted 3.11 job |
| FR-005, FR-009, FR-011, FR-014, FR-023; US1/AC4, US1/AC6, US3/AC2; SC-004 | Configuration/endpoint/bucket/transport/probe regressions and safe diagnostic summaries pass, including XML 5xx uncertainty; real license authenticity and reviewer-operated failure recovery remain unrun |
| FR-008, FR-010, FR-013; US1/AC5 | Cooperating-process tests, independent app startup, sidecars and lightweight stopped-volume restore pass; real-model cross-environment transfer and real MinIO restore remain unrun |
| FR-015, FR-020; US2/AC1-2; SC-005 | Local lint/format/type/regression gates and real disposable gate/helper/nested-test failures pass; hosted CI jobs have not executed |
| FR-017, FR-018; US2/AC3-4; SC-006 | Initially named missing-license skips; supplied-license follow-up now passed actual complete-record integration. Earlier supplied-directory failure remains recorded as failure, not skip; hosted jobs remain unrun |
| FR-019; SC-007 | Owned helper/container/volume cleanup, sentinel-safe reporting and actual storage integration's unrelated-test-object preservation pass; follow-up includes cleanup of image-declared anonymous volumes |
| FR-021, FR-022, FR-024, FR-025; US3/AC3; SC-008 | Architecture/settings/schema/privacy/lifecycle topics and runnable examples are authored; links/PowerShell syntax checked separately from pending repository-only reviewer, participant and accessibility evidence |

All ten constitution principles were rechecked: the mandated stack and lock,
model provenance/local loading, service/UI boundaries, secret exclusions,
MinIO default/schema/confirmed-save rule, input/failure guards, quality gates
and truthful operational documentation remain intact. T035's reporting gap and
T036's probe uncertainty contradiction are corrected; the explicitly recorded
external-evidence gaps are not waived.

### Supplied-license validation follow-up (2026-11-15)

A readable, nonempty license file was supplied outside the repository. Its
contents were not displayed, copied into source/images or included in reports.
The user was unavailable to answer the scope/authorization form. Isolated
storage-only validation was the autonomous minimum scope, not user-confirmed
authorization for full-model downloads or the broader reviewer walkthrough.
Server acceptance during this test is not certification of licensing
entitlement, future validity or permission for another deployment.

No existing operator credentials were needed: the fixture generated temporary
root/app values and a unique valid bucket on a verified owned network with
no published ports. The first attempt failed before prediction validation
because the pinned AIStor image declares an anonymous `/data` volume, whereas
the fixture assumed every volume carried Compose labels. That was a fixture
failure, not a license rejection, and was not converted to a skip.

The fixture now accepts only image-declared, engine-created anonymous mounts:
an unowned explicitly bound/mounted volume or volumes-from source is rejected.
Removing the captured owned service with `docker rm -f -v` lets Docker remove
its anonymous volumes; named volumes remain subject to exact project ownership
checks and separate cleanup. Actual prediction data remains `/mnt/data`;
the image's unused `/data` declaration is not a new prediction location.

| Executed validation | Observed result |
|---|---|
| Initial selected licensed integration | Failed with the fixture's missing Compose-label lookup, 61.37 seconds; no prediction validation ran |
| Focused deployment unit selector after fix | **51 passed, 4 Linux-only skips**, 45.37 seconds; includes image-anonymous versus unowned-explicit mount regressions and existing safe-report/uncertainty cases |
| Selected isolated storage test after fix | **1 passed, 3 deselected**, 63.08 seconds; complete-record write/read and sentinel/exact-key cleanup actually ran |
| App durability plus isolated storage selectors | **2 passed, 2 deselected**, 92.76 seconds; app-only startup/sidecars/backup/recreation and real storage passed with the cleanup change |
| Ruff lint/format, strict mypy and diff whitespace | Passed; 108 formatted files, 22 typed source files |
| Pinned AIStor binary metadata | `RELEASE.2026-09-19T17-05-25Z`; locked MinIO SDK 7.2.20, existing research image digest unchanged |
| Cleanup inventory | Three MinIO attempts had six captured volume identities; none remained. The first failed attempt's exact named/anonymous volumes were removed only after matching owned-container mount events and confirming no container referenced them. No test containers remained; unrelated resources were not modified |

This supersedes earlier missing-license statements and task-count snapshots:
**31/43 tasks complete, 12 pending**. T024 now has actual local service-backed
evidence, not only its formerly permitted skip/local-alternative evidence.
T017/T038/T041 remain pending intentional full-model/UI validation, normal-port
lifecycle checks and ready-model/prediction durability; T030/T031/T039/T042 and
the final gates depend on that work. No full model was downloaded and no
saved browser request, real storage backup/restore, transfer, hosted CI,
participant/accessibility or clean reviewer walkthrough is claimed.

### T044 PowerShell command validation (2026-11-15)

The original copied `docker volume inspect $name --format` ownership command
failed against a disposable labelled volume with exit **64** under Windows
PowerShell **5.1.19041.7844**: native argument handling stripped the Go-template
key's quotes (`function "com" not defined`). That exact volume was removed after
checking its project label. A PowerShell syntax check alone missed this failure.

The [section 9](#9-quiesced-backup-restore-and-transfer) backup block now checks
the native inspection exit, parses JSON with terminating errors, requires one
volume and the exact case-sensitive project label/key, and rejects running
writers before creating archives. A failed Compose stop also stops the block.

Executed the section 9 ownership/writer checks and both backup/restore command
blocks through `powershell.exe -NoProfile -NonInteractive -EncodedCommand`
(UTF-16LE/base64 script input). The harness substituted only disposable project
and volume identities and an external Windows backup path containing spaces;
it also added helper names/project labels for exact cleanup. The commands'
native mount, label and Python `-c` argument boundaries were exercised, not just
parsed. Fixture writers were quiesced first; the normal project's Compose stop
was deliberately not run. Docker was **29.9.3**, using the Linux amd64 engine
and section 9's unchanged pinned Python utility image.

| Executed check | Observed result |
|---|---|
| Matching project label | Accepted |
| Mismatched owner, case-changed owner, missing label, case-changed label key | All four refused with `Volume ownership not confirmed` |
| Nonexistent volume / native nonzero exit | Refused with `Volume inspection failed; ownership not confirmed` |
| Owned running fixture writer | Refused with `Writers are not confirmed stopped`; no archive directory created |
| Copied backup commands | Both nonempty archives created through the spaced Windows bind path |
| Copied restore commands | Both archives restored into new volumes with the expected interpolated project/volume labels |
| Restored fixture comparison | Both byte hashes, UID 10001 and file mode 0640 matched; UID 10001 could read the restored files |

**Ten executed checks passed.** Cleanup verified all six validation volumes,
all helper containers and both fixture archives were absent. Cleanup checked
exact allocated identities and ownership labels, never a global prune or
operator resource. The separate reproduction volume was also removed. The
pinned utility image remains cached. No ports were published, no MinIO or model
was started, and no operator data, credentials or license contents were read.

README/quickstart native argument boundaries were audited; no other embedded
quoted Go-template label lookup occurs. All their PowerShell blocks also passed
syntax validation, which remains separate from executed command evidence.
PowerShell 7 (`pwsh`) was unavailable; neither it nor Linux-host PowerShell was
executed or inferred to pass. README already links this canonical backup guide
and needs no duplicate command correction.

T044 is complete: **32/44 tasks complete, 12 pending**. This fixture-only command
validation does not replace T041's full-model/UI and normal deployment lifecycle,
T042's clean reviewer walkthrough, or T043's final dependency/evidence gates.
Actual physical MinIO restore, real-model transfer, hosted CI, accessibility
and participant checks remain unrun.

### Full-model and normal deployment walkthrough (2026-11-15)

The supplied license enabled further implementation, not just another storage
test. The requirements checklist was 16/16 checked. Read-only prerequisite
checks found loopback ports 8501/9000/9001 free and no conflicting normal-project
containers/volumes. No response was available to the scope form; proceeding
with this bounded full-model validation was an autonomous choice, not
user-confirmed scope, reviewer approval or certification of license entitlement.

Used a fresh project
`zeroshot-walkthrough-d29f0677e1e54a1c812292c2e06ab9b6`, the existing two Compose
files and immutable images. An explicit private empty env file prevented
operator `.env` inheritance. Generated root/app credentials were held in
external files restricted to the current Windows user and SYSTEM; no operator
password was requested or borrowed. Native model/cache/label data was not used.
The supplied license remained an external read-only mount.

The executed command prefix was `docker compose --env-file
<private-empty-env-file> -p <owned-project> -f compose.yaml -f
compose.minio.yaml`; the private path is intentionally not published. Suffixes
below are the same normal deployment operations documented in sections 3-5,
with a fresh owned project identity rather than an operator's project. Host
shell: Windows PowerShell 5.1.19041.7844; Docker 29.9.3/Linux amd64. App UID
10001 and actual loopback-only publications were inspected before validation.

| Executed command / operation | Observed result |
|---|---|
| `config --quiet`; `up -d --build` | App and AIStor started on the documented loopback ports; no unrelated service was stopped |
| `exec -T app python scripts/check_deployment.py storage --write-probe` | Acknowledged PUT, exact readback and owned-key cleanup returned `ready` |
| Model Management: select only DeBERTa, then Download selected models | Full configured model intentionally downloaded through the existing workflow; UI reached Ready with immutable revision `8e7e5af5983a0ddb1a5b45a38b129ab69e2258e8` |
| Candidate-Label Management: save a two-label set | Saved catalog and initialization evidence created in the Docker runtime |
| Classification: submit one non-sensitive fictional sentence once | Automatically displayed `Prediction saved to MinIO` and completed results, without another submit or manual refresh |
| Private API readback of `predictions/96da246f-dc89-4dcf-b93f-bbb845315cf2.json` | Exactly one prediction; matching UI/request ID, input, model revision, candidate/ranked results and existing record metadata inspected without publishing the payload |
| `stop`; `start` | Exact runtime file hashes/UIDs and the single prediction's byte hash matched the baseline |
| `up -d --force-recreate` | New service containers reused persisted state; same ready model, runtime hashes/UIDs and prediction |
| `down`; `up -d` (no volume deletion) | Same exact durable state and one matching complete saved prediction |
| Cold inference after recreation, with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` and socket connections forbidden | Existing ready model loaded locally and produced both ranked labels; no redownload, network connection or second prediction write |
| Final snapshot after failure checks and offline inference | Baseline still matched: model/manifests, all populated runtime caches, catalog/initialization/coordination sidecars, parent model-use lock and the saved record |

Browser request ID was `96da246f-dc89-4dcf-b93f-bbb845315cf2`; only non-sensitive
identity/provenance/outcome metadata is retained here. The runtime snapshot
covered every file under `/runtime`, including the configured HF/cache paths
and sidecars, and privately compared the saved object's bytes. Container
session futures/results were not treated as durable state.

Actual safe failure checks used only this owned deployment:

| Condition | Observed diagnostic |
|---|---|
| Generated invalid app credentials | Exit 1, `rejected` / `credentials` |
| Explicit mandated underscore-bearing default bucket | Exit 1, server-side `rejected` / `invalid_bucket`; no silent rename |
| Empty app credentials | Exit 2, `configuration_error` / `configuration` |
| TLS enabled against the local HTTP API | Exit 1, `unavailable` / `tls` |
| Directory supplied as license input to preflight | Exit 2, `minio_license_file_not_file` |
| Stop only the captured owned AIStor container | App health remained 200; storage probe exited 1, `unavailable` / `transport`; owned storage was restarted |

All six failures stopped before PUT and produced no probe key or extra
prediction. Representative current app/server logs contained none of the
checked generated credential values. Two harness issues were observed rather
than hidden: an initial assertion expected client-side bucket rejection, but
the server correctly returned authoritative rejection; a bounded post-restart
health wait initially omitted connection-reset handling. Correcting those
validation expectations/wait handling yielded the passing results above; no
application change or failed-test-to-skip conversion was made.

No uncertain write was manufactured: the existing ambiguity regressions remain
the evidence for that case. Real uncertain-write recovery is deferred rather
than risking another submission or deleting an unacknowledged object. Actual
physical MinIO restore and real-model cross-environment transfer also remain
unrun; the earlier quiesced fixture archive tests do not certify them.

**Cleanup**: first executed ordinary `down` without volume deletion, after the
final durability comparison. Then separately cleaned this disposable test
deployment: exact ownership/unreferenced checks preceded removal of its two
named volumes and two captured image-declared anonymous `/data` volumes. This
intentional test teardown is not a routine recovery instruction. No project
container/network remained; its unique app image tag, generated credential and
snapshot files, and temporary harness were removed. Shared base-image/build
cache and the operator's original license/data/services were untouched.

Final documentation checks passed: 22 PowerShell blocks parsed, 49 local
file/heading links resolved, whitespace checks passed and all 47 task IDs were
unique. The final inventory found no owned containers/networks/volumes or
temporary credential/harness files; the three loopback ports were free again.
Application code, model/label workflows and prediction schema were unchanged.
The existing stack/lock, local inference/provenance, service boundaries,
external secrets, safe failure/uncertainty and honest evidence constraints
remain intact; these checks do not replace final reviewer-dependent approval.

T017/T038/T041/T045 now have full-model/UI and normal lifecycle evidence.
T030's guide reconciliation is complete against the delivered commands,
no-port integration alternative and recorded outcomes. **37/47 tasks complete,
10 pending**. T031/T039/T042/T046 still require the separate repository-only
reviewer walkthrough, and T032-T034/T040/T043/T047 retain their dependent final
gates. No clean reviewer, hosted CI, screen-reader or participant success is
claimed. Earlier missing-license/full-model statements are historical snapshots,
superseded by this follow-up.

Acceptance mapping is in [plan.md](plan.md#requirement-and-acceptance-traceability). Record pass/fail/skip, prerequisite reasons, image/lock identities, and cleanup outcomes; do not substitute this designed guide for observed success.

### Repository-only reviewer walkthrough (2026-11-15)

A separate fresh-context reviewer followed only the README, its linked
repository guides and stated external prerequisites. This was an actual second
walkthrough, not a relabeling of the preceding operator run. The reviewer used
fresh Docker runtime/storage and private locked Python setup, not the existing
native models, caches, labels, credentials or services.

Environment: Windows PowerShell 5.1.19041.7844, uv 0.13.5, private native Python
3.13.17, Docker 29.9.3/Linux amd64 and Compose 5.7.0. Main project:
`zsreview-c3e52c6622fe`; independent shell project:
`zsreview-c3e52c6622fe-shell`. App image:
`sha256:87fa1db1170733ba688cff0d08b85da3394eb282dd092cc862e4932519963ce5`.
The pinned AIStor digest and model revision were unchanged from the earlier
walkthrough. Generated external credentials had restrictive ACLs. The app
explicitly used the README's trusted-local root-pair exception for this
disposable deployment, not a claimed least-privilege production identity.
Server acceptance is not certification of license entitlement or future validity.

For the table below, the Compose prefix is
`docker compose --env-file <private-empty-env> -p zsreview-c3e52c6622fe
-f compose.yaml -f compose.minio.yaml`. Private paths, credential values and
payloads are deliberately omitted.

| Executable example / reviewer action | Expected and observed outcome |
|---|---|
| `uv sync --python 3.13 --locked --all-groups` in private environment storage | Locked Python setup passed. An initial no-sync preflight lacked `urllib3`; the documented locked sync resolved that prerequisite rather than hiding the failed attempt |
| `uv run --locked python scripts\check_deployment.py preflight` | Passed external regular-file checks, without claiming license authenticity |
| `config --quiet`; `build --builder <owned-private-builder> --no-cache app`; `up -d` | Passed. Split the documented build/start into private no-cache BuildKit build and startup to avoid changing shared builder cache; no source or deployment behavior change |
| `uv run --locked python scripts\check_deployment.py health --component app`; same with `minio` | App and node health passed, separately from S3 permission |
| `exec -T app python scripts/check_deployment.py storage --write-probe` | Acknowledged PUT, exact readback and acknowledged own-key cleanup passed |
| Existing Model Management and Candidate-Label Management UI | Intentionally prepared DeBERTa v3 Zero-Shot v2.0 and saved two labels. Model became Ready at `8e7e5af5983a0ddb1a5b45a38b129ab69e2258e8` |
| One Classification submission | Automatically displayed `Prediction saved to MinIO`; no second submission. Request ID `6bf8ef2b-1abb-4733-827b-daa6abc65ead` |
| Private exact-key inspection | Exactly one object under `predictions/`; matching request/input, all 11 documented fields, model/revision, two labels/ranked results, finite descending scores, matching top class/score, UTC timestamp and application version `0.1.0` verified. No payload emitted |
| `stop`; `start`; `up -d --force-recreate`; ordinary `down`; `up -d` | Model Ready and labels reappeared; the same single complete matching record survived. The preceding operator run remains the stronger exact runtime-byte/UID and cold-offline comparison |
| Separate base-Compose app-only startup and health without storage credentials | Passed; independent shell usable and classification disabled with no ready model/labels. This project did not borrow the full deployment's state |

`mc` was unavailable, so its optional `stat`/`cat` examples were **not executed**.
The reviewer derived a one-off private SDK reader from the documented exact
key, 11-field schema and linked data model. It used the app's already-configured
endpoint/credentials, privately compared the fictional input and metadata,
released the GET response, and emitted only safe identities/counts/check
outcomes. Copying that temporary script into the owned app and executing it
passed before and after lifecycle checks. Removing it as the non-root app user
failed because the application directory was not writable; exact removal as
container root succeeded. It was never a build input or permanent source file.
No new inspection service, configuration contract or prediction store was added.

| Reviewer topic inventory | Review outcome and execution boundary |
|---|---|
| FR-021: purpose, architecture, directories, services/UI, configuration, models/provenance, cache/deletion, labels and output schema | Located in README and linked guides; actual preparation/classification/record checks above passed. Model deletion/cache cleanup and label recovery were reviewed, not exercised |
| FR-022: supported prerequisites, native/container paths, setup/run/readiness/stop/restart/validation | Located and commands accounted for above. Native Streamlit launch was not run; final automated suites are recorded separately below |
| FR-023: availability, licensing/mounts, endpoints, process inheritance, credentials, TLS, buckets/permissions, refresh and write uncertainty | Safe corrective actions located for every documented matrix entry; reviewed, not a manufactured failure-matrix execution. Earlier six actual safe failures and automated ambiguity/cleanup regressions remain separate evidence |
| FR-024: sensitive data, storage/retention, authorized inspection, backups, least privilege/TLS and access/coordination limits | Located; private matching-record inspection passed. Physical restore/transfer, destructive reset and a production least-privilege deployment were not executed |
| FR-025: unit/smoke/concurrency/service checks and evidence limits | Commands and explicit eligibility/skip/failure boundaries located. Reviewer did not run automated suites, hosted CI, accessibility or participant checks; parent final gates are separate |

The reviewer found safe next actions for occupied ports, absent/invalid license
files, denied operations despite healthy nodes, incorrect endpoints, missing or
stale environment, credentials, TLS, bucket rejection, owned-volume capacity/
permissions, catalog/marker recovery, stale processing, confirmed failure and
indeterminate writes. Matching records are not resubmitted. Missing keys alone
do not establish non-completion; retry remains deferred without both
authoritative absence and definitive original non-completion. No uncertain write
or destructive recovery was manufactured. Quiesced backup/restore/transfer and
destructive-reset examples remain reviewed-only, not successful real-data checks.

Cleanup individually verified removal of the main project's two service
containers, one network, two named volumes and both captured image-declared
anonymous `/data` volumes; the shell project's app container, network and one
named volume; temporary image aliases/app image; the private builder/helper/cache
volume; generated credentials, empty env file, private uv environment/cache,
harness and three browser-output files. A temporary-script deletion failure was
resolved as described above, not ignored. Shared base images/build cache,
existing builder selection, supplied license, native data and unrelated worktree
were preserved. No broad prune was used; owned resources/private directory were
absent and ports 8501/9000/9001 free afterward.

This completes T031/T039/T042/T046/T048, including US3/AC1-3 and SC-001/SC-008
reviewer obligations. It is not human participant, screen-reader, hosted-job or
license-entitlement approval. **42/49 tasks complete, seven final gates pending**
at this reviewer checkpoint; earlier pending-reviewer snapshots are historical.

### Final local gates and reconciliation (2026-11-15)

The separate reviewer completed before these final gates. No application,
prediction schema, model/label workflow, dependency or CI source was changed
in this pass; permanent edits reconcile directly related documentation/tasks.
Earlier evidence sections are historical checkpoints, superseded by this
section and the independent reviewer evidence immediately above.

| Final command / check | Actual result |
|---|---|
| `uv run --locked ruff check .` | Passed |
| `uv run --locked ruff format --check .` | Passed; 108 files already formatted |
| `uv run --locked mypy app scripts\check_deployment.py` | Passed; 22 source files |
| `uv run --locked pytest tests\unit tests\smoke tests\integration\test_classification_concurrency.py tests\integration\test_label_concurrency.py -q -rs`, with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` | **229 passed, 4 skipped**, 166.51 seconds; skips are the Linux-only CI shell fixtures |
| `uv run --locked pytest tests\integration\test_deployment.py -q -rs -s --tb=short`, with `RUN_DEPLOYMENT_TESTS=1` and the external `MINIO_LICENSE_FILE` | **4 passed**, 244.26 seconds; actual filtered-context/both-target inspection, CPU imports, app-only health/durability/fixture backup, loopback configuration and real isolated complete-record storage all passed |
| Network-disabled Linux suite inside the validation image, executed by the preceding command | **234 passed, 4 explicit opt-in skips**, 128.19 seconds; all four CI shell eligibility/nonzero branches ran. Inner container recursion and direct storage opt-ins were absent; the outer run separately executed eligible real storage |
| Native preliminary run while the reviewer was active | **4 failed, 225 passed, 4 skipped**, 364.42 seconds; four existing Windows spawned-writer readiness deadlines expired. These failures were retained, not converted to skips. The unchanged sequential final combined run above passed |
| Lightweight isolated AppTest entry-point observation | Confirmed that AppTest replaces `__main__` and its file identity; Windows spawn can re-import that entry point. No model/storage use, timeout change, test omission or application workaround was introduced |
| Final source/lock/ignore inspection | No app-contract file changes; Python floor and both Windows/Linux torch variants preserved. Only torch's CPU variant differs; 19 Linux CUDA/NVIDIA/Triton packages removed, no unrelated package versions changed. Nine synthetic sensitive-path ignore checks passed; `.env.example` remains included |
| Documentation validation | 22 README/quickstart PowerShell blocks parsed; 51 local file/heading links across seven documents and whitespace checks passed after reconciliation. All 49 task IDs are unique and checked. Syntax checks supplement, not replace, the recorded actual PowerShell/reviewer commands |
| Final cleanup inventory | Zero `zeroshot-test-` containers, networks, named volumes or image tags remained. Fixture-owned anonymous volumes are removed with captured owned containers. Exactly two remaining generated final-test credential files were then removed; original license and operator data were untouched |

The inner Linux run emitted one non-failing pytest cache-permission warning:
the non-root validation user cannot create a cache under the application source
directory. Tests completed successfully; no permission broadening or unrelated
image change was made to suppress that warning. Ordinary suites remained
offline and downloaded no models. Native Python was 3.13.17; container Python
remained the pinned 3.13.18/CPU runtime. Python 3.11 locked resolution/export
evidence remains distinct from an unrun hosted 3.11 job.

The final run includes existing generated-sentinel tests for default and
verbose/locals-enabled pytest reports/JUnit artifacts, safe Docker/helper failure
summaries and joint operation/cleanup failure propagation. Filtered-context and
runtime/validation-image checks used generated forbidden inputs, not the real
license or user data. Earlier actual safe failures, owned-helper/nested-test
failures, quiesced fixture archive checks and full-model exact-byte/UID
comparisons remain valid separate evidence. Required executed failures were
never reclassified as prerequisite skips.

#### Functional requirement reconciliation

| Requirement | Delivered behavior and actual evidence |
|---|---|
| FR-001 | Docker/Compose deployment; operator and fresh reviewer startup/classification passed |
| FR-002 | Mandated stack/floor/uv lock retained; lock audit, locked builds, CPU imports and final native/Linux regressions passed |
| FR-003 | Supported pinned AIStor and external-license guidance; real licensed complete-record integration passed, without entitlement certification |
| FR-004 | External secrets/license and deny-by-default source context; actual filtered-input/both-image sentinels, safe reports and ignore checks passed |
| FR-005 | Host API/Console/internal DNS, TLS and process context documented; reviewer and actual endpoint/TLS checks support the distinction |
| FR-006 | Loopback publications verified; no-port automated fixtures and trusted-local/access-control limits retained |
| FR-007 | Whole runtime and MinIO volumes; exact operator hashes/UIDs/object bytes survived every normal lifecycle operation; reviewer confirmed model/labels/record |
| FR-008 | Existing locks and canonical sidecars retained; both process suites passed. Native/Docker separation remains autonomous; real transfer unrun |
| FR-009 | Safe preflight, bounded health and explicit acknowledged storage probe passed; unit failure matrix and six actual safe failures distinguish node health from usable storage |
| FR-010 | Actual independent app-only startup/health passed without storage credentials, both in fixture and separate reviewer project |
| FR-011 | Exact default preserved; explicit valid override and actual authoritative underscore-bucket rejection verified, no silent substitution |
| FR-012 | Two independent one-submit browser walkthroughs automatically displayed saved completion and privately matched complete request/provenance records |
| FR-013 | Ordinary stop/recreation/down preserve data; stopped fixture backup/restore passed. Real physical MinIO restore is not claimed |
| FR-014 | Exact-key inspection/no-blind-retry guidance reviewed; ambiguity regressions retain identity and require absence plus non-completion. No real uncertain write manufactured |
| FR-015 | Existing CI extended; final Ruff/type/unit/smoke/concurrency checks passed locally and Linux regression ran inside validation |
| FR-016 | Locked versions, offline ordinary suites, explicit CPU source and generated sensitive-output/image sentinels passed |
| FR-017 | Actual isolated selected AIStor/SDK complete-record test passed, requiring a passed inner testcase rather than skip-shaped success |
| FR-018 | All four actual Linux CI shell eligibility/exit-propagation fixtures passed; missing prerequisites remain named skips with local alternative, configured-invalid inputs fail |
| FR-019 | Exact-key and captured owned-resource cleanup passed; unrelated test sentinel survived prediction cleanup, no existing bucket deleted |
| FR-020 | Disposable Ruff lint/format, mypy, pytest and helper/nested-test failures produced expected nonzero results and safe diagnostics; hosted jobs remain unrun |
| FR-021 | Fresh reviewer located every architecture/config/model/label/schema topic and executed preparation/classification/inspection |
| FR-022 | Actual Windows PowerShell 5.1 setup/readiness/lifecycle/reviewer commands plus corrected ownership/archive fixtures passed; unsupported/unavailable shell coverage not inferred |
| FR-023 | Reviewer located every safe corrective action; earlier real safe failures and current configuration/uncertainty/cleanup regressions remain separate evidence |
| FR-024 | Private authorized inspection, retention/backup/privacy/TLS/access/coordination limits reviewed; no payload published or production-security claim |
| FR-025 | All local gates have explicit outcomes and skip reasons; operator/reviewer/hosted/accessibility/participant evidence remains distinguished |

#### Acceptance scenario reconciliation

| Scenario | Evidence |
|---|---|
| US1/AC1 | Fresh normal deployment, readiness and actual loopback publications passed |
| US1/AC2 | Both operator and independent reviewer automatically observed saved completion and exactly one matching complete record |
| US1/AC3 | Operator exact runtime/object preservation and cold offline ready-model reuse passed; reviewer lifecycle and lightweight fixtures independently passed |
| US1/AC4 | Six actual safe setup failures plus CLI/unit failure branches passed without false success |
| US1/AC5 | Independent app-only/no-storage startup and management shell passed |
| US1/AC6 | Authorized key inspection/no-resubmit rules reviewed; late/uncertain-write regression behavior passed without a real manufactured ambiguous PUT |
| US2/AC1 | Local quality and process selectors plus Linux offline regressions passed; hosted execution remains unrun |
| US2/AC2 | Representative required check/helper failures returned nonzero with safe diagnostics; no hosted-job claim |
| US2/AC3 | Isolated real complete record, own-key/sentinel cleanup and captured-resource cleanup passed |
| US2/AC4 | Linux actual eligibility script branches verified named missing-license skips/local alternative and preserved executed nonzero failures |
| US3/AC1 | Separate fresh-context repository-only reviewer reached saved classification and private matching-record inspection |
| US3/AC2 | Separate reviewer located corrective actions for every documented setup/uncertainty condition |
| US3/AC3 | Separate reviewer located architecture/config/provenance/persistence/testing/privacy topics and explicit evidence limits |

#### Success criteria and constitution reconciliation

| Criterion | Result within the tested scope |
|---|---|
| SC-001 | Separate clean reviewer setup, model/labels, saved classification and exact private record inspection passed |
| SC-002 | Both tested successful browser requests automatically completed and each matched one complete record without resubmission |
| SC-003 | All tested normal non-destructive lifecycle comparisons passed; cold local ready-model reuse passed |
| SC-004 | Every tested setup failure had safe corrective guidance; reviewer found next actions for all matrix entries |
| SC-005 | Required local gates observable and passing; representative failure commands nonzero. Hosted job execution explicitly unrun |
| SC-006 | Eligible real integrations passed complete records; ineligible inner/fork/license conditions explicitly distinguished from executed failures |
| SC-007 | Zero unrelated deletion observed; exact owned cleanup and report/context/image sentinels passed |
| SC-008 | Separate reviewer located all FR-021 through FR-025 topics; every used example has executed, reviewed-only, deferred or prerequisite status above |

| Constitution principle | Final check |
|---|---|
| 1: mandated stack | Existing Python/PyTorch/Transformers/Streamlit/MinIO retained |
| 2: typed reproducible Python | Floor/universal lock preserved; Ruff/strict mypy/locked builds passed |
| 3: reproducible models | Explicit immutable revision, local PyTorch loading and cold offline reuse; no ordinary model downloads |
| 4: modular boundaries | App/service interfaces unchanged; diagnostics reuse existing settings/client |
| 5: Streamlit lifecycle/state | Automatic saved completion and session identity preserved; no durable-future claim |
| 6: configuration/secrets | External credentials/license, filtered context, secret-safe reports; local HTTP/root exception not a production claim |
| 7: prediction persistence | MinIO complete record/default/confirmed-write contract retained; actual matching records verified privately |
| 8: safe failure | Loopback/trusted-local deployment, validated boundaries and actionable uncertainty/recovery without blind retry |
| 9: quality gates | Final native/Linux/container/service suites passed; platform/opt-in skips and hosted limits explicit |
| 10: observability/docs | Non-sensitive metadata/reporting and complete reviewer-validated guide; no unrun success claims |

**Final implementation status: 49/49 tasks complete.** This closes
T032-T034/T040/T043/T047/T049 after the actual reviewer prerequisite, not by
waiving it. Remaining evidence limits are unchanged: hosted CI, PowerShell 7
and Linux-host PowerShell, participant/screen-reader checks, actual physical
MinIO restore and real-model cross-environment transfer are unrun; real
uncertain-write recovery was deliberately not manufactured. These limits are
not passing coverage or license/security certification. No commit or push was
performed; unrelated source/data/services and shared caches were preserved.

## 9. Quiesced backup, restore and transfer

Only use archives you created and trust. Protect backups with restrictive
permissions; they may include input/predictions, HF token-home files and server
configuration. Back up external secret/license material separately through your
approved secure process, never into source or images.

Stop all writers, including native apps using the source data. Resolve or defer
uncertain requests first. For the normal Docker project:

```powershell
docker compose -p zeroshot-local -f compose.yaml -f compose.minio.yaml stop
if ($LASTEXITCODE -ne 0) { throw 'Stop failed; writers are not confirmed stopped' }
$sourceVolumes = @('zeroshot-local_app-runtime', 'zeroshot-local_minio-data')
foreach ($name in $sourceVolumes) {
    $volumeJson = docker volume inspect $name
    if ($LASTEXITCODE -ne 0) { throw 'Volume inspection failed; ownership not confirmed' }
    $volumeInfo = @(($volumeJson -join "`n") | ConvertFrom-Json -ErrorAction Stop)
    if ($volumeInfo.Count -ne 1 -or
        $volumeInfo[0].Labels.PSObject.Properties.Name -cnotcontains 'com.docker.compose.project' -or
        $volumeInfo[0].Labels.'com.docker.compose.project' -cne 'zeroshot-local') {
        throw 'Volume ownership not confirmed'
    }
    $running = docker ps -q --filter "volume=$name"
    if ($LASTEXITCODE -ne 0 -or $running) { throw 'Writers are not confirmed stopped' }
}
$utility = 'python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90'
$backupDir = Join-Path $env:USERPROFILE ('zeroshot-backups\' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
docker run --rm --network none --mount "type=volume,src=zeroshot-local_app-runtime,dst=/data,readonly" --mount "type=bind,src=$backupDir,dst=/backup" $utility python -c "import tarfile; t=tarfile.open('/backup/app-runtime.tar','w'); t.add('/data',arcname='.'); t.close()"
if ($LASTEXITCODE -ne 0) { throw 'Runtime backup failed' }
docker run --rm --network none --mount "type=volume,src=zeroshot-local_minio-data,dst=/data,readonly" --mount "type=bind,src=$backupDir,dst=/backup" $utility python -c "import tarfile; t=tarfile.open('/backup/minio-data.tar','w'); t.add('/data',arcname='.'); t.close()"
if ($LASTEXITCODE -ne 0) { throw 'MinIO backup failed' }
```

The utility runs only against exact verified volumes. Record the private backup
location and compatible app/server image identities; do not publish archive
contents. This is a stopped physical backup, not a promise of live consistency.
The JSON lookup avoids embedded Go-template quotes that Windows PowerShell 5.1
can strip from native arguments. Failed inspection, invalid JSON, mismatched or
missing ownership, or a running writer stops the block before archive creation.

Restore to a **new** project so existing data is not overwritten:

```powershell
$restoreProject = 'zeroshot-restored-' + [Guid]::NewGuid().ToString('N')
$restoreApp = $restoreProject + '_app-runtime'
$restoreStorage = $restoreProject + '_minio-data'
docker volume create --label "com.docker.compose.project=$restoreProject" --label 'com.docker.compose.volume=app-runtime' $restoreApp
if ($LASTEXITCODE -ne 0) { throw 'Restore volume creation failed' }
docker volume create --label "com.docker.compose.project=$restoreProject" --label 'com.docker.compose.volume=minio-data' $restoreStorage
if ($LASTEXITCODE -ne 0) { throw 'Restore volume creation failed' }
docker run --rm --network none --mount "type=volume,src=$restoreApp,dst=/data" --mount "type=bind,src=$backupDir,dst=/backup,readonly" $utility python -c "from pathlib import Path; import tarfile; assert not any(Path('/data').iterdir()); t=tarfile.open('/backup/app-runtime.tar'); t.extractall('/data',filter='tar'); t.close()"
if ($LASTEXITCODE -ne 0) { throw 'Runtime restore failed' }
docker run --rm --network none --mount "type=volume,src=$restoreStorage,dst=/data" --mount "type=bind,src=$backupDir,dst=/backup,readonly" $utility python -c "from pathlib import Path; import tarfile; assert not any(Path('/data').iterdir()); t=tarfile.open('/backup/minio-data.tar'); t.extractall('/data',filter='tar'); t.close()"
if ($LASTEXITCODE -ne 0) { throw 'MinIO restore failed' }
```

Trusted archive metadata preserves directory relationships/UIDs/modes. Verify
app UID 10001 can use its runtime tree and inspect provenance, all caches,
catalog/initialization/lock sidecars before restarting. Supply an authorized
license/credentials for the restored compute and use the same compatible image
identities; do not perform unsupported server downgrades. Once verified and ports
are free, start with `docker compose -p $restoreProject -f compose.yaml -f
compose.minio.yaml up -d --build`. Original volumes remain untouched.

### Operator-controlled native/Docker transfer

1. Stop **all** source/destination writers and make the backups above. Inventory
   actual settings, not assumed defaults; include app-owned library caches
   outside the native model tree without copying unrelated global caches.
2. Prepare a private staging tree outside the checkout with this mapping:

   | Source | Staging/Docker runtime destination |
   |---|---|
   | Configured native `MODEL_DIR`, including manifests/staging | `models/` |
   | Model-use locks in its parent, named for configured model directories | Runtime parent, unchanged filenames |
   | Configured `HF_HOME` and its token/cache state | `hf-home/` |
   | Configured explicit adapter cache | `hub-cache/` |
   | Effective app-owned library hub/XDG caches | `hf-home/hub/`, `xdg-cache/` |
   | Label catalog plus `.initialized`, `.lock`, temp sidecars | `labels/catalog.yaml` plus corresponding suffixes |

3. Preserve provenance and relative cache relationships; do not merge catalogs,
   strip initialization evidence, alter manifests to claim ready, or share live
   native/container files. Use a new verified destination volume/project and
   explicit compatible permissions. Copy only the inventoried stopped app data.
4. Revalidate ready-model status, label recovery and cache cleanup previews at
   the destination before enabling writers. Cross-platform cache/ready usability
   is not assumed; use existing management recovery if validation fails.

No automatic migration or concurrent Windows/Linux lock sharing is introduced.
Real-model transfer and physical MinIO restore require their separate walkthrough;
lightweight artifact checks cannot certify them.

### Destructive reset (never routine recovery)

**Irreversible: deletes models, labels, caches and predictions.** First make and
verify backups, stop/remove only this project's containers with ordinary `down`,
and verify ownership of the exact two volumes as above. Only after explicit
operator confirmation:

```powershell
if ((Read-Host 'Type DELETE zeroshot-local to destroy the verified backed-up volumes') -eq 'DELETE zeroshot-local') {
    docker volume rm zeroshot-local_app-runtime zeroshot-local_minio-data
}
```

Do not use wildcard deletion or global prune. Do not apply this command to
another project or use it to repair an uncertain write.

## 10. Repository-only reviewer matrix

Use only [README](../../README.md) plus linked repository guides and stated
external prerequisites. Record command, environment/runner, image/lock identities,
expected result, observed pass/fail/unrun/explicit prerequisite skip, and exact
owned-resource cleanup status. Never attach credentials, license contents,
input or prediction JSON.

| Requirement topics | Reviewer action | Evidence |
|---|---|---|
| FR-021 | Locate purpose/module tree/models/provenance/settings/labels/schema | Topic links and actual module/config comparison |
| FR-022 | Follow clean native/Compose startup/readiness/stop/restart/tests | Recorded copyable commands/results |
| FR-023 | Exercise safe failure matrix and uncertainty inspection | Safe category and corrective next action |
| FR-024 | Locate retention/access/backup/TLS/locking limitations | Private backup/inspection and quiesced-owner review |
| FR-025 | Account for every validation example and skipped prerequisite | Observed outcomes, not inferred usability/accessibility |

The recorded repository-only walkthrough and cold ready-model reuse passed.
Physical MinIO restore, real-model transfer, and participant/screen-reader
checks remain unverified.
