import streamlit as st

from app.config.loader import load_model_settings
from app.config.model_catalog import (
    DEFAULT_MODEL_CATALOG_PATH,
    load_model_catalog,
)
from app.services.huggingface_hub_adapter import HuggingFaceHubAdapter
from app.services.model_manager import ModelManager


@st.cache_resource(show_spinner=False)
def get_model_manager() -> ModelManager:
    settings = load_model_settings()
    catalog = load_model_catalog(DEFAULT_MODEL_CATALOG_PATH)
    adapter = HuggingFaceHubAdapter(
        settings.transformers_cache, token_provider=_resolve_hf_token
    )
    return ModelManager(catalog, settings, adapter)


def _resolve_hf_token() -> str | None:
    return load_model_settings().hf_token
