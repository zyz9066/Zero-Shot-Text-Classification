# Feature 3: Candidate-Label Management Plan

Use this as the `/speckit.plan` input for the clarified feature 003 specification:

```text
/speckit.plan Create the technical implementation plan for Candidate-Label Management in the current specification, `specs/003-candidate-label-management/spec.md`. Honor all three clarifications and the project Constitution.

Plan this feature in the existing Python 3.11+ project. Build on features 001 and 002 without changing their startup, configuration, or model-management behavior. Candidate-label sets are non-secret configuration and are distinct from prediction outputs, for which MinIO remains the system of record.

Architecture and user interaction

- Use the existing Streamlit multipage application and its `st.Page`/`st.navigation` routing. Plan a trusted-environment administration workflow to create, inspect, edit, and remove named label sets. Keep presentation separate from independently testable validation and persistence services.
- Follow Streamlit's rerun and session model. Keep each administrator's unsaved edits session-scoped, including after validation errors, write failures, and stale-edit conflicts. Do not use shared resource caches as durable storage or leak drafts between sessions.
- Validate names and labels at the service boundary as well as in the UI: require a non-blank unique name and at least two non-blank labels; compare names and labels case-insensitively after trimming surrounding whitespace; retain label casing for display. A set's own name may be retained or changed in case, and labels may recur in different sets.
- Provide field- or collection-specific corrective validation messages. Require explicit confirmation for set removal. Make only valid saved sets available to a later classification feature through a clear, separately testable interface; do not build classification or selection for an actual inference request.
- Describe the administration workflow as suitable only for local or otherwise trusted environments. Navigation visibility is not authentication or authorization. Do not request credentials or expose secrets or sensitive local paths in errors or logs.

Persistence, recovery, and concurrent changes

- Research and select a simple, documented persistence format and location consistent with the Constitution's requirement for explicit non-secret label configuration files. Reuse established configuration patterns and existing dependencies where suitable. Describe how configuration is provisioned, edited, persisted across restarts, and made accessible to later features.
- Specify how first use with no configuration is distinguished from a configuration file missing after initialization, including across restart and after the last set is removed. Initialization occurs when a valid configuration is first loaded or successfully saved. Define durable initialization evidence, recovery instructions, and behavior when that evidence itself is missing, invalid, or unwritable; do not silently claim prior data was preserved when it cannot be detected or recovered.
- Fail closed when saved configuration is unreadable or contains any invalid set: offer no sets, block changes, report an actionable error, and preserve the original configuration until repaired. Distinguish this state from a valid empty collection and from a first-use missing file.
- Design safe writes and deletion so a reported failure does not alter previously saved sets. Address interrupted writes, partial initialization, replacement failures, and recovery without silently overwriting the last valid data. Evaluate the guarantees and limitations of the selected approach on Windows as well as supported development environments.
- Define concurrency control for multiple administrator sessions: reject a stale edit or confirmed removal if that set changed or was removed since it was opened, retain unsaved edits, and prompt for refresh. Protect the validation-and-write operation against simultaneous writers, including competing creates or renames, and preserve unrelated sets. Document the supported process/deployment scope and any limits rather than assuming session state alone prevents races.

Configuration and dependencies

- Preserve shell startup and allow label management without downloaded models, Hugging Face credentials, or MinIO credentials.
- Use existing project dependencies and configuration conventions where practical; introduce new dependencies only when justified by the design. Plan any dependency-manifest and lockfile updates reproducibly without making implementation changes during planning.
- Preserve the existing Python minimum and Ruff, type-checking, and testing conventions. Keep credentials, downloaded models, and runtime caches out of version control; do not require example labels or a default set.

Testing and validation

- Plan deterministic tests using temporary directories and lightweight fixtures, without network access, model downloads, or service credentials.
- Cover creation, restart persistence, listing and later-feature access, updates, confirmed and cancelled removal, duplicate names and labels including whitespace/case, validation feedback, and retained drafts.
- Cover first use, initialization and restart, removal of the final set, a missing configuration after initialization, invalid or unreadable configuration, failed writes, interrupted writes, safe recovery, and preservation of unaffected sets.
- Cover stale edits and removals, overlapping writes to different sets, and simultaneous duplicate-name creation or renaming within the supported concurrency scope. Include UI-level checks for session isolation, confirmation, and actionable error messages.
- Map each functional requirement, acceptance scenario, and success criterion to a design element and a validation method. Describe how to assess the 3-minute creation target and 90% first-attempt usability target; do not claim those targets have already been met.
- Provide a quickstart covering configuration and initialization, label-set administration, validation, confirmation, safe recovery, trusted-environment limitations, tests, and expected outcomes.

Generate the plan and normal Spec Kit design artifacts (`research.md`, `data-model.md`, any justified contracts, and `quickstart.md`). Recheck constitutional compliance before and after design. Keep the work within the current specification: do not modify application implementation, generate `tasks.md`, implement inference or MinIO prediction persistence, or add authentication in this planning step.
```
