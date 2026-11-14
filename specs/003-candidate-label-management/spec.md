# Feature Specification: Candidate-Label Management

**Feature Branch**: `003-candidate-label-management`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: Enable administrators in local or trusted environments to create and maintain named candidate-label sets that persist and are available for later classification, without implementing inference.

## Clarifications

### Session 2026-11-14

- Q: What should happen if two administrators change the same saved label set at the same time? → A: Reject a stale edit or removal, retain unsaved edits, and ask the administrator to refresh.
- Q: If saved label configuration contains both valid and invalid sets, which sets should remain available? → A: Make all sets unavailable and require repair before changes.
- Q: How should the application handle a missing label-configuration file? → A: Treat it as empty on first use; report it as an error after initialization.
- Q: How should uncertain writes and lost initialization evidence be handled? → A: Distinguish confirmed failures from indeterminate outcomes; require inspection before retry. Warn when total loss of the catalog and its initialization evidence is indistinguishable from first use. Interrupted first initialization may require recovery before a save succeeds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage reusable candidate-label sets (Priority: P1)

As an administrator in a local or otherwise trusted environment, I want to create and maintain reusable candidate-label sets, so that users can choose an appropriate set when classifying text in a later feature.

**Why this priority**: Classification needs valid, reusable candidate labels; administrators need a reliable way to prepare and maintain them first.

**Independent Test**: Without running inference, create a named set with two distinct labels, save it, restart the application, review and update it, and verify validation and confirmed removal without changing other sets.

**Acceptance Scenarios**:

1. **Given** an administrator enters a unique non-blank set name and at least two distinct non-blank labels, **When** they save the set, **Then** it appears among available sets with its name and labels, **And** it remains available after the application restarts.
2. **Given** an administrator submits a set with a blank name, fewer than two labels, a blank label, or duplicate labels, **When** validation runs, **Then** the submitted changes are not saved or offered for later classification, **And** a corrective message identifies each affected field or the label collection, **And** valid entered content remains available for correction.
3. **Given** two labels differ only in letter case or leading or trailing whitespace, **When** the administrator saves the set, **Then** the labels are identified as duplicates and must be corrected before saving. For valid labels, the entered letter case is preserved for display.
4. **Given** a saved set already has a name, **When** another set is created or renamed to that name with different letter case, **Then** the change is rejected with a corrective message.
5. **Given** a saved set, **When** an administrator changes its name or adds or removes labels and saves valid changes, **Then** the updated set is available for later classification and other saved sets remain unchanged.
6. **Given** an administrator requests removal of a saved set, **When** they cancel or decline confirmation, **Then** the set remains unchanged. **When** they explicitly confirm removal, **Then** only the selected set is removed.
7. **Given** the label configuration is missing on first use or contains no saved sets, **When** the administrator opens label management, **Then** the application explains that no sets are available and how to create one.
8. **Given** saved configuration cannot be read or contains invalid sets, **When** the administrator opens label management, **Then** the application reports the problem and a safe corrective next step, **And** no sets are offered or changes allowed until the configuration is repaired.
9. **Given** a save or removal cannot be committed, **When** the application can confirm failure before replacement, **Then** it reports the failure and corrective action, previously saved sets remain unchanged, and editable input remains available. **When** the replacement outcome or durability is uncertain, **Then** it reports an indeterminate outcome, retains the draft, and asks the administrator to inspect saved state before retrying.
10. **Given** no model has been downloaded and no service credentials have been configured, **When** an administrator manages label sets, **Then** model and prediction-storage availability do not prevent those operations.
11. **Given** an administrator reviews the workflow and its documentation, **When** they manage label sets or recover from a configuration failure, **Then** they can find guidance on configuration, persistence, recovery, and the trusted-environment limitation, **And** the workflow does not request credentials or present hidden navigation as access control.
12. **Given** label-management activity and failures generate logs or messages, **When** those outputs are reviewed, **Then** they contain no credentials, tokens, or sensitive local paths.
13. **Given** an administrator has opened a saved set and another administrator changes or removes it, **When** the first administrator attempts to save an edit or confirm removal based on the earlier version, **Then** the stale operation is rejected, the administrator is asked to refresh, and unsaved edits remain available.
14. **Given** label configuration has been initialized and its saved configuration file is subsequently missing while initialization evidence remains, **When** an administrator opens label management, **Then** the application reports the missing configuration and a safe corrective next step instead of treating it as an empty collection, **And** it blocks changes until recovery.

### Edge Cases

