# Research: Deployment, CI, and Developer Documentation

Implementation verification found that copying source and setting `PYTHONPATH`
alone did not preserve installed-package importability outside the checkout.
The dependency stage now installs the local project after copying approved app
source, using `uv sync --locked --no-dev --no-build-isolation`. Its setuptools
backend is the existing locked runtime dependency (84.2.1), not an independently
resolved build environment. The final image retains no uv/build invocation.

**Date**: 2026-11-14. Decisions apply to planning; recheck supported distribution and immutable identities at implementation/update time.

**Implementation recheck (2026-11-15)**: Official container/license documentation
still specifies AIStor, external active licensing, and single-compute Free Tier
registration. The three index digests below were re-resolved successfully.
Docker 29.9.3 reports a local Linux x86_64 engine; uv is 0.13.5.
Reviewed public action tag identities: checkout v4
`11d5960a326750d5838078e36cf38b85af677262`, setup-python v5
`a26af69be951a213d495a4c3e4e4022e16d87065`, setup-uv v6
`d0cc045d04ccac9d8b7881df0226f9e82c39688e` (dereferenced commit;
the annotated v6 tag object is `d0d8abe699bfb85fec6de9f7adb5ae17292296ff`).
At the initial implementation recheck, no external license or app/root
credentials were supplied. Existing operator services are never borrowed.

**Supplied-license follow-up (2026-11-15)**: An externally supplied license
enabled actual isolated complete-record write/read integration with the pinned
AIStor image below, whose binary reports `RELEASE.2026-09-19T17-05-25Z`.
The validation image uses locked MinIO SDK 7.2.20 and generated temporary
server/app credentials. The selected storage test passed, then passed again
alongside the app durability regression (2 passed, 2 deselected). Full-model
and reviewer walkthroughs remain unrun; successful server operations do not
certify license entitlement, renewal or authorization for other deployments.
The pinned image declares an additional anonymous `/data` volume, while this
recipe stores predictions at `/mnt/data`. Tests now distinguish Docker-created
anonymous mounts from explicit unowned mounts and remove anonymous volumes
only through their captured owned containers; named data volumes still require
project-label verification and exact cleanup.

