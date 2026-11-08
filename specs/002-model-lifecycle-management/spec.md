# Feature Specification: Model Lifecycle Management

**Feature Branch**: `002-model-lifecycle-management`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: Provide a trusted-environment administrator workflow for inspecting configured zero-shot classification models, downloading and tracking local model availability, deleting selected app-managed models, and clearing the Hugging Face cache. Reuse the centralized model and cache settings established by feature 001. Prepare models for later inference without implementing inference, candidate-label management, or prediction persistence.

## Clarifications

### Session 2026-11-08

- Q: If a model entry has no configured revision, what revision policy should govern its download? → A: Download the current upstream default and record the exact resolved immutable revision used.
- Q: If an administrator requests the same model while its download is already running, what should the application do? → A: Treat it as the existing in-progress operation and show its status without starting another download.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage configured model availability (Priority: P1)

As an administrator in a local or otherwise trusted environment, I want to inspect and manage configured zero-shot classification models, so that models are ready for later classification work.

**Why this priority**: Later inference depends on known, complete local model artifacts and reliable model provenance.

**Independent Test**: With a catalog containing the two required public models, verify that an administrator can inspect model details and availability, download a missing model using a test double, refresh its status, reuse an already complete model, and safely exercise deletion and cache-cleanup confirmations.

**Acceptance Scenarios**:

1. **Given** a valid catalog containing configured models, **When** the administrator opens or refreshes model management, **Then** each model's display name, identifier, task, local availability, and configured or resolved revision when available are shown.
2. **Given** a configured model is missing locally, **When** the administrator requests its download, **Then** progress and a clear completion or failure result are provided, **And** the model is reported ready only after the download completes, **And** its identifier and resolved immutable revision are available for later inference when provided by the source, including when no revision was configured in the catalog.
3. **Given** a configured model is already completely available locally, **When** the administrator requests it, **Then** the existing model is reused and an unnecessary second download is avoided.
4. **Given** a download is interrupted or fails, **When** the administrator refreshes status or retries, **Then** incomplete files are not reported as ready, **And** the failure is actionable, **And** retrying can complete without corrupting an existing complete model.
5. **Given** a configured model is completely available locally, **When** the administrator selects deletion and explicitly confirms, **Then** only that app-managed model is deleted, **And** refreshed status reports it as unavailable, **And** unrelated files remain untouched.
6. **Given** Hugging Face cache contents exist, **When** the administrator requests cache cleanup, **Then** its scope and impact are explained and explicit confirmation is required, **And** confirmed cleanup affects the configured Hugging Face cache without silently deleting app-managed model files.
7. **Given** the administrator begins model deletion or cache cleanup, **When** the administrator cancels or declines confirmation, **Then** no files are removed.
8. **Given** a requested operation encounters an unavailable network, unresolved revision, invalid configuration, permission failure, insufficient disk space, or unavailable cache, **When** the operation fails, **Then** the administrator receives a safe, actionable message and the model is not falsely reported ready.
9. **Given** a configured model is already downloading, **When** the administrator requests that same model again, **Then** the current operation and its status are shown, **And** no duplicate download is started.

### Edge Cases

