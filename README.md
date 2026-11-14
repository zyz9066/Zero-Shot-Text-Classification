# Zero-Shot-Text-Classification
Spec Kit-guided MLOps platform for zero-shot text classification with Hugging Face Transformers, Streamlit model management, local caching, and MinIO-backed prediction storage.

## Candidate-label management

Run `uv sync --locked` and `uv run --locked streamlit run app/streamlit_app.py`.
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