- An attempted edit leaves an existing set with fewer than two labels or gives it a duplicate name; the last saved valid version remains available and unchanged.
- A name or label contains only whitespace, or labels differ only in case or surrounding whitespace.
- An administrator changes the casing of a set's own name without conflicting with another set.
- The label configuration is missing after initialization, malformed, contains invalid or duplicate sets, or cannot be read or written; an error must not be presented as a successful change or silently overwrite existing configuration. A partially invalid collection is unavailable until repaired.
- No model is downloaded and no prediction-storage credentials are configured; neither is needed to manage label sets.
- A deletion is cancelled or fails before replacement; the selected set and other saved sets remain unchanged. An uncertain replacement is reported as indeterminate, not as a confirmed failure.
- If initialization is interrupted after its evidence is recorded, recovery may be required even though no save succeeded. If both catalog and evidence are absent, prior total loss is indistinguishable from first use.
- Two administrators edit the same saved set, or one removes a set another has opened; a stale edit or removal cannot overwrite the more recent change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow an administrator to create named label sets, inspect saved sets and their labels, and add or remove labels and change a set's name.
- **FR-002**: The system MUST require a non-blank set name and at least two non-blank labels before a new or edited set is saved.
- **FR-003**: The system MUST reject duplicate labels within a set, comparing labels without regard to letter case or leading and trailing whitespace, and MUST preserve entered letter case when displaying valid labels.
- **FR-004**: The system MUST reject a set name that duplicates another saved set's name without regard to letter case or leading and trailing whitespace. An existing set MUST be able to retain its own name or change its casing.
- **FR-005**: Validation errors MUST identify each affected field or the label collection and provide a corrective message. Failed validation MUST retain valid entered content and MUST NOT alter the last saved version of any set.
- **FR-006**: Saved sets MUST persist across application restarts and be made available, with their names and labels, for selection by later classification features. Only valid saved sets may be offered.
- **FR-007**: Saving a valid update MUST change only the selected set and MUST leave other saved sets unchanged.
- **FR-008**: Removing a saved set MUST require explicit confirmation. Cancelling MUST leave all sets unchanged; successful removal MUST affect only the selected set.
- **FR-009**: An empty collection MUST be distinguishable from unreadable or invalid saved configuration. The system MUST explain the state and a corrective next step. For unreadable or invalid saved configuration, the system MUST NOT offer any sets, allow changes, or overwrite the configuration until it is repaired.
- **FR-010**: A failed read, save, update, or removal MUST be reported with a safe, actionable message. Confirmed pre-replacement write failures MUST NOT alter previously saved sets. An uncertain replacement or durability outcome MUST be reported as indeterminate rather than success or confirmed failure, with inspection required before retry; editable input MUST remain available.
- **FR-011**: Label management MUST operate without requiring downloaded models, model-service credentials, or prediction-storage credentials.
- **FR-012**: Set names and labels MUST be treated as non-secret configuration; the workflow MUST NOT request credentials or tokens, and logs and error messages MUST NOT expose secrets or sensitive local paths.
- **FR-013**: Label-management actions MUST be described as intended for local or otherwise trusted environments unless a separate feature supplies authentication and authorization. Hiding an administrative view MUST NOT be presented as access control.
- **FR-014**: Label configuration and its persistence and recovery process MUST be documented. The feature MUST support administrator-defined labels without requiring any particular example label or default set.
- **FR-015**: If a saved set has changed or been removed since an administrator opened it, the system MUST reject an edit or removal based on the earlier version, ask the administrator to refresh, and retain unsaved edits for recovery.
- **FR-016**: A missing label-configuration file with no initialization evidence MUST be treated as first use with an empty collection and a warning that total loss cannot be detected. Initialization occurs when a valid configuration is first loaded or successfully saved and persists after the last set is removed. If initialization evidence remains but the catalog is missing, including after interrupted first initialization, the system MUST report a recoverable error and block changes until recovery, including after restart.

### Key Entities

- **Candidate Label**: A non-blank text value representing one possible class, retaining its entered letter case.
- **Candidate-Label Set**: A uniquely named collection of at least two distinct candidate labels, saved for reuse.
- **Label-Set Change**: An attempted creation, update, or removal of a set, with a success, confirmed failure, or indeterminate outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can create and save a set containing a name and two valid labels in 3 minutes or less, and the same set is visible after an application restart.
- **SC-002**: In all tested blank-name, fewer-than-two-label, blank-label, duplicate-label, and duplicate-name cases, the invalid changes are rejected with a corrective message and valid entered content is retained.
- **SC-003**: In all tested valid update and confirmed removal cases, only the targeted set changes; in all tested cancelled or confirmed pre-replacement failed removal cases, no saved set changes. Indeterminate outcomes are identified and require inspection.
- **SC-004**: In all tested unreadable or invalid configuration cases, no set is offered and changes are blocked until repair; in all tested missing-after-initialization, unreadable, invalid, and unwritable configuration cases, the administrator receives an actionable failure message and existing saved sets are not silently overwritten.
- **SC-005**: In a usability check, at least 90% of participating administrators can create, find, and update a valid set on their first attempt without assistance.

## Assumptions

- Features 001 and 002 provide the existing application foundation and model-management workflow; this feature does not redefine either.
- Leading and trailing whitespace is ignored when comparing set names, as it is for labels. Labels in different sets may be identical.
- A failed edit leaves the last saved valid version available; unsaved edits are not themselves offered for later classification.
- Saved sets are non-secret configuration. Administrators are responsible for not entering credentials or other sensitive values as names or labels.
- Selecting a set for an actual classification request belongs to the later classification feature; this feature makes valid saved sets available for that selection.
- The persistence format and implementation will be determined during planning, subject to the project Constitution.

## Out of Scope

- Running zero-shot classification, selecting a model, or displaying prediction results.
- Persisting predictions to MinIO.
- Model downloading, deletion, or cache cleanup.
- Authentication, authorization, or role management.
- Docker Compose, CI changes, and completing the full project README.
