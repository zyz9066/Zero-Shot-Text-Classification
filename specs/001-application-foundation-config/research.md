# Research: Application Foundation and Configuration

## Decision 1: Typed settings with explicit source merging

**Decision**: Use immutable, type-annotated Python dataclasses for application and service-specific settings. Use PyYAML `safe_load` to parse non-secret YAML into plain mappings, then explicitly merge values in this order: environment variables, YAML, and documented defaults. Map supported environment variable names explicitly rather than importing the entire process environment into configuration.

**Rationale**: The configuration surface is small and its source precedence is an explicit requirement. A straightforward merge is easy to review and test, and avoids making precedence depend on framework defaults. Python dataclasses provide a standard-library representation; explicit validation can report setting names and expected corrections without including values.

**Alternatives considered**:
- Pydantic settings: offers declarative validation and additional settings-source abstractions. It is not needed for this small settings surface; explicit source resolution is simpler to audit against the required precedence.
- Unstructured dictionaries: avoid a settings dependency but weaken type clarity and make service boundaries easier to misuse.

**Validation and error policy**: Validate the YAML document shape and global syntax when loading it. Validate application-level settings at startup and service-specific settings when the service is initialized or used. A missing default YAML file may fall back to environment values and defaults; an explicitly selected but missing file is an actionable configuration error. Never include secret values or absolute local paths in errors.

## Decision 2: Separate shell and service settings

**Decision**: Expose distinct immutable settings groups for application, model/cache, and MinIO configuration. The shell reads only application-level settings. Model and MinIO credentials are resolved and validated at their service boundary, not during shell startup.

**Rationale**: This implements the clarification in the spec and allows the initial page to start without external service credentials. It also keeps later services dependent on explicit configuration interfaces instead of Streamlit UI code reading environment variables directly.

**Alternatives considered**:
- Validate all settings at startup: rejected because it prevents the explicitly required shell startup without model or MinIO credentials.
- Load settings independently in each page/service: rejected because it risks inconsistent precedence, defaults, and error handling.

## Decision 3: YAML safety and secret handling

**Decision**: Load only plain YAML values with `yaml.safe_load`. Keep the committed `configs/app.yaml` limited to non-secret settings. Read MinIO credentials and any Hugging Face token only from environment variables or an approved secret manager. Mark secret fields as non-representable in settings output and exclude values from logs and error messages.

**Rationale**: PyYAML documents that `safe_load` recognizes standard YAML tags and cannot construct arbitrary Python objects. Restricting secrets to external secret sources aligns with the Constitution and avoids accidental disclosure through config dumps.

**Alternatives considered**:
- `yaml.load` with an unrestricted loader: rejected because it can construct arbitrary Python objects.
- Store local credentials in committed YAML: rejected by the Constitution.

## Decision 4: Streamlit configuration lifecycle

**Decision**: Load small settings during the current Streamlit script run and pass the relevant settings explicitly to the shell or service boundary. Do not cache settings or credentials in shared Streamlit caches or session state. The settings loader is deterministic and inexpensive; later model/connection resource caching belongs to the owning features and must follow the Constitution's thread-safety requirements.

**Rationale**: Streamlit reruns the script on user interaction. Its documentation distinguishes copy-returning `st.cache_data` from globally shared mutable `st.cache_resource`; neither is needed for small configuration values, and caching secrets would add avoidable retention and sharing risk.

**Alternatives considered**:
- Store all resolved settings in `st.session_state`: rejected because configuration is not user-specific state and could become stale after configuration changes.
- Use `st.cache_resource` for settings: rejected because shared resources are mutable/shared and settings do not warrant resource caching.

## Decision 5: Dependency reproducibility

**Decision**: Declare Python project metadata, runtime dependencies, development dependencies, and Ruff/type-checker settings in `pyproject.toml`; commit `uv.lock` and use locked synchronization and execution for documented validation commands. Keep Python 3.11+ as the minimum. Add the project-wide runtime libraries through their owning features while maintaining one project lock.

**Rationale**: The Constitution requires isolated, reproducible dependency management. uv documents lock and sync as distinct project operations, and a committed lock records the resolved environment while `pyproject.toml` expresses the supported dependency constraints.

**Alternatives considered**:
- Unpinned ad hoc `pip install` commands: rejected because they do not establish a reproducible environment.
- Separate dependency manifests per service: rejected because they would create conflicting resolution sources for one application.

## Decision 6: Structured, secret-safe logging

**Decision**: Use Python's standard `logging` package with stable event names and a narrow allow-list of structured, non-sensitive fields. Configure a consistent machine-readable output format without logging configuration values, credentials, tokens, raw user input, or absolute paths.

**Rationale**: The application needs useful structured diagnostics but does not need a separate logging framework for the foundation. A small standard-library setup limits dependencies and keeps field disclosure under application control.

**Alternatives considered**:
- Log raw configuration objects for troubleshooting: rejected because objects can contain credentials and local paths.
- Add a logging framework solely for the shell: rejected unless later operational requirements show the standard library is insufficient.

## Configuration keys in scope

- `APP_CONFIG_FILE`: optional path to the YAML file; defaults to `configs/app.yaml`.
- `APP_VERSION`: application version; default `0.1.0`.
- `MODEL_DIR`: model directory; default `./models`.
- `HF_HOME`: Hugging Face cache root; default `./.cache/huggingface`.
- `TRANSFORMERS_CACHE`: Transformers cache path; default `./.cache/huggingface/transformers`.
- `MINIO_ENDPOINT`: required when MinIO is used; no credential or network access required at shell startup.
- `MINIO_SECURE`: explicitly configured when MinIO is used; production deployments use TLS when supported.
- `MINIO_BUCKET`: bucket name; default `zeroshot_learning_output`.
- `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`: secrets supplied through environment or an approved secret manager, required only when MinIO is used.
- `HF_TOKEN`: optional secret supplied externally for future model access; not used by this feature.

No blocking research questions remain. Exact compatible dependency versions are resolved into the lockfile during implementation; this feature has no model-download, GPU, MinIO-availability, or throughput requirement.

## References

- Project Constitution: `.specify/memory/constitution.md`.
- Project requirements: `homework02-MLOps_Project_ ZeroShot_TextClassification_SpecKit.md`.
- PyYAML documentation: https://pyyaml.org/wiki/PyYAMLDocumentation
- Streamlit caching and shared-resource guidance: https://docs.streamlit.io/develop/concepts/architecture/caching
- uv dependency declaration: https://docs.astral.sh/uv/concepts/projects/dependencies/
- uv lock and sync: https://docs.astral.sh/uv/concepts/projects/sync/
