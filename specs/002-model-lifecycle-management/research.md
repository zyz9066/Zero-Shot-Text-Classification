# Research: Model Lifecycle Management

## Decision 1: Keep the model catalog separate from application settings

**Decision**: Store non-secret model entries in `configs/models.yaml` and load them through a dedicated catalog parser. Reuse `load_model_settings()` for `MODEL_DIR`, `HF_HOME`, `TRANSFORMERS_CACHE`, and `HF_TOKEN`; do not add a new top-level key to `configs/app.yaml` or duplicate environment-variable resolution.

**Rationale**: Feature 001 deliberately validates a fixed set of application YAML keys. A separate catalog keeps that contract intact and makes adding supported models configuration-driven.

**Alternatives considered**:
- Add `models` to the root application YAML: rejected because it broadens the foundation configuration loader and mixes catalog validation with runtime path/secret resolution.
- Hard-code model identifiers in the service: rejected because the feature requires the catalog to be extensible without workflow redesign.

## Decision 2: Use Hugging Face Hub APIs for repository metadata and snapshots

**Decision**: Use `HfApi.model_info()` to read the model and revision metadata, then use `snapshot_download()` for a complete repository snapshot. If the catalog omits a revision, resolve the upstream default and retain the resolved immutable commit SHA; pass that SHA to the download so the downloaded files all correspond to one revision. Supply the optional configured token only to Hub requests that need it. Never set `trust_remote_code=True`.

**Rationale**: The Hub client supports revision-aware downloads and reports model repository metadata, including a SHA. The full-snapshot API downloads all files needed by the configured model without the project inventing a partial file list.

**Alternatives considered**:
- Download selected files individually: rejected because model repositories vary in required files and separate requests could resolve a moving branch to different commits.
- Clone the model repository with Git/LFS: rejected because it adds external tool prerequisites and does not provide the Hub client's cache/revision handling.

## Decision 3: Separate Hub cache from app-managed model copies

**Decision**: Download the snapshot into the configured `TRANSFORMERS_CACHE`, then materialize a standalone copy under `MODEL_DIR`. Copy into a staging directory beneath `MODEL_DIR`, verify the copy completed, write its non-secret provenance manifest, and promote it to the final model location with a same-filesystem rename. Do not use the final model directory as `snapshot_download(local_dir=...)`.

**Rationale**: With `local_dir`, Hugging Face Hub bypasses the configured shared cache and creates a `.cache/huggingface` metadata folder inside the destination. Using the shared cache and then copying keeps the app-managed model independent: clearing the Hub cache cannot silently break a model marked ready. The trade-off is temporary extra disk use while both copies exist; insufficient storage must leave the model not-ready and preserve any previously complete installation.

**Alternatives considered**:
- Point the final model location at a Hub cache snapshot or symlink: rejected because cache cleanup and Windows symlink support could invalidate or degrade the app-managed model.
- Download directly into the final directory: rejected because a failed download could make partial artifacts look installed.

## Decision 4: Persist only completed installation metadata; keep operation state in-process

**Decision**: Store a small manifest with each installed model containing its identifier, requested revision, resolved immutable revision, and completion timestamp. Derive ready status only when the managed directory and manifest are valid. Keep progress/failure state transient in a thread-safe in-process operation registry keyed by model identifier; concurrent requests for the same model report the existing operation rather than starting another download.

**Rationale**: The feature has no database requirement. The manifest provides durable provenance, while transient operation state can be updated during a running download without introducing another persistence system.

**Alternatives considered**:
- Treat directory existence alone as readiness: rejected because interrupted downloads can leave directories behind.
- Persist transient download state in MinIO or a database: rejected as outside this feature and not needed for a single local application process.

## Decision 5: Make cache cleanup targeted, previewed, and separate from model deletion

**Decision**: Treat `TRANSFORMERS_CACHE` as the Hub repository cache used by this feature. Use `scan_cache_dir()` and its deletion strategy to enumerate revisions and calculate the expected reclaimed space. Show the scope/estimate and require confirmation before executing the strategy. Use the supported `hf cache prune` operation with an explicit cache directory to remove orphaned/incomplete download artifacts that are not represented as complete revisions. Never recursively delete `HF_HOME`, the external token, or `MODEL_DIR` as part of cache cleanup. If the configured cache path is missing or unreadable, report that state safely and do not broaden the deletion target.

**Rationale**: The cache API tracks shared blobs so deleting a revision does not remove data still used by another cached revision. Hugging Face documents pruning for interrupted `.incomplete` downloads. `HF_HOME` can also contain authentication state, so deleting the entire root is unsafe. The app-managed model copy remains usable after cache cleanup.

**Alternatives considered**:
- Recursively remove `HF_HOME`: rejected because it can delete tokens, non-cache files, and unrelated Hugging Face state.
- Delete only cache directories that look old or incomplete using custom globbing: rejected because the Hub cache shares blobs and its metadata must be respected.

## Decision 6: Streamlit page and operation lifecycle

**Decision**: Register the page with `st.Page` and `st.navigation` in the existing application entry point. Keep the page as a UI layer and invoke the model manager through an explicit service boundary. Use `st.cache_resource` only if the shared manager is needed across reruns/sessions, and make its operation registry thread-safe. Do not cache credentials, operation state as serialized data, or model weights in this feature.

**Rationale**: Streamlit's preferred multipage APIs support explicit page routing. Its resource cache shares the same mutable instance across users and sessions, so any shared manager must be safe for concurrent use. Model loading is out of scope.

**Alternatives considered**:
- Put download and deletion logic directly in the page: rejected because it makes filesystem and Hub behavior difficult to test independently.
- Use `st.cache_data` for the manager: rejected because operation state is mutable and resource-like, not serializable result data.

## Decision 7: Cache cleanup interaction and failure handling

**Decision**: Build a cleanup preview from the selected configured cache path before confirmation. The preview reports affected repositories/revisions and estimated space when available. After confirmation, run the cache deletion strategy and refresh model/cache status. A canceled operation performs no deletion. Translate Hub, filesystem, permission, and disk errors to safe operation outcomes; logs contain only allow-listed non-sensitive metadata.

**Rationale**: The specification requires destructive operations to be explicit and actionable. Previewing through the cache library is more trustworthy than estimating or deleting files independently.

## Dependency and validation notes

- Add `huggingface_hub` as a direct runtime dependency and update the committed `uv.lock` with `uv sync --locked` validation.
- Do not add PyTorch or Transformers just for downloading; feature 001's plan defers them until the first feature that actually loads or runs a model.
- Verify the current `.gitignore` continues to exclude `models/`, `.cache/huggingface/`, and local secrets.
- All automated tests use fake Hub responses, temporary cache/model directories, and no network or full model weights.

## References

- [Hugging Face Hub: Download files](https://huggingface.co/docs/huggingface_hub/guides/download)
- [Hugging Face Hub: Manage the cache](https://huggingface.co/docs/huggingface_hub/guides/manage-cache)
- [Hugging Face Hub: Python API reference](https://huggingface.co/docs/huggingface_hub/main/en/package_reference/hf_api)
- [Streamlit: Multipage navigation](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation)
- [Streamlit: Caching and shared resources](https://docs.streamlit.io/develop/concepts/architecture/caching)
- Project Constitution: `.specify/memory/constitution.md`
- Feature 001 settings contract: `specs/001-application-foundation-config/`
