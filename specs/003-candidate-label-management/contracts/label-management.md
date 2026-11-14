# Contract: Candidate-Label Management

## Service boundary

The UI calls a label-management service with an injected catalog path, or a label-specific resolved path (`LABEL_CONFIG_FILE` overrides `configs/labels.yaml`). Access is lazy and does not change application startup, model settings, or MinIO settings. The service has no Streamlit dependency.

Conceptual operations (exact names may follow existing conventions):

- `list_sets()`: return immutable validated set snapshots, each with ID, revision, name, and ordered labels; an ordinary first-use absence returns an empty collection with the notice described below.
- `create(name, labels)`: validate against the latest catalog under the lock and return the new snapshot.
- `update(id, expected_revision, name, labels)`: reject a missing or changed ID/revision; otherwise validate the proposed set against the latest catalog and return its updated snapshot.
- `remove(id, expected_revision, confirmed)`: if not confirmed, do not mutate; if confirmed, reject a missing or changed ID/revision, otherwise remove only that set.

No operation returns partial catalog results if any entry, catalog, or marker is invalid or unreadable. Errors distinguish validation (field or label index/collection), stale snapshot, lock timeout, configuration/recovery, confirmed pre-commit write failure, and indeterminate commit outcome. Messages contain no secrets, raw filesystem paths, or raw underlying exceptions. UI retains valid and unsaved content on errors; a stale response instructs refresh without silently replacing the draft.

The first-use result warns that, when both catalog and initialization evidence are missing, prior total loss is indistinguishable from first use. A valid catalog with absent marker emits a warning and establishes the marker before any sets are returned. The UI presents warnings and safe corrective guidance; it must not claim lost data was restored.

## Catalog format

```yaml
schema_version: 1
sets:
  - id: 8fbdc477-1e0f-40c8-8ff1-f6751b50ec35
    revision: 1
    name: Example topics
    labels:
      - sports
      - technology
```

This example is illustrative, not a required default. A valid empty catalog uses `sets: []`. The loader rejects duplicate mapping keys and requires exactly the stated keys and types, valid unique IDs, positive integer revisions, non-blank trimmed names and labels, at least two labels per set, and case-folded uniqueness. Read-only consumers receive snapshots, not mutable access to persistence.

## Persistence and conflict contract

All cooperating readers and writers use the same canonical sidecar lock path, resolving path aliases and applying platform-appropriate case normalization. A 10-second bounded native `filelock` with `preserve_lock_file=True` and `fallback_to_soft=False` covers marker/catalog inspection and the full read-check-validate-write transaction. Lock timeout or unavailable native locking is an error, not permission to proceed. Manual edits require stopping all application writers; the contract does not cover uncooperative writers or multi-host/network filesystems.

The marker is a UTF-8 YAML mapping containing exactly `schema_version: 1`; it is validated and flushed before exposing a newly provisioned catalog or making a first catalog write. Catalog mutation writes and flushes a same-directory temporary file, then replaces the catalog. Before the commit point, a failed operation leaves saved sets unchanged. If a replacement or post-commit durability result is uncertain, report it as indeterminate, preserve the draft, and instruct the administrator to inspect the current saved catalog before retrying. Do not equate an indeterminate outcome with a confirmed failure or success.

## UI interaction contract

- Show the trusted-environment limitation; page visibility is not access control.
- Present saved sets or an empty/error state; add, remove, and edit labels and set names; show actionable validation feedback near the affected input or collection.
- Preserve the draft during reruns and invalid, failed, or stale operations. Saved state is never derived from another session's draft.
- Require separate explicit confirmation for deletion; cancelling does not call a mutating operation.
- Offer no classification request, model selection, credentials form, or prediction persistence in this feature.
