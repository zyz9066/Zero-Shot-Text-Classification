import streamlit as st

from app.config.loader import load_model_settings
from app.config.model_catalog import (
    DEFAULT_MODEL_CATALOG_PATH,
    ModelCatalogError,
    load_model_catalog,
)
from app.config.settings import ConfigurationError
from app.services.huggingface_hub_adapter import HubAdapterError, HuggingFaceHubAdapter
from app.services.model_manager import ModelManager


@st.cache_resource(show_spinner=False)
def _get_model_manager() -> ModelManager:
    settings = load_model_settings()
    catalog = load_model_catalog(DEFAULT_MODEL_CATALOG_PATH)
    adapter = HuggingFaceHubAdapter(
        settings.transformers_cache, token_provider=_resolve_hf_token
    )
    return ModelManager(catalog, settings, adapter)


def _resolve_hf_token() -> str | None:
    return load_model_settings().hf_token


@st.fragment(run_every="1s")
def _render_model_status(manager: ModelManager) -> None:
    statuses = manager.list_status()
    if not statuses:
        st.info("No models are configured.")
        return

    for status in statuses:
        with st.container(border=True):
            st.subheader(status.display_name)
            st.caption(status.model_id)
            st.write(f"Task: {status.task}")
            st.write(f"Availability: {status.availability.title()}")
            if status.resolved_revision:
                st.write(f"Resolved revision: `{status.resolved_revision}`")
            elif status.requested_revision:
                st.write(f"Configured revision: `{status.requested_revision}`")
            if status.progress is not None:
                st.progress(status.progress)
            if status.safe_message:
                st.caption(status.safe_message)


def render_model_management() -> None:
    st.title("Model Management")
    st.warning(
        "Model-management actions are intended only for local or otherwise trusted "
        "environments. Hiding this page is not access control."
    )

    try:
        manager = _get_model_manager()
    except (ConfigurationError, ModelCatalogError) as error:
        st.error(str(error))
        return

    st.caption(f"Model directory: {manager.settings.model_dir}")
    st.caption(f"Hugging Face cache: {manager.settings.transformers_cache}")
    _render_model_status(manager)

    model_ids = [status.model_id for status in manager.list_status()]
    if model_ids:
        labels = {
            status.model_id: status.display_name for status in manager.list_status()
        }
        selected_models = st.multiselect(
            "Models to download",
            model_ids,
            format_func=labels.__getitem__,
        )
        if st.button("Download selected models", disabled=not selected_models):
            operations = [
                manager.request_download(model_id) for model_id in selected_models
            ]
            for operation in operations:
                st.info(operation.safe_message)

        selected_model = st.selectbox(
            "Model to delete",
            model_ids,
            format_func=labels.__getitem__,
        )
        confirm_delete = st.checkbox(
            "I understand this deletes only the selected app-managed model",
            key="confirm_model_delete",
        )
        if st.button("Delete selected model", disabled=not confirm_delete):
            operation = manager.delete_model(selected_model, confirmed=True)
            if operation.state == "succeeded":
                st.success(operation.safe_message)
            else:
                st.error(operation.safe_message)

    st.subheader("Hugging Face cache")
    st.write(
        "Cache cleanup is separate from model deletion. Shared Hub cache artifacts "
        "may support multiple models; app-managed model copies, HF_HOME, and "
        "authentication credentials are not part of this cleanup."
    )
    if st.button("Preview cache cleanup"):
        try:
            st.session_state["model_cache_cleanup_preview"] = (
                manager.preview_cache_cleanup()
            )
        except HubAdapterError as error:
            st.error(str(error))

    preview = st.session_state.get("model_cache_cleanup_preview")
    if preview is not None:
        st.write(f"Configured cache: {preview.cache_path}")
        st.write(
            f"{preview.repository_count} repositories, {preview.revision_count} "
            f"revisions, {preview.incomplete_download_count} incomplete downloads"
        )
        st.write(f"Estimated space reclaimed: {preview.expected_freed_bytes:,} bytes")
        confirm_cleanup = st.checkbox(
            "I understand the cache cleanup scope and impact",
            key="confirm_cache_cleanup",
        )
        if st.button(
            "Clear configured Hugging Face cache", disabled=not confirm_cleanup
        ):
            operation = manager.clear_cache(confirmed=True)
            st.session_state.pop("model_cache_cleanup_preview", None)
            if operation.state == "succeeded":
                st.success(operation.safe_message)
            else:
                st.error(operation.safe_message)


render_model_management()
