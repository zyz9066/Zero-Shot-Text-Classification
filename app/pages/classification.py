from __future__ import annotations

import streamlit as st

from app.config.loader import load_app_settings
from app.config.model_catalog import ModelCatalogError
from app.config.settings import ConfigurationError
from app.services.classification import (
    ClassificationError,
    ClassificationService,
    SessionSubmissionCoordinator,
    SubmissionStatus,
)
from app.services.label_manager import LabelManager, LabelManagerError
from app.services.model_manager import ModelManagerError
from app.services.model_provider import get_model_manager
from app.services.prediction_store import PredictionStore
from app.utils.logging_config import configure_logging, log_event

_COORDINATOR_KEY = "classification_submission_coordinator"
_LOGGER = configure_logging("classification_page")


def _show_outcome(status: SubmissionStatus) -> None:
    outcome = status.outcome
    if outcome is None:
        return
    request_id = outcome.request.request_id
    if outcome.status == "saved" and outcome.result is not None:
        result = outcome.result
        st.success(f"{outcome.message} Request ID: {request_id}")
        st.subheader(f"Top class: {result.predicted_class}")
        st.write(f"Score: {result.predicted_score:.6f} (not a calibrated probability)")
        st.write(f"Model: {result.model_name} (`{result.model_identifier}`)")
        st.write(f"Resolved revision: {result.model_revision or 'unavailable'}")
        st.write(f"Prediction timestamp: {result.timestamp}")
        st.dataframe(
            [
                {"Label": item.label, "Score": item.score}
                for item in result.ranked_results
            ],
            hide_index=True,
            use_container_width=True,
        )
    elif outcome.status == "indeterminate":
        st.error(
            f"{outcome.message} Request ID: {request_id}. An authorized operator "
            "must inspect `predictions/{request_id}.json` in the configured bucket. "
            "Do not resubmit if it exists. Retry only after both absence and that "
            "the original write cannot complete are established; otherwise defer "
            "and escalate."
        )
    else:
        st.error(outcome.message)


def render_classification() -> None:
    st.title("Text Classification")
    st.warning(
        "Use this feature only in a local or otherwise trusted environment unless "
        "separate authentication and authorization are provided. Hiding navigation "
        "is not access control."
    )
    st.info(
        "Before you submit: your exact input text and prediction will be stored in "
        "the configured MinIO bucket."
    )

    if _COORDINATOR_KEY not in st.session_state:
        st.session_state[_COORDINATOR_KEY] = SessionSubmissionCoordinator()
    coordinator = st.session_state[_COORDINATOR_KEY]
    status = coordinator.poll()
    if status.state == "in_progress" and status.request_id:
        st.info(f"{status.message} Request ID: {status.request_id}")
    elif status.outcome is not None:
        _show_outcome(status)

    try:
        model_manager = get_model_manager()
        label_manager = LabelManager()
        application_version = load_app_settings().app_version
    except (ConfigurationError, ModelCatalogError, LabelManagerError):
        log_event(
            _LOGGER,
            "classification.page_initialization",
            outcome="failure",
        )
        st.error(
            "Classification settings or local data could not be loaded. Check the "
            "server configuration and local model or label catalog."
        )
        return

    try:
        ready_models = tuple(
            item for item in model_manager.list_status() if item.availability == "ready"
        )
    except ModelManagerError:
        log_event(
            _LOGGER,
            "classification.model_list",
            outcome="failure",
        )
        st.error(
            "The local model catalog is unavailable. Check Model Management and "
            "refresh the page."
        )
        return
    if ready_models:
        model_ids = [item.model_id for item in ready_models]
        model_names = {item.model_id: item.display_name for item in ready_models}
        model_id = st.selectbox(
            "Model",
            model_ids,
            format_func=model_names.__getitem__,
            key="classification_model_id",
        )
    else:
        st.info("No ready local models are available. Prepare one in Model Management.")
        st.selectbox(
            "Model",
            ["No ready model"],
            disabled=True,
            key="classification_model_placeholder",
        )
        model_id = ""

    try:
        catalog = label_manager.list_sets()
    except LabelManagerError:
        catalog = None
        st.error(
            "The candidate-label catalog is unavailable or invalid. Repair it in "
            "Candidate-Label Management."
        )

    if catalog is not None and catalog.sets:
        label_ids = [item.id for item in catalog.sets]
        label_names = {item.id: item.name for item in catalog.sets}
        label_set_id = st.selectbox(
            "Candidate-label set",
            label_ids,
            format_func=label_names.__getitem__,
            key="classification_label_set_id",
        )
    else:
        if catalog is not None:
            st.info(
                "No saved candidate-label sets are available. Create one in "
                "Candidate-Label Management."
            )
        st.selectbox(
            "Candidate-label set",
            ["No valid label set"],
            disabled=True,
            key="classification_label_placeholder",
        )
        label_set_id = ""

    text = st.text_area(
        "Text to classify",
        key="classification_text",
        height=180,
    )
    submit = st.button(
        "Classify text",
        disabled=not model_id or not label_set_id,
        key="classification_submit",
    )

    if not submit:
        return

    service = ClassificationService(
        model_manager,
        label_manager,
        PredictionStore(),
        application_version=application_version,
    )
    identity = service.identity_for(text, model_id, label_set_id)
    active_status = coordinator.check(identity)
    if active_status.state != "idle":
        st.info(f"{active_status.message} Request ID: {active_status.request_id}")
        return

    try:
        request = service.prepare_request(text, model_id, label_set_id)
    except ClassificationError as error:
        st.error(str(error))
        return
    started = coordinator.start(request, service)
    st.info(f"{started.message} Request ID: {started.request_id}")
    st.rerun()


render_classification()
