# Data Model: Text Classification and Prediction Persistence

## Classification request

An immutable request contains a UUID request identifier, the exact submitted text, a model snapshot, and a label-set snapshot. Reject text that is blank after whitespace checking, is not valid for the model, or would exceed the model's actual pair-input limit for any candidate. Preserve the exact input for display/recovery and the required stored record; do not silently normalize, truncate, or split it.

## Model snapshot

Contains display name, model identifier, selected local artifact identity, and recorded resolved revision. Use the existing ready-state and manifest interface, and revalidate the identity before success. The current model manager accepts a ready manifest only when its resolved revision is a 40-character hash; if a future valid provider cannot expose one, represent the revision as `null`, never fabricate it. Load only from the app-managed local artifact, with PyTorch and local-only/trusted-code-disabled settings.

## Candidate-label snapshot

Contains the stable saved-set ID, set revision and name captured on submission, and an ordered immutable tuple of at least two valid unique labels. Validate through the existing whole-catalog reader. Subsequent valid edits do not change the snapshot. A removed set, invalid catalog, or unreadable catalog invalidates completion. Revision differences alone do not invalidate a still-present valid set.

## Prediction result

Contains the snapshot model identity, candidate labels, one finite numeric score per label ordered descending, top class and its identical score, UTC prediction timestamp, and application version. Ties may have any consistent presentation order. Reject missing, extra, repeated, nonnumeric, or non-finite scores rather than displaying or persisting malformed predictions. Scores represent competing alternatives, not established calibrated probabilities.

## Saved prediction record

One UTF-8 JSON object at `predictions/<request-id>.json` in the configured bucket:

| Field | Type and invariant |
|---|---|
| `request_id` | UUID string, equal to key identifier |
| `input_text` | Exact submitted text; sensitive |
| `predicted_class` | Top label, equal to first ranked label |
| `predicted_score` | Finite number, equal to first ranked score |
| `candidate_labels` | Array of captured label strings |
| `ranked_results` | Array of `{label, score}` objects, exactly one per candidate in descending score order |
| `model_name`, `model_identifier` | Captured display name and identifier |
| `model_revision` | Resolved revision string or JSON `null` when genuinely unavailable |
| `timestamp` | UTC ISO 8601 prediction time, identical to the displayed value |
| `application_version` | Effective configured application version |

Serialize strictly valid JSON (reject NaN and infinity); do not store credentials, local paths, or exception messages. The key contains no text, label, model, or secret. Request ID and bucket/key allow an authorized operator to inspect an uncertain outcome. Storage lifecycle policies control retention; no local substitute or application history is introduced.

## Request and write states

`idle` → `validating` → `running` → `saving` → `saved` only on confirmed write. Validation, dependency, inference, or confirmed pre-commit storage errors lead to `failed`; a possibly accepted write with no conclusive response leads to `indeterminate`. Both retain the user's input. A completed request may later be intentionally resubmitted as a new request.

While a request is active in one session, an exact repeat is the same exact text, model ID/revision, and label-set ID/revision; it refers to the existing request and returns its status. A different submission is not queued or started until the active request finishes. Retain the different text and selections in session state and explain that they may be submitted afterward; revalidate dependencies when that new request is submitted. The matching tuple is transient session state, not a persisted field.

`indeterminate` is not a confirmed failure. The UI displays the request ID and operator instructions; a missing object observed once is not proof that an in-flight write cannot appear later. A new request is safe only when the operator confirms both absence and that the original write is no longer able to complete. Otherwise defer retry. Session loss or process restart does not establish that fact.
