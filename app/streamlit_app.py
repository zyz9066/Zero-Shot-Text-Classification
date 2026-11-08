import streamlit as st

from app.config.loader import load_app_settings
from app.config.settings import ConfigurationError
from app.utils.logging_config import configure_logging, log_event

logger = configure_logging()

try:
    settings = load_app_settings()
except ConfigurationError as error:
    issue = error.issue
    log_event(
        logger,
        "configuration.validation_failed",
        setting_name=issue.setting_name,
        source_kind=issue.source_kind,
        outcome="invalid",
    )
    st.set_page_config(page_title="Zero-Shot Text Classification")
    st.title("Zero-Shot Text Classification")
    st.error(str(error))
    st.stop()

log_event(logger, "application.startup", outcome="started")
st.set_page_config(page_title="Zero-Shot Text Classification")
st.title("Zero-Shot Text Classification")
st.caption(f"Application version {settings.app_version}")
st.write("Application foundation is ready.")
