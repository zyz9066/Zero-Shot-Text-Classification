# Data Model: Candidate-Label Management

## Candidate label

- **Value**: A non-empty UTF-8 string after trimming leading/trailing whitespace. Store the trimmed spelling and preserve letter case.
- **Comparison key**: The trimmed value's Unicode `casefold()` result. Keys must be unique within a set, but may recur across different sets.
- **Order**: Preserve the administrator's saved label order when returning and displaying a set.

## Candidate-label set

- **ID**: Opaque UUID generated at creation, unique within the catalog and stable through rename or edits. Recreating a removed name creates a new ID.
- **Revision**: Positive integer. Start at 1 and increment on every successful edit, including rename; old revisions cannot authorize edit or removal.
- **Name**: Non-empty trimmed string, preserving display case. Its case-folded comparison key is unique across the catalog; a set may retain its own key.
- **Labels**: Ordered collection of at least two valid, distinct candidate labels.

## Catalog

- **Schema version**: Integer `1`; unknown or missing versions are invalid.
- **Sets**: List of complete candidate-label sets. An empty list is valid. Every ID and normalized name must be unique; every entry must satisfy all set and label rules. Reject malformed or unknown fields; never return a partially valid catalog.
- **Format**: UTF-8 YAML mapping, parsed with a safe loader that rejects duplicate mapping keys. Catalog structure and administrative examples are described in the [contract](contracts/label-management.md).
- **Location**: Default `configs/labels.yaml`, resolved from the application working directory, with optional `LABEL_CONFIG_FILE` environment override or explicit service path for tests. Empty overrides are errors; path resolution and error mapping occur only when label management is used.

## Initialization marker

- **Location**: Sidecar beside the selected catalog, e.g. `configs/labels.yaml.initialized`; lock and temporary files are also colocated. Marker is persistent, non-secret state, not the catalog itself.
- **Contents**: UTF-8 YAML mapping with exactly `schema_version: 1`; reject missing/unknown keys and non-integer or unsupported versions. It contains no labels or credentials.
- **Meaning**: Marker presence proves initialization was attempted or a valid catalog was successfully loaded. It is created and durably flushed before the first catalog write or before exposing a valid pre-provisioned catalog.
- **Lifecycle**: Never remove on normal last-set deletion. A missing catalog with a valid marker, invalid/unreadable marker, or inability to create/write marker is a recovery error. A valid catalog with no marker triggers warning and marker creation before exposing sets. If both catalog and marker are missing, first use and total evidence loss are indistinguishable; warn that missing prior data cannot be detected or reconstructed.

## Session draft

- **Contents**: Unsaved name, ordered labels, selected set ID, and revision captured when opened; validation and operation feedback.
- **Ownership**: One browser session; not stored in a global cache and not persisted as saved configuration.
- **Lifecycle**: Preserve through reruns, validation failures, stale conflicts, and write failures. Successful save may replace the draft with the newly saved snapshot; refresh after a conflict does not discard unsaved text. Session termination or server restart ends the draft.

## State and transitions

| State | Condition | Permitted behavior |
|---|---|---|
| First use | Catalog and marker absent | Show empty state with evidence-loss caveat; create allowed after marker creation |
| Valid | Catalog and marker valid, including zero sets | List, create, update, and confirmed delete under lock |
| Provisioned | Valid catalog, marker absent | Warn; establish marker under lock before exposing sets; failure blocks use |
| Recovery required | Marker invalid/unreadable; initialized catalog missing; or catalog unreadable/invalid | Report safe corrective guidance; no sets exposed and no mutation |
| Stale draft | Saved ID absent or revision differs from captured revision | Reject update/delete, retain draft, ask for refresh |
| Indeterminate write | Outcome or durability after attempted replacement cannot be established | No success or ordinary failure claim; refresh/inspect before retry |

A new/updated set is saved only after full validation and successful replacement. An update increments its revision; confirmed deletion removes exactly its ID. Reads and mutations inspect marker and catalog together under the same cooperative lock.
