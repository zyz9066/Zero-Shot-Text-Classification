from pathlib import Path
from unittest.mock import Mock

import streamlit as st
from streamlit.testing.v1 import AppTest

from app.config.loader import load_model_settings
from app.config.model_catalog import load_model_catalog
from app.services.model_manager import ModelManager

APP_PATH = Path(__file__).parents[2] / "app" / "streamlit_app.py"
MODEL_PAGE = "pages/model_management.py"


def test_model_management_page_renders_without_hugging_face_token(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("MODEL_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(tmp_path / "hub-cache"))
    st.cache_resource.clear()

    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception

    app.switch_page(MODEL_PAGE).run(timeout=10)

    assert not app.exception
    captions = [element.value for element in app.caption]
    markdown = [element.value for element in app.markdown]
    subheaders = [element.value for element in app.subheader]
    warnings = [element.value for element in app.warning]
    assert "MoritzLaurer/deberta-v3-base-zeroshot-v2.0" in captions
    assert "facebook/bart-large-mnli" in captions
    assert "DeBERTa v3 Zero-Shot v2.0" in subheaders
    assert "BART Large MNLI" in subheaders
    assert sum("Availability: Missing" in value for value in markdown) == 2
    assert any("trusted environments" in value for value in warnings)


def test_incomplete_local_model_is_shown_as_incomplete(
    monkeypatch, tmp_path: Path
) -> None:
    model_root = tmp_path / "models"
    monkeypatch.setenv("MODEL_DIR", str(model_root))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))
    monkeypatch.setenv("TRANSFORMERS_CACHE", str(tmp_path / "hub-cache"))
    st.cache_resource.clear()

    manager = ModelManager(load_model_catalog(), load_model_settings(), Mock())
    incomplete_directory = manager.model_directory(
        "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
    )
    incomplete_directory.mkdir(parents=True)
    (incomplete_directory / "partial.bin").write_bytes(b"partial")

    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(MODEL_PAGE).run(timeout=10)

    assert not app.exception
    assert any("Availability: Incomplete" in element.value for element in app.markdown)
