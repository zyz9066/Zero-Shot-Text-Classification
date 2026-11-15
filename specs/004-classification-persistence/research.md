# Research: Text Classification and Prediction Persistence

## 1. Existing project boundaries

**Decision**: Reuse the current Streamlit navigation, configuration loaders, `ModelManager` ready status and manifest, and `LabelManager` validated catalog. Add separately testable inference, orchestration, and storage services. Add `torch`, `transformers`, and the MinIO Python client as direct runtime dependencies with compatible locked versions during implementation.

**Rationale**: `pyproject.toml` currently declares Streamlit, Hugging Face Hub, PyYAML, and filelock, but not an inference runtime or MinIO client. The application already resolves MinIO credentials only when `load_minio_settings` is called; the model manager records a 40-character resolved revision, and the label manager validates a complete catalog under a cross-process file lock. Preserve these behaviors and the Python floor.

**Dependency compatibility**: Keep Transformers 5.23+ and PyTorch 2.6+ compatible with the repository's Hugging Face Hub 2.x lock. Resolving Transformers 4.x downgraded Hub to 0.x, whose CLI lacks the existing `hf cache prune` command used by Model Management; this breaks a pre-existing cache-cleanup workflow. The lockfile must preserve the Hub 2.x version while adding inference dependencies.

**Alternatives considered**: Loading from the Hub during classification would violate local readiness and reproducibility. UI-direct service calls for inference and storage would make error paths hard to test. A local prediction database would violate the MinIO system-of-record requirement.

## 2. Full-input inference and scoring

**Decision**: Load the selected local artifact using PyTorch and local-only settings, with remote code disabled. Build the exact premise/hypothesis pair for each candidate and check the full token count including special tokens without truncation. Use the actual trustworthy model and tokenizer constraints, choosing the most restrictive applicable limit; fail safely if a supported limit cannot be established. Ensure the inference path uses those same pairs without truncation. Use exclusive-label scoring (`multi_label=False`) and require a recognized NLI entailment index and exactly one finite score per label.

**Rationale**: The Transformers zero-shot pipeline constructs a pair per label and its source defaults to `ONLY_FIRST` truncation. Its exclusive mode normalizes entailment logits across labels. The model's hypothesis and special tokens contribute to the limit. The current repository's label service already requires two or more labels. Scores change with the candidate set and are not assumed calibrated.

**Alternatives considered**: Silent truncation or chunk aggregation contradicts the clarification. Character-count limits cannot establish model token limits. The pipeline's default truncation cannot itself prove full-input processing.

**Verification caveat**: The public Transformers source cited below is the current upstream branch, not the future locked package version. During implementation inspect and test the selected locked version's actual tokenization, model limit, entailment mapping, and scoring path; if its pipeline cannot guarantee identical full pairs, perform the NLI forward pass on the prevalidated tokenized pairs. Test the exact boundary for both configured model families with lightweight fixtures; do not download full models during ordinary tests.

## 3. Concurrent availability and Streamlit

**Decision**: Add a native, canonical, cross-process per-model use/mutation guard shared by classification and app-managed delete/promotion, with bounded timeouts and fixed ordering before the existing label catalog lock. Hold the model guard throughout a request's success decision. Let valid label edits proceed during inference; at finalization read and validate the whole catalog under its existing lock, require the original stable ID to remain present, and keep that lock through the write outcome. Capture original labels independent of later revisions. Include narrow service APIs rather than reaching into private locks from a page.

**Rationale**: The current model manager's `threading.RLock` is per instance, not a cross-process guard. The label catalog already serializes cooperating reads and mutations, and its stable UUIDs distinguish remove/recreate. Locking the catalog across all inference would unnecessarily block label edits. Retaining a cached loaded model is not proof the managed artifact is still available.

**Alternatives considered**: Check-then-write without a guard allows removal after the check. Holding the label lock through inference blocks the selected edit behavior. Process-local locks alone do not protect other application processes.

**Limits**: Native sidecar locks are cooperative on one local host. Manual edits, deletion of lock files, non-cooperating processes, and multiple hosts cannot be made safe by these locks; stop application processes before manual catalog or model changes. Out-of-band changes and outages can occur and must be detected when observed, but transient uncoordinated removal followed by restoration is not provably detectable. Unsupported deployment models need a separate coordination design, not an implied guarantee.

**Streamlit decision**: Use session-scoped drafts and an in-progress job handle; register a job once before scheduling work, return its existing status on repeat submission, and keep worker results isolated to that session. Workers do not call Streamlit APIs. Use resource caching only for reusable, keyed model/client resources, and protect shared resource use. Do not treat cached values as durable storage or cache user input/results. Use existing compatible APIs; validate any newer API against the project's declared Streamlit minimum before using it.

