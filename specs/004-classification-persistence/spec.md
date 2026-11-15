# Feature Specification: Text Classification and Prediction Persistence

**Feature Branch**: `004-classification-persistence`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: Classify user-provided text using a ready local zero-shot model and a saved candidate-label set, display ranked predictions, and save every successful result in MinIO with reproducibility metadata.

## Clarifications

### Session 2026-11-14

- Q: What should happen when the submitted text is too long for the selected model to process in one request? → A: Reject the request and retain the text for editing.
- Q: If the selected label set is edited while classification is running, what should happen to that request? → A: Continue with the captured labels if the set remains available and valid; fail if it is removed or unavailable.
- Q: How should the model score the candidate labels for each classification request? → A: Score labels as competing alternatives and report one top class.
- Q: How should a user resolve a classification whose storage outcome is uncertain? → A: Have an operator inspect storage using the request identifier before retrying.
- Q: What should happen if the user submits the same classification again while the first submission is still processing? → A: Keep one in-progress request and show its status; do not start another.
- Q: How should the app distinguish a duplicate submission from a new request while a request is still running? → A: Match the exact submitted text and selected model ID/revision and label-set ID/revision. Reuse status for an exact match; block a different submission until the active request finishes and retain the new text and selections for later.
- Q: What minimum accessibility requirements should the classification page meet? → A: Require keyboard-only operation, accessible control names, and accessible validation, progress, save, and error updates; make no formal WCAG conformance claim.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Classify text and save the prediction (Priority: P1)

As a user in a local or otherwise trusted environment, I want to classify text using an available model and a saved candidate-label set, so that I can view a ranked prediction and have the successful result saved for later analysis.

**Why this priority**: A useful classification must both present its prediction and preserve the corresponding record in the designated system of record.

**Independent Test**: With a ready local model, a valid saved label set, and reachable prediction storage, submit non-blank text, inspect the ranked result, and verify the corresponding saved record and its metadata. Exercise invalid inputs, inference failures, and confirmed and uncertain storage outcomes without requiring model downloads in ordinary unit tests.

**Acceptance Scenarios**:

1. **Given** a ready local zero-shot model, a valid saved label set, and non-blank text, **When** the user submits a classification request, **Then** the result shows the top class and its score, every candidate label and score in ranked order, the model used, and the prediction timestamp, **And** the corresponding record is saved in MinIO.
2. **Given** blank text, no ready model, an unavailable selected model, or no valid selected label set, **When** the user attempts classification, **Then** the request is not completed, an actionable message identifies what needs attention, and the entered text remains available.
3. **Given** a successful classification, **When** the displayed result and saved record are reviewed, **Then** the model identifier, available resolved revision, candidate labels, and timestamp correspond to those used for that request, **And** the saved record contains all required prediction and application metadata.
4. **Given** model loading or inference fails, **When** the request finishes, **Then** no successful prediction is claimed, a safe and actionable error is shown, and the entered text remains available.
5. **Given** inference completes but prediction storage confirms that the write failed, **When** the request finishes, **Then** the user is told that the result was not saved and how to recover, **And** the application does not claim successful classification or silently use another store.
6. **Given** inference completes but the storage write outcome cannot be determined, **When** the request finishes, **Then** the user receives the request identifier and instructions for an operator to inspect storage before retrying, **And** the application does not claim success or silently create a duplicate record.
7. **Given** the user is preparing a request, **When** they view the submission controls, **Then** they are told before submission that their input and prediction will be stored. **When** the request is processed, **Then** logs and user-facing errors do not expose raw input, credentials, tokens, or sensitive local paths.
8. **Given** the selected model or labels become unavailable during processing, **When** the request finishes, **Then** no successful result is claimed, the entered text remains available, and the user receives a safe next step. A completed request uses one consistent snapshot of its selected model and labels.
9. **Given** the configured storage bucket is missing, **When** a valid request is saved and creation is permitted, **Then** the bucket is created and the result is saved there. **When** creation is rejected or the configured name is unacceptable to the service, **Then** an actionable storage failure is reported without substituting another bucket.
10. **Given** a malformed or unreadable saved label catalog, **When** the user opens or submits classification, **Then** no sets from that catalog are offered as valid, and the user is directed to repair the catalog.
11. **Given** text exceeds what the selected model can process in one request, **When** the user submits it, **Then** the request is rejected without classifying a truncated portion, the text remains available, and the user is asked to shorten it.
12. **Given** the selected label set is edited while a request runs but remains available and valid, **When** the request succeeds, **Then** its result and saved record use the labels captured for that request rather than the edited labels. If the set is removed or unavailable, the request must not be reported successful.
13. **Given** a valid request with multiple candidate labels, **When** classification runs, **Then** the labels are scored as competing alternatives and the highest-ranked label is reported as the single predicted class.
14. **Given** a classification request is processing, **When** the user repeats the submission in the same session with the exact same text and the same selected model ID/revision and label-set ID/revision, **Then** the current request's status is shown and no second request or prediction record is started. **When** the text or any selected ID/revision differs, **Then** no second request is started, the active request remains unchanged, and the new text and selections remain available with a clear message that the new submission can be made after the active request finishes.
15. **Given** a user navigates the classification workflow using only a keyboard or assistive technology, **When** they identify and operate inputs and review validation, progress, save, or error updates, **Then** controls have accessible names, are keyboard-operable, and status updates are exposed accessibly.