- The model catalog is empty, malformed, contains duplicate identifiers, or references a model with an unsupported task.
- A configured model revision cannot be resolved or is no longer available.
- A local model directory exists but contains an incomplete or invalid download.
- A repeated or overlapping request attempts to download the same model more than once.
- The configured model directory or Hugging Face cache directory is missing, unreadable, or not writable.
- The Hugging Face cache contains artifacts shared by multiple models; cleanup must communicate that impact before confirmation.
- A public model is requested without a token, or a restricted model requires credentials that are not configured.
- A deletion or cleanup request is cancelled before confirmation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST present a catalog of configured zero-shot classification models with each model's display name, identifier, task, local availability, and configured or resolved revision when available.
- **FR-002**: The initial catalog MUST include `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` and `facebook/bart-large-mnli`.
- **FR-003**: The catalog MUST be extendable through non-secret configuration without requiring a redesign of the model-management workflow.
- **FR-004**: An administrator MUST be able to inspect the effective model and Hugging Face cache locations and refresh local availability.
- **FR-005**: An administrator MUST be able to request downloading one or more configured models and receive meaningful progress, completion, or failure feedback.
- **FR-006**: A complete local model MUST be reused rather than downloaded again unnecessarily. Missing, downloading, failed, and incomplete states MUST be distinguishable, and incomplete artifacts MUST NOT be presented as ready. A repeated request for a model that is already downloading MUST report the existing operation and MUST NOT start a duplicate download.
- **FR-007**: Failed or interrupted downloads MUST leave the model in a recoverable state; retries MUST NOT corrupt an existing complete model or make partial files appear ready.
- **FR-008**: An administrator MUST be able to delete a selected app-managed local model only after explicit confirmation. Deletion MUST be confined to the configured model directory and MUST NOT remove unrelated files.
- **FR-009**: Clearing the Hugging Face cache MUST be a separate, explicitly confirmed operation from deleting an app-managed model. Its scope and impact MUST be explained before confirmation, and it MUST NOT silently delete app-managed model files.
- **FR-010**: The identifier and revision actually used for each completed model download MUST be available to later inference features. If the catalog does not specify a revision, the system MUST resolve and record the immutable revision used whenever the model source exposes it.
- **FR-011**: Public models MUST be inspectable and downloadable without a Hugging Face token. Restricted-model credentials, when needed, MUST use the project's established external secret configuration.
- **FR-012**: Failures caused by network, revision, configuration, permission, storage-capacity, or cache-availability problems MUST produce actionable messages without exposing credentials, tokens, or sensitive local paths.
- **FR-013**: Downloaded model artifacts, runtime cache contents, credentials, and tokens MUST NOT be committed to the repository.
- **FR-014**: Model-management actions MUST be described as suitable only for local or otherwise trusted environments unless a separate feature implements real authentication and authorization. Hiding an administrative view MUST NOT be represented as access control.

### Key Entities *(include if feature involves data)*

- **Configured Model**: A catalog entry describing a model's display name, identifier, task, and optional requested revision.
- **Local Model Artifact**: A locally stored model associated with a configured model and its resolved revision, with an observable availability state.
- **Model Operation**: A download, deletion, or cache-cleanup request with an observable outcome and safe diagnostic information.
- **Hugging Face Cache**: Cached model artifacts managed separately from the app-managed local model directory.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every configured model is represented in the catalog with a stable identifier and an accurate local availability state.
- **SC-002**: Every successfully completed download is shown as ready and exposes the resolved immutable revision used when the source provides it, including when the catalog omits a revision; no failed or incomplete download is shown as ready.
- **SC-003**: Repeating a request for a complete local model or a model that is already downloading does not start another download for the same model and revision.
- **SC-004**: In all tested download failure and retry cases, an incomplete model is never reported as available and a retry can reach a complete state without damaging a previously complete artifact.
- **SC-005**: In all tested deletion and cache-cleanup cases, only the explicitly confirmed target is changed; cancelling confirmation leaves managed files unchanged.
- **SC-006**: All tested configuration, network, revision, permission, and storage failures produce an actionable message without exposing credentials, tokens, or sensitive local paths.

## Assumptions

- Feature 001 is implemented and provides centralized model-directory, Hugging Face cache, and optional token settings; this feature consumes those settings rather than defining replacements.
- The two named initial models are public zero-shot classification models; credentials are optional for them.
- If a catalog entry omits a revision, the current upstream default may be downloaded, and its resolved immutable revision is retained when the source exposes it.
- Model management is limited to local development or a trusted environment because authentication and authorization are not part of this feature.
- Model identifiers and revisions are retained as provenance for a later inference feature; this feature does not load models for inference.
- Tests use test doubles or lightweight fixtures and do not download full models or require network access.

## Out of Scope

- Creating, editing, saving, or selecting candidate-label sets.
- Running zero-shot inference or presenting classification results.
- Persisting predictions to MinIO.
- Adding authentication, authorization, or role management.
- Deployment, Docker Compose, CI changes, and completing the full project README.
