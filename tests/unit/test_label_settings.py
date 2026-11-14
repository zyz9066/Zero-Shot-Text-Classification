from pathlib import Path

import pytest

from app.config.label_settings import LabelSettingsError, resolve_label_path


def test_path_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(tmp_path / "environment.yaml"))
    assert resolve_label_path(tmp_path / "explicit.yaml") == tmp_path / "explicit.yaml"
    assert resolve_label_path() == tmp_path / "environment.yaml"
    monkeypatch.delenv("LABEL_CONFIG_FILE")
    assert resolve_label_path() == Path("configs/labels.yaml")


def test_empty_environment_override_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LABEL_CONFIG_FILE", "  ")
    with pytest.raises(LabelSettingsError, match="LABEL_CONFIG_FILE"):
        resolve_label_path()