**Alternatives considered**: Module-global request data can leak between sessions. An unguarded button handler can reissue side effects on reruns. Relying on new Streamlit-only APIs without revising the minimum can break existing installations.

**Active-submission identity decision**: Within a session, define an exact repeat by the tuple of exact submitted text, selected model ID and revision, and selected label-set ID and revision. An exact repeat returns the active request's status without launching another worker or write. A different tuple is not queued or started while that request is active; retain its text and selections, explain that it can be submitted after the active request completes, and revalidate it on that later submission.

**Rationale**: A per-session single-flight check without a payload identity could silently treat changed text or selections as a duplicate. Allowing multiple active requests would require separate UI state and duplicate-write lifecycle handling not required by the feature.

**Accessibility decision**: Use keyboard-operable native Streamlit controls with explicit accessible names. Expose validation, progress, save, and error updates to assistive technology through APIs supported by the declared Streamlit minimum. Validate keyboard operation and the names/status exposure for the full classification flow; make no formal WCAG conformance claim.

**Rationale**: A concrete baseline makes the interaction reviewable without claiming a conformance level that has not been evaluated. Avoid custom controls when native controls satisfy the workflow.

## 4. MinIO bucket, write outcome, and recovery

**Decision**: Use the configured bucket, preserving the existing default `zeroshot_learning_output` exactly. Report invalid names or denied bucket creation, and direct the operator to set a compatible bucket rather than silently changing the default. Write one strict JSON object at `predictions/<request-id>.json`; disable automatic write retries and use explicit conservative outcome classification. Verify the selected client and transport really disable write retries, including proxy/transport configuration; if that cannot be established, do not claim a safe single-attempt guarantee.

**Rationale**: S3 general-purpose bucket rules exclude underscores, so the mandated default is not universally usable. A UUID-derived key identifies a request without exposing text. A confirmed complete write is the only success; a timeout or disconnect cannot establish whether the write is committed or still in flight. Strong read-after-write semantics following an acknowledged write do not prove that a timed-out request cannot complete after a negative lookup.

**Alternatives considered**: Automatically substituting a valid bucket violates the configuration contract. Blind retry or a fresh key after an uncertain write risks duplicate records. Conditional writes may help protect a key but do not by themselves prove a timed-out write cannot later appear; support varies by compatible service and must not be assumed.

**Recovery**: Display the request ID. An authorized operator checks the exact key and content in the configured bucket. If found, do not resubmit. If absent, do not resubmit until both absence and non-completion of the original request are independently established from service/transport evidence; stopping a client, waiting, or one missing-object response is insufficient on its own. If the deployment cannot provide that evidence, leave the outcome unresolved and escalate. Document any product-specific procedure actually verified; do not invent a universal way to establish quiescence. The record may contain sensitive text and should be inspected only by authorized operators.

**Evidence guidance**: Establish current absence with an authorized query to the authoritative endpoint after checking its consistency guarantees. Establish non-completion from deployment-specific client, proxy, and server request telemetry or a documented quiescence procedure showing the original PUT has terminated and cannot be replayed or complete later. If those facts cannot be proven, do not retry.

**Compatibility caveat**: The documented atomicity and strong consistency references below describe AWS S3, not every MinIO-compatible deployment. Integration tests must verify the selected service/client combination; no generalized MinIO late-write guarantee is assumed.

## 5. Tests and operational documentation

**Decision**: Use isolated deterministic fakes for tokenization, inference, clocks, and storage; test model/label races with real cooperating processes and local files. Run an opt-in service-backed write/read integration test in an isolated bucket. Provide Windows-friendly instructions, manual safe recovery, and a usability protocol with participant counts and the 90% threshold.

**Rationale**: This establishes behavior without network/model downloads in unit tests while retaining service-level evidence. Usability and compatibility are observed outcomes, not claims based on design alone.

**Alternatives considered**: A live full-model test in the unit suite is slow, network-dependent, and violates the Constitution. Pure mocks cannot verify actual object-store interaction or cross-process locking.

## Sources

- [Transformers zero-shot pipeline source](https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/pipelines/zero_shot_classification.py) and [pipeline documentation](https://huggingface.co/docs/transformers/main_classes/pipelines#transformers.ZeroShotClassificationPipeline)
- [Amazon S3 bucket naming](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html), [PutObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html), and [consistency model](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html#ConsistencyModel)
- [Streamlit session state](https://docs.streamlit.io/develop/concepts/architecture/session-state) and [resource caching](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource); version-matched references bundled with the installed Streamlit were also consulted.
- Existing project: `app/config/loader.py`, `app/services/model_manager.py`, `app/services/label_manager.py`, `app/streamlit_app.py`, and `pyproject.toml`.