### Edge Cases

- The text contains only whitespace, exceeds the selected model's single-request input limit, or is unsupported; reject the request, retain the entered text, and explain the corrective action. Do not silently truncate text or split it into multiple requests.
- There are no ready models or no saved label sets; identify the missing prerequisite and direct the user to the existing management workflow.
- A selected model is deleted, incomplete, or otherwise unavailable, or a label set is removed or the catalog becomes invalid while a request is being processed; do not claim success for an unavailable dependency or mix versions.
- The label set is edited during processing but remains available and valid; a completed request uses and records the originally captured labels, not a mixture of old and new values.
- A model's resolved revision is unavailable from its recorded provenance; do not invent a revision or silently substitute another model or revision.
- Scores tie, or inference returns missing, duplicated, non-numeric, or non-finite label scores; every successful result must contain exactly one finite numeric score for each selected label in descending order. Tied labels may appear in either order.
- Storage credentials are missing or rejected, the service is unreachable, bucket creation is denied, or the configured bucket name is rejected. In particular, the mandated default name may be rejected by an S3-compatible service; report the problem and allow an operator to configure a suitable name.
- A write times out after it may have reached storage; distinguish the uncertain outcome from confirmed failure and require operator inspection before retry. If the record is found, avoid resubmission; a new submission is safe only when absence is confirmed and the original write can no longer complete; otherwise do not retry yet.
- While a request is processing in one session, an exact repeat uses the same text, model ID/revision, and label-set ID/revision and shows the existing request's status. A different submission is not started until the active request finishes; retain its text and selections and explain when it can be submitted. An intentional submission after completion is a separate request, subject to the uncertain-outcome recovery instructions.
- Sensitive input or prediction data appears in an underlying exception or service response; omit it from logs and user-facing errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a user to enter or paste text, select a ready local zero-shot classification model, select a valid saved candidate-label set, and submit a classification request.
- **FR-002**: The system MUST reject blank or whitespace-only text, unavailable models, and missing, unreadable, or invalid label sets with actionable feedback. A failed request MUST retain the entered text for correction or recovery.
- **FR-003**: Before submission, the system MUST inform the user that the input text and prediction will be stored.
- **FR-004**: Each request MUST use a consistent snapshot of the selected model and candidate labels. If the selected set is edited during processing but remains available and valid, the request MUST continue using its captured labels. The model's recorded identifier and resolved revision, when available, MUST be used for inference and provenance; a different model or revision MUST NOT be substituted silently. Model loading and inference MUST use the PyTorch backend.
- **FR-005**: The system MUST NOT report a successful classification if the required selected model or labels become unavailable during processing. It MUST provide a safe, actionable next step and retain the entered text.
- **FR-006**: The system MUST score selected labels as competing alternatives and report one top class. A successful result MUST display the predicted class and score, all selected candidate labels and their scores in descending order, the model used, and the prediction timestamp. Each selected label MUST have exactly one finite numeric score; the top class and score MUST match the first ranked result. Ties may appear in either order.
- **FR-007**: Scores MUST NOT be described as calibrated probabilities unless that interpretation has been established.
- **FR-008**: Every successful classification MUST be persisted as structured JSON in MinIO, the system of record, using the configured bucket or the default `zeroshot_learning_output`. If the bucket is missing, the system MUST create it when permitted; if creation or use is rejected, it MUST report an actionable failure without silently switching storage or buckets.
- **FR-009**: Each saved result MUST include a request identifier, input text, predicted class and score, candidate labels, ranked labels and scores, model display name and identifier, resolved model revision when available, prediction timestamp, and application version. Its model, labels, scores, and timestamp MUST correspond to the displayed result and the snapshot used for inference.
- **FR-010**: Model-loading and inference failures MUST be reported safely and actionably and MUST NOT be presented as successful predictions.
- **FR-011**: A confirmed storage failure MUST be distinguished from an uncertain storage outcome; neither may be presented as a successfully saved classification. For an uncertain outcome, the user MUST receive the request identifier and instructions for an operator to inspect storage before retrying. The instructions MUST say not to resubmit if the record is found, permit a new submission only if absence is confirmed and the original write can no longer complete, and defer retry otherwise. The application MUST NOT silently create duplicate records.
- **FR-012**: The system MUST treat input text and prediction data as potentially sensitive. Logs and user-facing errors MUST NOT expose raw input, prediction data, credentials, tokens, or sensitive local paths; useful non-sensitive operational diagnostics MUST remain available.
- **FR-013**: The workflow and documentation MUST state that the feature is intended for local or otherwise trusted environments unless separate authentication and authorization are provided. Hiding navigation MUST NOT be described as access control.
- **FR-014**: Documentation MUST describe where predictions are stored, the configured bucket and default, retention behavior, relevant access and security limitations, and safe recovery from storage failures or uncertain outcomes, including how an operator can inspect storage using the request identifier.
- **FR-015**: Core behavior MUST have deterministic automated tests without model downloads during ordinary unit tests. Prediction persistence MUST have integration coverage against MinIO or a compatible service, with a reproducible documented command when not run in CI.
- **FR-016**: Classification MUST consume the existing configuration, model availability and provenance, and valid saved label sets without changing their management workflows. If the label catalog is unreadable or contains invalid sets, no sets from it may be offered until it is repaired.
- **FR-017**: Text exceeding the selected model's single-request input limit MUST be rejected without truncation or splitting, with an instruction to shorten it and the entered text retained.
- **FR-018**: Repeating an identical submission in the same user session while it is processing (same exact text, model ID/revision, and label-set ID/revision) MUST show the existing request's status without starting another request. A submission with different text or any different selected ID/revision MUST NOT start while the request is in progress; the application MUST retain the new text and selections and explain that they can be submitted after the active request finishes. A later intentional submission is a separate request, subject to the uncertain-outcome recovery instructions.
- **FR-019**: The classification workflow MUST be keyboard-operable, controls MUST have accessible names, and validation, progress, save, and error updates MUST be exposed accessibly. The feature makes no formal WCAG conformance claim.

