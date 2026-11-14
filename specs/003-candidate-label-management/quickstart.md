# Quickstart: Candidate-Label Management

This guide covers the candidate-label management workflow and its validation.

## Prerequisites and setup

- Python 3.11+ and `uv`; a local/trusted environment and a writable local filesystem.
- Sync the lockfile: `uv sync --locked`.
- No downloaded model, network connection, Hugging Face token, or MinIO credentials are required to use label management.
- The default label catalog is `configs/labels.yaml`; optionally set `LABEL_CONFIG_FILE` to a non-empty local path. Its sibling initialization marker and lock file must remain with it. See [data model](data-model.md) and [contract](contracts/label-management.md). The default local files are ignored; put an override outside Git or configure an appropriate ignore rule. Do not commit local catalog contents, marker, lock, or temporary files.

## Launch and exercise

From the repository root:

```powershell
uv run --locked streamlit run app/streamlit_app.py
```

1. Open Candidate-Label Management. On first use without a catalog and marker, verify the empty state and the warning that previous total loss cannot be detected.
2. Create a uniquely named set with two labels. Verify it appears with both labels; restart the application and verify it remains available.
3. Edit the set and add or remove a label; save and verify unrelated sets are unchanged. If a different saved set is selected, reselect the opened set before saving; the draft remains intact. Attempt a duplicate label with different case or surrounding whitespace and a duplicate set name; verify corrective feedback and retained draft content. Names and labels must contain valid Unicode characters encodable as UTF-8.
   For labels containing line breaks, select **Edit labels individually**. Sets
   that already contain multiline labels open in that mode automatically.
4. Open the same saved set in two sessions. Save a change in one, then attempt an edit or confirmed deletion from the stale session; verify rejection, refresh guidance, and preserved unsaved edits. If the opened set was removed, use **Use draft as a new set** to retain and save its draft, or copy the draft before opening another set.
5. Open the set to remove and check the displayed opened-set name. Request deletion, cancel it and verify no change; repeat with confirmation and verify only that set is removed. Selecting a different set disables removal until the opened set is reselected or the selected set is opened, and clears the previous confirmation. After removing the final set, restart and verify the initialized empty catalog remains valid.
6. With the app stopped and a backup made, test a missing initialized catalog, an invalid catalog, and an unwritable location. Restart and confirm a safe actionable error, no offered sets, blocked changes, and preserved surviving files. Restore from backup using the procedure below.
7. If a write reports an indeterminate outcome, inspect the saved sets and acknowledge the inspection before retrying; the change may already have been applied. A stale draft can retain its content while its selected revision is explicitly refreshed.

## Recovery

Stop all application writers before manual file operations. Back up surviving catalog and marker files. Restore a known-valid catalog and marker from backup, or deliberately provision a valid empty catalog only after accepting that missing data cannot be recovered; then restart and verify validation. An interrupted first initialization may leave a marker without a catalog and requires the same explicit recovery. A valid catalog without its marker triggers a warning before a new marker is created. If both files are absent, the application cannot distinguish total prior loss from first use; restore from an independent backup if available. See [research](research.md) for platform and durability limits.

## Automated checks after implementation

```powershell
uv run --locked pytest tests/unit/test_label_catalog.py tests/unit/test_label_manager.py tests/integration/test_label_concurrency.py tests/smoke/test_label_management.py
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app
```

Tests use temporary directories and no network or services. Run the filesystem and subprocess cases on Windows and POSIX where supported.

## User-observable success checks

- Time a representative administrator creating a set with two labels from the management page; success is 3 minutes or less and the set remains visible after restart.
- Recruit at least 10 representative administrators; give each the same create/find/update task without assistance, record the number who complete it on their first attempt, and divide by the number of participants. The target is at least 90%; report actual count and any limitations, not an unmeasured pass.
- Confirm every invalid input is rejected with corrective feedback, and all tested recovery and concurrent-change scenarios follow the contract.

**Validation status**: The automated checks have been run on Windows. POSIX
filesystem behavior has not been tested in this environment. No representative
administrators participated in a timed or usability exercise, so both the
3-minute and 90% targets remain unverified (participant count: 0).
