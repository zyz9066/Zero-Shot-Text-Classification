# Quickstart: Text Classification and Prediction Persistence

## Prerequisites and configuration

- Python 3.11+, `uv`, and the committed dependency lock.
- A ready app-managed zero-shot model and a valid saved candidate-label set with at least two labels. Prepare them through the existing Model Management and Candidate-Label Management pages; model downloads remain part of the existing management workflow.
- A reachable MinIO-compatible service and authorized operator. Set `MINIO_ENDPOINT`, `MINIO_SECURE`, `MINIO_ACCESS_KEY`, and `MINIO_SECRET_KEY` in the process environment or an approved secret manager. Do not commit credentials or enter sensitive input for a test.
- `MINIO_BUCKET` may override the bucket in `configs/app.yaml`; otherwise the required default is `zeroshot_learning_output`. Some S3-compatible services reject that underscore-containing default. Configure a service-accepted bucket explicitly; the application reports rejection and never selects a different bucket or store on its own.
- Prediction data is written to `predictions/<request-id>.json` in the configured bucket. The feature does not impose retention or delete records; retention is determined by the service's bucket policy and authorized operator actions. Treat both input text and predictions as sensitive.
- Use only a local or otherwise trusted environment unless separate authentication and authorization are provided. Navigation visibility is not access control. Use TLS where supported and least-privilege storage credentials.

The application shell and classification page can start without MinIO credentials; credentials are required only when a prediction is written.

## Launch and classify

```powershell
uv sync --locked
$env:MINIO_ENDPOINT = "localhost:9000"
$env:MINIO_SECURE = "false"
$env:MINIO_ACCESS_KEY = "<authorized-access-key>"
$env:MINIO_SECRET_KEY = "<authorized-secret-key>"
$env:MINIO_BUCKET = "zeroshot-learning-test"
uv run --locked streamlit run app\streamlit_app.py
```

Set secrets through your normal secure environment configuration rather than committing or recording their values. Omit `MINIO_BUCKET` to use the configured/default bucket. In the Classification page, confirm the storage notice, choose a ready model and saved label set, enter text, and submit. A successful request displays one top class and every label's finite score in descending order, plus model provenance and timestamp, only after MinIO confirms the write. Scores are not described as calibrated probabilities. Input that exceeds the full model pair limit is rejected without truncation or splitting and remains available for editing.

During an active submission, an exact repeat (same text, model ID/revision, and label-set ID/revision) shows the existing request status. A changed text or selection is retained but not started until the active request finishes. A later intentional request receives a new request ID.

## Inspect records and recover uncertain writes

The UI displays a request ID. An authorized operator can inspect the exact object using their already-configured MinIO-compatible client, for example:

```powershell
mc stat <alias>/<bucket>/predictions/<request-id>.json
mc cat <alias>/<bucket>/predictions/<request-id>.json
```

Use the content command only when authorized; the object contains submitted text and prediction data. Compare the record's request ID, exact input, labels and scores, model name/identifier/revision, timestamp, and application version. Do not copy its contents or credentials into logs, tickets, or chat.

For an indeterminate write, the application gives the request ID and instructs the user to ask an authorized operator to inspect that key:

- If the matching record exists, do not resubmit.
- To establish absence, have an authorized operator query the exact key from the configured authoritative service after checking that service's consistency guarantees. To establish non-completion, use the deployment's client/proxy/server request evidence or a documented quiescence procedure to confirm the original PUT has terminated and cannot be replayed or complete later. A single missing-object lookup, client timeout, process restart, or elapsed wait does not establish both facts.
- If service and transport evidence cannot establish both facts, leave the outcome unresolved and escalate. There is no universal safe waiting interval.

A confirmed rejection is reported as a failed write, not a successful classification. Do not substitute another store or bucket. The entered text remains in the session for correction or recovery.

## Automated checks

```powershell
uv run --locked pytest tests\unit tests\smoke tests\integration\test_classification_concurrency.py tests\integration\test_label_concurrency.py
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
```

The classification/storage integration test is opt-in and must use an isolated test bucket. With an accessible service, the required MinIO settings, and permission to use that bucket:

```powershell
$env:MINIO_TEST_BUCKET = "zeroshot-integration-test"
uv run --locked pytest tests\integration\test_prediction_storage.py
```

Expected result: write one complete record and read it back; the test removes only the object it created and does not remove a bucket. Without `MINIO_TEST_BUCKET`, the test skips without contacting a service.

## Validation record

- Unit, smoke, and cooperating-process tests: **174 passed** with the command above.
- Ruff lint: **passed**. Ruff formatting: **95 files already formatted**. Strict mypy: **passed for 21 application source files**.
- Locked versions used for verification: PyTorch `2.15.0+cpu`, Transformers `5.23.0`, Hugging Face Hub `2.4.0`, and MinIO client `7.2.20`. Keeping Hub 2.x avoids breaking the existing `hf cache prune` model-management workflow.
- MinIO service-backed integration: **not run**; no isolated `MINIO_TEST_BUCKET` service configuration was provided. The opt-in test was confirmed to skip.
- Accessibility check: AppTest verified saved, active/blocked, and indeterminate outcome messages. The browser accessibility snapshot confirmed explicit names for Model, Candidate-label set, and Text to classify, plus alert/status roles for trusted-environment guidance and the storage notice. Keyboard Tab navigation reached the named model and text controls, and keyboard-entered text remained visible. A manual screen-reader session was not available; this is not a WCAG conformance claim.
- First-attempt usability target (SC-006): **unverified**; no participant exercise was conducted. Do not claim that the 90% target has been met.

## Usability check

With a ready model, valid labels, and reachable storage, ask participants individually to submit sample text and locate the ranked result and confirmed-save status on their first attempt without assistance. Record participant count, successes, failures, and obstacles; calculate `successes / participants` and compare it with 90%. Do not count assisted attempts as first-attempt successes. The exercise remains unverified until it is actually conducted.
