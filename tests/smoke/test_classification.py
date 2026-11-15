from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import streamlit as st
from streamlit.testing.v1 import AppTest

import app.config.loader as config_loader
import app.services.classification as classification
import app.services.label_manager as label_manager
import app.services.model_provider as model_provider
from app.services.classification import (
    CandidateLabelSnapshot,
    ClassificationOutcome,
    ClassificationRequest,
    ModelSnapshot,
    PredictionResult,
    RankedResult,
    RequestIdentity,
    SubmissionStatus,
)

APP_PATH = Path(__file__).parents[2] / "app" / "streamlit_app.py"
CLASSIFICATION_PAGE = "pages/classification.py"


def test_classification_page_has_labeled_controls_and_storage_notice(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(tmp_path / "hub-cache"))
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(tmp_path / "labels.yaml"))
    st.cache_resource.clear()

    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception

    app.switch_page(CLASSIFICATION_PAGE).run(timeout=10)

    assert not app.exception
    labels = [element.label for element in app.text_area]
    labels.extend(element.label for element in app.selectbox)
    assert "Text to classify" in labels
    assert "Model" in labels
    assert "Candidate-label set" in labels
    assert any(
        "stored in the configured MinIO bucket" in element.value for element in app.info
    )

    app.text_area[0].set_value("draft text").run()

    assert not app.exception
    assert app.text_area[0].value == "draft text"
    submit = next(item for item in app.button if item.key == "classification_submit")
    assert submit.disabled


def test_classification_shell_does_not_require_storage_credentials(
    monkeypatch,
) -> None:
    for key in (
        "MINIO_ENDPOINT",
        "MINIO_SECURE",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception


def test_classification_page_displays_only_a_confirmed_saved_result(
    monkeypatch,
) -> None:
    request_id = str(uuid4())
    request = ClassificationRequest(
        request_id,
        "non-sensitive input",
        ModelSnapshot("org/model", "Test Model", "a" * 40, "models/local"),
        CandidateLabelSnapshot("labels-id", 1, "Topics", ("sports", "news")),
    )
    result = PredictionResult(
        request_id,
        request.text,
        "sports",
        0.8,
        ("sports", "news"),
        (RankedResult("sports", 0.8), RankedResult("news", 0.2)),
        "Test Model",
        "org/model",
        "a" * 40,
        "2026-11-14T20:00:00+00:00",
        "0.1.0",
    )
    outcome = ClassificationOutcome("saved", request, "Prediction saved.", result)

    class SavedCoordinator:
        def poll(self):
            return SubmissionStatus("saved", request_id, outcome.message, outcome)

    monkeypatch.setattr(
        model_provider,
        "get_model_manager",
        lambda: SimpleNamespace(
            list_status=lambda: (
                SimpleNamespace(
                    model_id="org/model",
                    display_name="Test Model",
                    availability="ready",
                ),
            )
        ),
    )
    monkeypatch.setattr(
        label_manager,
        "LabelManager",
        lambda: SimpleNamespace(
            list_sets=lambda: SimpleNamespace(
                sets=(SimpleNamespace(id="labels-id", name="Topics"),)
            )
        ),
    )
    monkeypatch.setattr(
        config_loader,
        "load_app_settings",
        lambda: SimpleNamespace(app_version="0.1.0"),
    )
    monkeypatch.setattr(
        classification, "SessionSubmissionCoordinator", SavedCoordinator
    )

    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(CLASSIFICATION_PAGE).run(timeout=10)

    assert not app.exception
    assert any("Prediction saved." in item.value for item in app.success)
    assert any("Top class: sports" in item.value for item in app.subheader)
    assert any("not a calibrated probability" in item.value for item in app.markdown)


def test_changed_in_progress_submission_keeps_text_and_exposes_status(
    monkeypatch,
) -> None:
    request_id = str(uuid4())
    blocked_message = (
        "A classification is already processing. Submit this text and selections "
        "after it finishes."
    )

    class ActiveCoordinator:
        def poll(self):
            return SubmissionStatus(
                "in_progress",
                request_id,
                "Classification is processing.",
            )

        def check(self, _identity):
            return SubmissionStatus("blocked", request_id, blocked_message)

    class UnusedService:
        def __init__(self, *_args, **_kwargs):
            pass

        def identity_for(self, text, model_id, label_set_id):
            return RequestIdentity(text, model_id, None, label_set_id, 1)

    monkeypatch.setattr(
        model_provider,
        "get_model_manager",
        lambda: SimpleNamespace(
            list_status=lambda: (
                SimpleNamespace(
                    model_id="org/model",
                    display_name="Test Model",
                    availability="ready",
                ),
            )
        ),
    )
    monkeypatch.setattr(
        label_manager,
        "LabelManager",
        lambda: SimpleNamespace(
            list_sets=lambda: SimpleNamespace(
                sets=(SimpleNamespace(id="labels-id", name="Topics"),)
            )
        ),
    )
    monkeypatch.setattr(
        config_loader,
        "load_app_settings",
        lambda: SimpleNamespace(app_version="0.1.0"),
    )
    monkeypatch.setattr(
        classification,
        "SessionSubmissionCoordinator",
        ActiveCoordinator,
    )
    monkeypatch.setattr(classification, "ClassificationService", UnusedService)

    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(CLASSIFICATION_PAGE).run(timeout=10)
    app.text_area[0].set_value("changed text")
    app.button(key="classification_submit").click().run(timeout=10)

    assert not app.exception
    assert any("Classification is processing." in item.value for item in app.info)
    assert any(blocked_message in item.value for item in app.info)
    assert app.text_area[0].value == "changed text"
    assert app.selectbox[0].value == "org/model"
    assert app.selectbox[1].value == "labels-id"


def test_indeterminate_storage_outcome_has_safe_recovery_error(monkeypatch) -> None:
    request_id = str(uuid4())
    request = ClassificationRequest(
        request_id,
        "private input",
        ModelSnapshot("org/model", "Test Model", "a" * 40, "private/model/path"),
        CandidateLabelSnapshot("labels-id", 1, "Topics", ("sports", "news")),
    )
    outcome = ClassificationOutcome(
        "indeterminate",
        request,
        "Prediction storage did not confirm the write.",
    )

    class UncertainCoordinator:
        def poll(self):
            return SubmissionStatus(
                "indeterminate",
                request_id,
                outcome.message,
                outcome,
            )

    monkeypatch.setattr(
        classification,
        "SessionSubmissionCoordinator",
        UncertainCoordinator,
    )

    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(CLASSIFICATION_PAGE).run(timeout=10)

    assert not app.exception
    error = "\n".join(item.value for item in app.error)
    assert request_id in error
    assert "inspect" in error
    assert "Do not resubmit if it exists." in error
    assert "private input" not in error
    assert "private/model/path" not in error
