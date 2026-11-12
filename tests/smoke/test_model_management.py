from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parents[2] / "app" / "streamlit_app.py"
MODEL_PAGE = "pages/model_management.py"


def test_model_management_page_renders_without_hugging_face_token(
    monkeypatch,
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)

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