**Later execution status (2026-11-15)**: The separate full-model/operator and
fresh-context repository-only reviewer walkthroughs have now passed, followed
by final local quality/container/licensed-storage gates. Earlier unrun statuses
above describe their original checkpoints; see the authoritative
[final evidence](quickstart.md#final-local-gates-and-reconciliation-2026-11-15).
Hosted CI, participant/accessibility, physical MinIO restore and real-model
cross-environment transfer remain unrun.

## 1. Supported storage distribution

**Decision**: Use current MinIO AIStor's container distribution with externally obtained valid licensing. Target one Linux amd64 compute resource and data volume. Use AIStor Free where its terms and registration permit the developer's use.

**Rationale**: Official instructions identify `quay.io/minio/aistor/minio`, `minio server /mnt/data --license /minio.license`, API 9000 and console 9001. Official licensing requires an active license available through SUBNET; the free offering is single-compute and has support limitations. A missing/invalid license can deny S3 while Console/health endpoints still respond. Do not equate a free license with unconditional, forever-available licensing or product support.

**Alternatives considered**: Archived community distributions/old binary download instructions are not a supported default. Replacing MinIO is out of scope. Paid AIStor remains an operator option, not a project prerequisite beyond valid licensing.

**Sources**:
- [Official container installation](https://docs.min.io/aistor/installation/container/install/)
- [Licensing and renewal](https://docs.min.io/aistor/operations/licenses/)
- [Offering and registration](https://min.io/pricing)
- [Root credentials and file settings](https://docs.min.io/aistor/reference/aistor-server/settings/root-credentials/)

Licensing docs explicitly distinguish normal, read-only, and offline states. The server can remain alive when S3 is blocked. License-specific timing claims can override defaults, so troubleshooting must inspect the actual license state rather than promise a universal grace period.

## 2. Immutable runtime identities

**Decision**: Select these registry-observed index digests, with `linux/amd64` explicitly selected:

| Component | Immutable image reference | Observed amd64 child digest |
|---|---|---|
| Python | `python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90` | `sha256:48d884813cf44e927cf64c5529dd630dd3b18338c6dc727991eef9b71e934a20` |
| uv | `ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff` | `sha256:a12ede1e6dc90d3b3e600d0901731e71f0ab0f4d72683ea097b76c19c43cc8df` |
| AIStor | `quay.io/minio/aistor/minio:latest@sha256:107cf2014a9583c74c11e3cdbd6903d89c2244355886b89ce532f4ecae9c23f3` | `sha256:a94e1fe399bd050fe6d6148839597a4995350c0e62c9e83f0cec8b5630ed0a1e` |

**Rationale**: `docker buildx imagetools inspect` resolved public metadata without pulling layers or starting services. Python's manifest reports `3.13.18-slim-trixie`. AIStor's digest, not the moving `latest` label, is the immutable release identity. Record its binary release/version on the first executed validation. Digest existence is not evidence of successful startup, licensed storage, or model loading.

**Alternatives considered**: Moving tags alone are not reproducible. ARM manifests exist but do not establish a tested ARM deployment. Building AIStor from source is unnecessary.

**Update policy**: Review official support/license changes, resolve candidate index/platform digests, rebuild with the universal lock, and run packaging, CPU import/inference, persistence, license/failure, concurrency, service integration, and reviewer checks before changing selected identities. Do not silently refresh tags.

**Sources**:
- [Official Python image](https://hub.docker.com/_/python)
- [uv Docker integration and digest pinning](https://docs.astral.sh/uv/guides/integration/docker/)
- Public registry metadata for the references above.

## 3. Linux CPU dependencies without a second lock

**Decision**: During implementation configure an explicit `pytorch-cpu` uv index at `https://download.pytorch.org/whl/cpu`, source `torch` from it only when `sys_platform == 'linux'`, and regenerate the existing universal lock. Preserve the Python >=3.11 constraint and Windows PyPI resolution. Keep other packages on their existing indexes.

**Rationale**: Current lock selects torch 2.15.0 with Linux CUDA/NVIDIA dependencies; Windows CPU behavior does not establish CPU-only Linux packaging. Official uv documentation supports explicit indexes and source markers. Current cp311 and cp313 Linux amd64 wheels were independently observed:

| Published wheel | SHA256 |
|---|---|
| `torch-2.15.0+cpu-cp311-cp311-manylinux_2_28_x86_64.whl` | `cee15855a32ad89a9bb27b8a9d6e07a859dcd2e11ed1b5561f3d6206e31a103b` |
| `torch-2.15.0+cpu-cp313-cp313-manylinux_2_28_x86_64.whl` | `0f6f69701b2d38ddc412364dfb92e2e13e74960d33fa3573b4930ced626e81c7` |

This verifies published availability, not installation or inference. Implementation must verify cp311 and cp313 resolution, lock consistency, runtime import/CPU inference, and no accidental unrelated dependency downgrade. Python slim-trixie is the selected glibc-based candidate, not a musl image.

**Alternatives considered**: Keep Linux CUDA wheels (unnecessary GPU weight for CPU scope); replace torch after locked install (breaks reproducibility); maintain a separate platform lock (unnecessary drift); downgrade Hub/Transformers (risks existing cache-prune behavior).

**Sources**:
- [uv PyTorch indexes and platform sources](https://docs.astral.sh/uv/guides/integration/pytorch/)
- [Official CPU wheel index](https://download.pytorch.org/whl/cpu/torch/)
- Existing `pyproject.toml`, `uv.lock`, and model adapters.

## 4. Runtime persistence and coordination

**Decision**: Mount the entire application runtime parent, not just `MODEL_DIR`; keep all app durable paths under `/runtime`. Mount MinIO storage separately.

**Rationale**: `app/services/model_manager.py:model_use_guard` resolves the model root and places `.<model-directory-name>.use.lock` in its parent. `app/services/label_manager.py` places `.initialized`, `.lock`, and atomic replacement sidecars beside the canonical catalog. Native locking uses preserved lock files, with no soft-lock fallback. The existing label initialization marker distinguishes missing-after-initialization from first use. Losing it would lose recovery evidence.

**Alternatives considered**: Only mounting models loses their parent locks; only mounting the label YAML loses initialization/coordination evidence. Concurrent Windows/WSL/container bind-sharing introduces unsupported canonical identity/locking assumptions. Network filesystems and multi-host are out of scope.

**Transfer**: Keep native Windows/Docker files separate, as the specification's autonomous default. Stop all writers before export/import, preserve provenance and marker data, and verify the destination's canonical layout and native locks. Do not merge live files or overwrite initialized state automatically.

## 5. Independent startup and external provisioning

**Decision**: Base Compose contains only app; a second Compose file adds storage and its required file inputs. No storage health dependency for app startup. App credentials remain optional environment inputs; server root credentials use external file-backed secrets.

**Rationale**: Compose interpolates required variables even for services an operator may not intend to start. Separating required license/root-file interpolation preserves shell startup without MinIO prerequisites. Long-form license bind with `create_host_path: false` prevents accidental creation of a directory. Server `_FILE` values are container secret paths; Compose secret sources are host paths.

**Alternatives considered**: Single file with globally required server interpolation blocks independent startup. Default root passwords violate safe provisioning. New application `_FILE` settings/entrypoint credential loaders duplicate the existing config mechanism.

**Sources**:
- [Compose interpolation and required/default values](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Compose services: ports, dependencies and volume binds](https://docs.docker.com/reference/compose-file/services/)
- [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)
- [Docker Desktop Windows requirements](https://docs.docker.com/desktop/setup/install/windows-install/)

Docker Desktop requires a supported Windows/WSL 2 environment, virtualization, adequate memory/disk, and Linux containers. Document current vendor prerequisites rather than claim all Windows versions/architectures work. `docker compose config` can disclose resolved credentials; only quiet validation is suitable for routine copied commands.

## 6. Readiness, failures, and CI eligibility

**Decision**: Distinguish app shell health, AIStor liveness/node readiness, and authorized write/read permission. Use bounded no-retry opt-in probes with unique `healthchecks/` keys. Reuse the existing prediction integration test in an isolated eligible CI deployment.

**Rationale**: Official endpoints `/minio/health/live` and `/minio/health/ready` indicate process/node health, not license-authorized S3 operations. The application MinIO client already disables urllib3 retries and uses 5-second connection/30-second read timeouts. Preserve that behavior. A probe uses safe content, not a real prediction, and never overwrites prediction UUID keys.

The existing integration test opts in with `MINIO_TEST_BUCKET`, writes/reads complete JSON using a UUID, deletes only its acknowledged exact object, and does not delete a bucket. It has no model inference. Extend the existing CI rather than create duplicate quality jobs.

**Alternatives considered**: Health-only success can lie about usable storage; production-bucket probes using prediction keys can pollute results; blind PUT retries can conceal uncertainty; treating invalid supplied licenses/test failures as skips hides regressions. Mock results are not service-backed coverage.

**Sources**:
- [AIStor health probes](https://docs.min.io/aistor/operations/monitoring/healthcheck-probe/)
- [AIStor license states](https://docs.min.io/aistor/operations/licenses/)
- Existing `app/services/prediction_store.py`, `tests/integration/test_prediction_storage.py`, and `.github/workflows/ci.yml`.

## 7. U1: Port-independent automated validation

**Decision**: Use a unique project and `docker compose run -d --no-deps --use-aliases --name <owned-name>` for test service containers, with neither `--service-ports` nor explicit publication. Run health/persistence clients in the validation image on the verified owned network. Implement the fixture in `tests/integration/test_deployment.py` and reuse it in CI/local validation; no new Compose override file is needed.

**Rationale**: Official Compose run documentation explicitly states that run does not publish service-configured ports, preventing collisions with already-open ports. It retains the service configuration/volumes; `--no-deps` prevents implicit service startup and `--use-aliases` provides the service aliases within the unique project network. A unique project alone would not prevent collisions from normal `up` using fixed host publications.

The fixture must verify actual container/project/network ownership and no host port bindings before probing. It supplies test-only client settings, uses `minio:9000`/`app:8501` internally, and never falls back to host localhost. It recreates only its captured containers with the same owned volumes. The full-model operator walkthrough separately verifies the documented normal deployment commands and requires its local ports to be available.

**Alternatives considered**: Reserve/find free host ports (allocation races and extra routing); ephemeral host publication (unnecessary for service-backed automated tests); merge overrides (additional files/version-specific merge rules); stop an existing server (violates unrelated-resource safety).

**Source**: [Official Compose run behavior and options](https://docs.docker.com/reference/cli/docker/compose/run/) verified during this re-plan. This is source verification, not an executed networking test.

## 8. U2: One controlled context, two image targets

**Decision**: Remove the separate named test context. Use the existing root context with one deny-by-default `.dockerignore` that explicitly allows approved app/test Python source and necessary non-secret inputs. Only the validation target copies approved tests; runtime COPY inputs exclude them.

**Rationale**: Official Docker documentation identifies `.dockerignore` in the context root as the filter applied before transfer, documents negation/last-match rules, and describes named contexts as separate input sources. A single context avoids an unverified second filtering mechanism. Current repository test fixtures are Python source; generated `__pycache__` artifacts also exist and must not be included. A broad tests-directory allow rule is insufficient: list approved file paths and exclude generated/runtime/secret material, including unlisted files under approved ancestors.

Verify filtering against a disposable context copy containing generated forbidden sentinels, using an inspection build that observes the filtered context itself. Checking runtime COPY output alone cannot establish that excluded data was never sent to the builder. Separately verify runtime has no tests/dev tooling and validation contains approved tests without runtime-generated sentinels. Keep test sentinel values generated at execution, not embedded as secret-like constants in source/image fixtures.

**Alternatives considered**: Named contexts with separate filters/staging helper (unnecessary extra machinery); a second Dockerfile-specific ignore policy (duplicate allowlist maintenance); excluding all tests and mounting an unfiltered source tree at validation time (moves rather than solves the sensitive-input boundary).

**Source**: [Official build-context and ignore-file behavior](https://docs.docker.com/build/concepts/context/) verified during this re-plan. Approved non-sensitive test source in the shared context is an intentional change to the earlier plan, not an exception to the specification's sensitive-data exclusions.

## Execution prerequisites and evidence limits

Research has resolved design choices. External prerequisites remain: a valid license authorized for the intended isolated/local compute resource, supported Docker/WSL or Linux runtime, network access to selected images/dependencies, sufficient disk/memory, and intentional model-download access for the full walkthrough.

No image was built, service started/stopped, license inspected, lock changed, or service-backed test run during planning or this re-plan. No-port fixture behavior and the single-context allowlist still require actual implementation tests. CI eligibility with the actual selected server/client/license combination must be recorded during implementation. If license terms do not permit the proposed CI instance, report that explicit prerequisite limitation and the reproducible local alternative; do not invent licensing permission.