### Key Entities

- **Classification Request**: A uniquely identified submission containing user text and a snapshot of the chosen model and candidate labels.
- **Model Snapshot**: The selected ready local model's display name, recorded identifier, and resolved revision when available.
- **Candidate-Label Snapshot**: The valid saved set of possible classes used for one request.
- **Prediction Result**: The top class and score, complete ranked label scores, model provenance, prediction timestamp, and application version associated with a request.
- **Saved Prediction Record**: The structured representation of a request and its result in the designated prediction store, with a confirmed or uncertain persistence outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all tested successful requests, the user sees the top class and a ranked score for every selected label, and one corresponding stored record contains all required request, prediction, model, timestamp, and application-version metadata.
- **SC-002**: In all tested blank-text, over-limit text, unavailable-model, invalid-label-set, and inference-failure cases, no success is claimed, the user receives an actionable message, and entered text remains available.
- **SC-003**: In all tested model or label changes and availability failures during processing, no successful result mixes snapshots or claims success with an unavailable required dependency.
- **SC-004**: In all tested confirmed and uncertain storage failures, the outcome is identified correctly, no successful save is claimed, and uncertain outcomes are accompanied by an inspection-before-retry instruction.
- **SC-005**: In all tested submissions, the storage notice is visible before submission; review of representative logs and errors finds no raw input, prediction data, credentials, tokens, or sensitive local paths.
- **SC-006**: In a usability check with the prerequisites ready, at least 90% of participating users can submit text and find the ranked result and save status on their first attempt without assistance.
- **SC-007**: In all tested exact repeats in the same session while the original request is processing, its status is shown without starting another request. In all tested submissions with different text or selected IDs/revisions during that time, no new request is started, the active request remains unchanged, and the new text and selections remain available with an instruction to submit after completion.
- **SC-008**: Accessibility review confirms every classification control is operable by keyboard, controls have accessible names, and validation, progress, save, and error updates are exposed to assistive technology; no WCAG conformance claim is made.

## Assumptions

- Features 001, 002, and 003 supply configuration, ready local model provenance, and valid saved label sets. An unreadable or partially invalid label catalog makes all its sets unavailable until repaired.
- When the model source does not expose a resolved revision, the record indicates that it is unavailable rather than inventing one; reproducibility is limited by that missing provenance.
- A confirmed successful storage write is required before classification is presented as successful. An operator with storage access can use the request identifier to investigate an uncertain write; in-app prediction-history browsing remains out of scope.
- Retention is governed by the configured storage policy and operator actions; this feature does not implement retention management.
- The mandated default bucket name may not satisfy every service's naming rules. Operators can supply a valid configured bucket name instead.
- The feature is for local or otherwise trusted environments and does not add authentication or authorization.

## Out of Scope

- Changing model download, deletion, or cache-cleanup workflows.
- Creating or editing candidate-label sets.
- Prediction history browsing, analytics, export, and retention management beyond documenting storage behavior.
- Authentication, authorization, and role management.
- Docker Compose, CI changes, and completing the full project README.
