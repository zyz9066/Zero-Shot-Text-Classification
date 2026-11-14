# Research: Candidate-Label Management

## 1. Catalog and validation

**Decision**: Use a UTF-8 YAML catalog by default at `configs/labels.yaml`, with versioned root metadata and stable set IDs/revisions. Use a safe PyYAML loader that explicitly rejects duplicate mapping keys and validate the entire document before exposing any entries. A dedicated label configuration path override may be supplied by environment or explicit injection; resolve it only when the feature is used. Ignore the default mutable catalog, marker, lock, and temporary files; document that override paths must be outside Git or separately ignored. Document an example rather than shipping a mandatory default set.

**Rationale**: The repository already uses YAML, PyYAML, typed settings, service-specific loading, and validation; this does not add a dependency for parsing or alter shell startup. A validated whole-catalog snapshot enforces fail-closed behavior and gives future inference a simple read-only interface.

**Alternatives considered**: A database would add operational complexity and would not satisfy the Constitution's explicit label-configuration-file requirement by itself. A checked-in mutable catalog risks committing local edits and does not by itself distinguish first use from later loss.

Normalize names and labels with Unicode `strip()` for surrounding whitespace and `casefold()` for comparisons. Store trimmed display values retaining entered letter case. Reject non-string values, blanks, duplicate normalized names or labels, malformed IDs/revisions, unknown schema versions, and invalid collections. Names remain unique across sets; labels need only be unique within one set.

## 2. First use, initialization, and missing evidence

**Decision**: Alongside the catalog keep a separate durable, versioned initialization marker and a stable separate lock file. Treat both catalog and marker absent as first use, with an explicit notice that absence alone cannot prove no prior data existed. When a valid existing catalog is loaded without a marker, validate it under the lock, create and flush the marker before returning the catalog, and report marker failures rather than silently proceeding. Before the first save with no catalog, create and flush the marker under the lock before committing the catalog. A valid marker plus missing catalog, invalid/unreadable marker, or unreadable/invalid catalog is a recovery error: block all reads of sets and mutations, preserve surviving files, and give safe recovery instructions. Preserve the marker even after the last set is removed.

**Rationale**: Evidence outside the catalog survives normal catalog deletion and restarts. Marker-first ordering deliberately prefers a recoverable error over misclassifying an interrupted initialization as a clean first use. A provisioned valid catalog becomes initialized on its first successful load.

**Alternatives considered**: In-memory state fails across restarts. Embedding the marker only in the catalog cannot detect loss of the catalog. Treating every missing catalog as empty can silently conceal data loss. A marker cannot solve simultaneous removal of both evidence and catalog: after that event first use and prior loss are observationally identical. An administrator must use a separate backup to recover data; the application must not claim the absence proves no prior sets or that deleted data can be recovered.

**Recovery**: Stop all writers; back up surviving catalog/marker; inspect and restore a valid catalog and marker from a trusted backup, or deliberately provision a valid empty catalog only after acknowledging loss; then restart and validate. Do not have the UI automatically overwrite invalid evidence. If an initial marker was created but the first catalog write failed or was interrupted, recovery follows the same explicit procedure. If a valid catalog survives but its marker is lost, warn that initialization evidence was missing before recreating it; the catalog is not proof that no earlier data was lost.

## 3. Concurrency and stale changes

**Decision**: Add `filelock>=4.2.10` as a direct runtime dependency. It is already present transitively in the lockfile (the installed version is 4.2.10 and requires Python >=3.11); update the manifest/lock reproducibly during implementation. Use one canonical sidecar lock path, a bounded acquisition timeout, and native OS locking on supported Windows/POSIX local filesystems. Instantiate with `preserve_lock_file=True` and `fallback_to_soft=False`; the installed version exposes both options. Hold the lock for reads that inspect marker and catalog together and for every complete validate/read-modify-write transaction. Never remove the lock file while processes may be using it. Expose a safe timeout or unsupported-backend error; do not silently fall back to an untested soft-lock scheme.

