# Classification and Prediction Storage Contract

## Selection and request

- The page reads current `ModelManager.list_status()` and `LabelManager.list_sets()` results; only `ready` models and valid saved sets are selectable. Catalog failure offers no sets. Refresh and revalidate selected identities on submit; never trust widget state alone.
- Show the storage notice before submit. Keep the text, selected IDs, request status, and request identifier in session-scoped state, separate from widget keys that can disappear during navigation. Do not put user text in query parameters or shared caches.
- Per session, atomically register a request and its private job/future before starting work. An exact repeat has the same exact text, model ID/revision, and label-set ID/revision; it returns the active request status without launching another worker or write. A different submission is not queued or started while the request is active; retain its text and selections, leave the active request unchanged, and explain it can be submitted after completion, with dependencies revalidated then. Different sessions remain isolated; a later intentional submission gets a new ID. Keep UI updates on Streamlit's script thread; worker code must not access Streamlit session state or put request data in a process-wide registry or cache. Session disconnection does not prove a running write was cancelled.

## Model and labels

- Obtain a cooperative per-model guard before reading ready status and manifest, and hold it through loading, inference, final availability validation, and the storage outcome. The same guard must protect app-managed delete and promotion/replacement across cooperating processes; a bounded busy failure is explicit. Acquire this guard before the model manager's in-process lock in every path that needs both; refactor current deletion ordering as needed to prevent deadlock. Never hold a shared-model inference lock while acquiring another model lock.
- Capture the label set by stable ID from the validated catalog. Permit normal edits while inference runs. Before writing, acquire the existing canonical label catalog lock, validate the entire catalog and confirm the same set ID still exists and is valid. Hold that lock until the storage outcome is determined so a cooperating removal cannot race the success decision. A revision change alone is allowed and the captured labels remain in use. Acquire model guard before catalog lock; no manager path may acquire them in reverse order.
- Coordinate app-managed operations on one host using canonical paths and native cross-process locks. Do not claim protection against external edits, lock-file replacement, network filesystems, or multiple hosts; document that operators must stop application processes before manual changes. Recheck artifacts and catalog on finalization, and fail safely if unavailable. Test actual cooperating manager operations, not only mocked checks.
- Cache heavyweight model resources by local artifact identity, model ID, resolved revision, and relevant runtime configuration; serialize use of a shared model if thread safety is not established. Recheck readiness on every request even on a cache hit. Do not cache request text, results, or label catalog availability.

## Inference

- Load the local artifact with PyTorch and `local_files_only` and without `trust_remote_code`. Resolve the actual tokenizer/model maximum conservatively; fail actionably if no reliable bound can be determined. For each label, tokenize the exact premise and generated hypothesis with special tokens and truncation disabled. Reject if any pair exceeds the bound, before inference. Ensure the actual inference path processes the same full pair, with no silent fallback to truncated input.
- Run single-label/competing-alternative scoring. Validate a one-to-one mapping between the captured candidates and finite numeric output scores, then sort descending and derive the top result. Reject unsupported models or malformed output safely. Keep timestamp and all displayed values identical to the record.

## Storage and outcomes

- Resolve MinIO settings only for this feature. Use one UUID-derived object key per request and a single structured JSON object; do not reuse an ID for a different payload. Disable automatic write retries that could obscure outcome. Concurrent bucket creation is reconciled only after verifying the configured bucket is usable; creation denial, invalid name, and configuration errors remain explicit.
- `saved`: receive conclusive confirmation of the correct write and display the request ID with the result for authorized inspection. `failed`: only when evidence proves no write was accepted, including validation failure before a write or an authoritative rejection that rules out acceptance. `indeterminate`: transport timeout, disconnect, interrupted process, or any error for which acceptance or a late completion cannot be excluded. Do not infer confirmed failure solely from a timeout, a missing response, or a single missing-object lookup.
- For an indeterminate outcome, give the request ID and a reference to operator guidance. The operator checks the exact key in the configured bucket using authorized tools. If present and the record matches, do not resubmit. If absent, resubmit only after the operator has independently established that the original write can no longer complete; if neither fact can be established, leave unresolved and escalate. A restart, wait, or missing-object response alone is not proof of quiescence. The application does not promise automatic reconciliation or automatic retry.
- Errors and logs use fixed safe messages and allowlisted metadata; do not interpolate third-party exceptions or payloads. Treat record contents as sensitive and protect storage access through operator configuration.

## Accessibility

- Keep every classification control operable with a keyboard and give controls accessible names. Expose validation, progress, save, and error updates accessibly using APIs supported by the declared Streamlit minimum; make no formal WCAG conformance claim.

## Compatibility and failure boundaries

The existing model manager's `threading.RLock` is per instance and does not coordinate separate processes; the label manager already uses a canonical native sidecar file lock. Implement and test the required narrow coordination explicitly, including lock timeout and release on all failures. Test that existing confirmed deletion, stale label edits/removals, unrelated sets, downloads, and shell startup retain their intended behavior. Network/remote administrators and uncooperative file mutations are outside the supported concurrency model and require operational coordination.