Assign each set a stable opaque ID and change revision. Edits and deletions supply the revision captured when the set was opened. Under the lock, compare the current ID/revision; reject missing or changed sets as stale before modification. Revalidate name uniqueness against the latest whole catalog before create/rename. A successful mutation preserves unrelated sets and advances the modified set's revision, so delete/recreate with the same name cannot pass an old check.

**Rationale**: The lock serializes cooperating processes; revision comparison also catches stale drafts that outlive a lock. A separate lock file remains stable across catalog replacement. UI/session state alone cannot protect shared persisted data.

**Alternatives considered**: Hand-rolled `fcntl`/`msvcrt` branches require separate locking semantics and timeout handling. A process-local mutex does not protect another process. A last-writer-wins policy conflicts with the clarification.

**Limits**: Locks are cooperative: direct editor changes must be done with application writers stopped. Use the same canonical configured path and one local host; network filesystems, uncooperative writers, multiple hosts, and removal/replacement of the lock while in use are outside the guarantee. The implementation must check that the native backend is available; fail closed if not.

## 4. Write safety and durability

**Decision**: Under the lock, validate and serialize the complete new catalog to a uniquely named temporary file in the same directory; flush and `fsync` the file, then use `os.replace` as the commit point. Before replacement, failures remove only the operation's own temporary file and leave the prior catalog unchanged. After the commit point, do not report an ordinary failed write as if the old catalog were guaranteed intact: if a subsequent durability check fails or the outcome cannot be established, report an explicit indeterminate outcome and require refresh/inspection before retry. Use a directory sync where supported, and document platform limitations.

**Rationale**: Same-directory replacement avoids cross-filesystem moves. The lock makes cooperating reads/writes consistent even where Python does not promise atomic replacement on a platform; the temporary file prevents a failed pre-commit write from truncating the live catalog.

**Alternatives considered**: Writing in place risks a truncated catalog. Deleting the catalog before replacement breaks the old-or-new guarantee. Automatic rollback after a possibly committed replacement can overwrite another valid state or fail itself.

**Limits**: Python documents POSIX atomicity for a successful replacement, not a universal Windows or crash-durability guarantee. Windows sharing/permission failures and POSIX `EIO` can leave uncertain outcomes; surface them and inspect rather than claim a guaranteed rollback. Power loss, filesystem behavior, metadata sync, and simultaneous loss of catalog and marker are not fully controllable. Run Windows and POSIX fault-injection tests; do not claim those tests prove hardware-level durability. Clean up only the operation's own temporary files.

## 5. Streamlit interaction and tests

**Decision**: Register a new page in the existing navigation and preserve the existing `pages/` organization rather than moving existing pages. Use native widgets, uniquely prefixed keys, and separate per-session draft data from widget keys so reruns and conditional rendering do not discard drafts. Keep revision snapshots with each draft; refresh the saved view on conflict without discarding edits. Use explicit confirmation for deletion, server-side validation in the service, and user-safe error mapping.

**Rationale**: Installed Streamlit guidance says widget state may be removed when not rendered and session state is per browser session, not durable storage. The existing project already uses `st.navigation` and `AppTest`.

**Alternatives considered**: Module-global or shared cached drafts risk cross-session leakage; UI-only validation does not protect the persistence boundary.

**Sources**:
- Installed Streamlit 1.67.0 bundled `session-state.md`, `multipage-apps.md`, and `testing.md`; the project declares Streamlit >=1.39, so implementation must avoid unverified newer-only APIs or explicitly revise the minimum.
- [Python `os.replace`](https://docs.python.org/3/library/os.html#os.replace)
- [POSIX `rename`](https://pubs.opengroup.org/onlinepubs/9799919799/functions/rename.html)
- [Linux `fsync`](https://man7.org/linux/man-pages/man2/fsync.2.html)
- [filelock concepts](https://py-filelock.readthedocs.io/en/latest/concepts.html)
- [Python Windows locking](https://docs.python.org/3/library/msvcrt.html#msvcrt.locking)
- [Windows MoveFileEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)
