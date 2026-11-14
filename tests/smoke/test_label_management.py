from contextlib import contextmanager
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.config.label_catalog import LabelCatalog, LabelSet, serialize_catalog
from app.services.label_manager import LabelManager, LabelManagerError

APP_PATH = Path(__file__).parents[2] / "app" / "streamlit_app.py"
PAGE = "pages/label_management.py"


def test_create_and_validate_without_credentials(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(tmp_path / "labels.yaml"))
    monkeypatch.delenv("HF_TOKEN", raising=False)
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    assert not app.exception
    app.text_input(key="label_name").set_value("Topics")
    app.text_area(key="label_values").set_value("Sports\nsports")
    app.button(key="label_save").click().run()
    assert any("duplicate" in item.value.lower() for item in app.error)
    assert app.text_input(key="label_name").value == "Topics"
    app.text_area(key="label_values").set_value("Sports\nTechnology")
    app.button(key="label_save").click().run()
    assert not app.exception
    assert any("saved" in item.value.lower() for item in app.success)


def test_draft_is_session_scoped_and_confirmation_is_required(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    saved = manager.create("Original", ["One", "Two"])
    first = AppTest.from_file(str(APP_PATH)).run()
    second = AppTest.from_file(str(APP_PATH)).run()
    first.switch_page(PAGE).run()
    second.switch_page(PAGE).run()
    first.button[0].click().run()
    first.text_input(key="label_name").set_value("Unsaved").run()
    assert second.text_input(key="label_name").value == ""
    assert first.button[-1].disabled
    first.checkbox[0].check().run()
    assert not first.button[-1].disabled
    first.checkbox[0].uncheck().run()
    assert manager.list_sets().sets == (saved,)


def test_stale_draft_remains_available(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    saved = manager.create("Original", ["One", "Two"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.button[0].click().run()
    app.text_input(key="label_name").set_value("Draft").run()
    manager.update(saved.id, saved.revision, "Changed", ["One", "Two"])
    app.button(key="label_save").click().run()
    assert any("refresh" in error.value.lower() for error in app.error)
    assert app.text_input(key="label_name").value == "Draft"


def test_confirmed_removal_and_draft_survives_navigation(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    manager.create("Original", ["One", "Two"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.button[0].click().run()
    app.text_input(key="label_name").set_value("Draft").run()
    app.switch_page("streamlit_app.py").run()
    app.switch_page(PAGE).run()
    assert app.text_input(key="label_name").value == "Draft"
    app.checkbox[0].check().run()
    app.button[-1].click().run()
    assert not app.exception
    assert manager.list_sets().sets == ()


def test_removal_cannot_target_a_different_set_than_selected(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    alpha = manager.create("Alpha", ["One", "Two"])
    beta = manager.create("Beta", ["Three", "Four"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    next(
        button for button in app.button if button.label == "Open selected set"
    ).click().run()
    app.text_input(key="label_name").set_value("My unsaved draft").run()
    app.checkbox[0].check().run()
    app.selectbox[0].select(beta.id).run()
    assert any(text.value == "Opened saved set: Alpha" for text in app.text)
    assert any(
        "open" in item.value.lower() and "selected" in item.value.lower()
        for item in app.info
    )
    assert next(
        button for button in app.button if button.label == "Remove opened set"
    ).disabled
    assert manager.list_sets().sets == (alpha, beta)
    assert app.text_input(key="label_name").value == "My unsaved draft"
    app.selectbox[0].select(alpha.id).run()
    assert not app.checkbox[0].value
    assert next(
        button for button in app.button if button.label == "Remove opened set"
    ).disabled
    app.selectbox[0].select(beta.id).run()
    next(
        button for button in app.button if button.label == "Open selected set"
    ).click().run()
    app.checkbox[0].check().run()
    next(
        button for button in app.button if button.label == "Remove opened set"
    ).click().run()
    assert not app.exception
    assert manager.list_sets().sets == (alpha,)


def test_edit_cannot_target_a_different_set_than_selected(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    alpha = manager.create("Alpha", ["One", "Two"])
    beta = manager.create("Beta", ["Three", "Four"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    next(
        button for button in app.button if button.label == "Open selected set"
    ).click().run()
    app.text_input(key="label_name").set_value("Edited Alpha").run()
    app.selectbox[0].select(beta.id).run()
    assert app.button(key="label_save").disabled
    assert any(text.value == "Opened saved set: Alpha" for text in app.text)
    assert any("selected" in item.value.lower() for item in app.info)
    assert app.text_input(key="label_name").value == "Edited Alpha"
    assert manager.list_sets().sets == (alpha, beta)
    app.selectbox[0].select(alpha.id).run()
    assert not app.button(key="label_save").disabled
    app.button(key="label_save").click().run()
    changed, unchanged = manager.list_sets().sets
    assert changed.id == alpha.id and changed.name == "Edited Alpha"
    assert unchanged == beta
    next(
        button for button in app.button if button.label == "Start a new set"
    ).click().run()
    app.selectbox[0].select(beta.id).run()
    app.text_input(key="label_name").set_value("New").run()
    app.text_area(key="label_values").set_value("A\nB").run()
    assert not app.button(key="label_save").disabled
    app.button(key="label_save").click().run()
    assert [item.name for item in manager.list_sets().sets] == [
        "Edited Alpha",
        "Beta",
        "New",
    ]


@pytest.mark.parametrize("removed", [False, True])
def test_stale_removal_preserves_draft(
    monkeypatch, tmp_path: Path, removed: bool
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    saved = manager.create("Original", ["One", "Two"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    next(
        button for button in app.button if button.label == "Open selected set"
    ).click().run()
    app.text_input(key="label_name").set_value("My unsaved draft").run()
    app.checkbox[0].check().run()
    if removed:
        manager.remove(saved.id, saved.revision, confirmed=True)
    else:
        manager.update(saved.id, saved.revision, "Changed", ["One", "Two"])
    next(
        button for button in app.button if button.label == "Remove opened set"
    ).click().run()
    assert not app.exception
    assert any("refresh" in error.value.lower() for error in app.error)
    assert app.text_input(key="label_name").value == "My unsaved draft"
    assert len(manager.list_sets().sets) == (0 if removed else 1)


def test_removed_opened_set_can_recover_draft_as_new(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    alpha = manager.create("Alpha", ["One", "Two"])
    beta = manager.create("Beta", ["Three", "Four"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    next(
        button for button in app.button if button.label == "Open selected set"
    ).click().run()
    app.text_input(key="label_name").set_value("Recovered Alpha").run()
    app.text_area(key="label_values").set_value("Unsaved\nLabels").run()
    manager.remove(alpha.id, alpha.revision, confirmed=True)
    app.run()
    assert not app.exception
    assert any(
        "removed" in notice.value.lower() and "refresh" in notice.value.lower()
        for notice in app.warning
    )
    assert app.button(key="label_save").disabled
    assert next(
        button for button in app.button if button.label == "Remove opened set"
    ).disabled
    assert app.text_input(key="label_name").value == "Recovered Alpha"
    assert app.text_area(key="label_values").value == "Unsaved\nLabels"
    assert manager.list_sets().sets == (beta,)
    next(
        button for button in app.button if button.label == "Use draft as a new set"
    ).click().run()
    assert app.text_input(key="label_name").value == "Recovered Alpha"
    assert app.text_area(key="label_values").value == "Unsaved\nLabels"
    app.button(key="label_save").click().run()
    unchanged, recovered = manager.list_sets().sets
    assert unchanged == beta
    assert recovered.name == "Recovered Alpha"
    assert recovered.labels == ("Unsaved", "Labels")


def test_invalid_catalog_shows_recovery_without_edit_controls(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    path.write_text("invalid: true", encoding="utf-8")
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    assert any("repair" in error.value.lower() for error in app.error)
    assert not app.text_input
    assert path.read_text(encoding="utf-8") == "invalid: true"


def test_non_utf8_saved_catalog_shows_safe_recovery(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    saved = manager.create("Valid", ["A", "B"])
    invalid = LabelSet(
        "8fbdc477-1e0f-40c8-8ff1-f6751b50ec35", 1, "Other", ("bad\ud800", "B")
    )
    path.write_text(serialize_catalog(LabelCatalog((saved, invalid))), encoding="utf-8")
    before = path.read_bytes()
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    assert not app.exception
    assert any("repair" in error.value.lower() for error in app.error)
    assert not app.text_input
    assert not app.selectbox
    assert path.read_bytes() == before


def test_draft_remains_editable_during_recovery(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    manager.create("Original", ["A", "B"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.text_input(key="label_name").set_value("My unsaved draft").run()
    path.write_text("invalid: true", encoding="utf-8")
    app.run()
    assert app.error
    assert app.text_input(key="label_name").value == "My unsaved draft"
    assert not app.button


def test_nested_yaml_shows_safe_recovery_and_retains_draft(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    manager.create("Original", ["A", "B"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.text_input(key="label_name").set_value("My unsaved draft").run()
    path.write_text("sets: " + "[" * 1500 + "x" + "]" * 1500, encoding="utf-8")
    before_catalog = path.read_bytes()
    before_marker = manager.marker.read_bytes()
    app.run()
    assert not app.exception
    assert any("repair" in error.value.lower() for error in app.error)
    assert all(str(tmp_path) not in error.value for error in app.error)
    assert app.text_input(key="label_name").value == "My unsaved draft"
    assert not app.button
    assert path.read_bytes() == before_catalog
    assert manager.marker.read_bytes() == before_marker


@pytest.mark.parametrize("invalid_file", ["catalog", "marker"])
def test_invalid_yaml_scalar_retains_draft_and_shows_recovery(
    monkeypatch, tmp_path: Path, invalid_file: str
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    manager.create("Original", ["A", "B"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.text_input(key="label_name").set_value("My unsaved draft").run()
    target = path if invalid_file == "catalog" else manager.marker
    target.write_text("invalid: 2024-99-99\n", encoding="utf-8")
    before_catalog = path.read_bytes()
    before_marker = manager.marker.read_bytes()
    app.run()
    assert not app.exception
    assert any("repair" in error.value.lower() for error in app.error)
    assert all(str(tmp_path) not in error.value for error in app.error)
    assert app.text_input(key="label_name").value == "My unsaved draft"
    assert not app.button
    assert not app.selectbox
    assert path.read_bytes() == before_catalog
    assert manager.marker.read_bytes() == before_marker


def test_path_resolution_error_preserves_draft(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(tmp_path / "labels.yaml"))
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.text_input(key="label_name").set_value("My draft").run()

    class BrokenPath:
        def resolve(self):
            raise OSError("private path")

    monkeypatch.setattr(
        "app.services.label_manager.resolve_label_path", lambda _path=None: BrokenPath()
    )
    app.run()
    assert not app.exception
    assert any("configuration" in error.value.lower() for error in app.error)
    assert all("private path" not in error.value for error in app.error)
    assert app.text_input(key="label_name").value == "My draft"
    assert not app.button


def test_root_catalog_path_preserves_draft(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(tmp_path / "labels.yaml"))
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.text_input(key="label_name").set_value("My draft").run()
    root = Path.cwd().anchor
    monkeypatch.setenv("LABEL_CONFIG_FILE", root)
    app.run()
    assert not app.exception
    assert any("configuration" in error.value.lower() for error in app.error)
    assert all(root.casefold() not in error.value.casefold() for error in app.error)
    assert app.text_input(key="label_name").value == "My draft"
    assert not app.button


def test_post_commit_release_failure_requires_inspection(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    manager.create("Original", ["A", "B"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.button[0].click().run()
    app.text_input(key="label_name").set_value("My draft").run()

    original_lock = LabelManager._lock
    original_write = LabelManager._write
    committed = False

    def track_write(self, sets, state):
        nonlocal committed
        original_write(self, sets, state)
        committed = True

    @contextmanager
    def fail_release(self):
        nonlocal committed
        with original_lock(self):
            yield
        if committed:
            committed = False
            raise OSError("private path")

    monkeypatch.setattr(LabelManager, "_lock", fail_release)
    monkeypatch.setattr(LabelManager, "_write", track_write)
    app.button(key="label_save").click().run()
    assert any("uncertain" in error.value.lower() for error in app.error)
    assert app.text_input(key="label_name").value == "My draft"
    app.run()
    assert app.button(key="label_save").disabled
    assert manager.list_sets().sets[0].name == "My draft"


def test_multiline_label_round_trips_without_splitting(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    saved = manager.create("*Topics*", ["Line one\nLine two", "Other"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.button[0].click().run()
    assert app.text_area(key="label_item_0").value == "Line one\nLine two"
    assert app.text_area(key="label_item_1").value == "Other"
    app.button(key="label_save").click().run()
    assert manager.list_sets().sets[0].labels == saved.labels
    app.text_area(key="label_item_0").set_value("Changed\nvalue").run()
    app.button(key="label_save").click().run()
    assert manager.list_sets().sets[0].labels == ("Changed\nvalue", "Other")
    assert any("*Topics*" in item.value for item in app.text)
    app.button(key="label_remove_item_1").click().run()
    next(button for button in app.button if button.label == "Add label").click().run()
    app.text_area(key="label_item_1").set_value("Replacement").run()
    app.switch_page("streamlit_app.py").run()
    app.switch_page(PAGE).run()
    assert app.text_area(key="label_item_0").value == "Changed\nvalue"
    assert app.text_area(key="label_item_1").value == "Replacement"
    app.button(key="label_save").click().run()
    assert manager.list_sets().sets[0].labels == ("Changed\nvalue", "Replacement")


def test_create_multiline_label_in_individual_mode(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.text_input(key="label_name").set_value("Topics").run()
    app.text_area(key="label_values").set_value("First\nSecond").run()
    next(
        button for button in app.button if button.label == "Edit labels individually"
    ).click().run()
    app.text_area(key="label_item_0").set_value("First\ncontinued").run()
    app.button(key="label_save").click().run()
    assert LabelManager(path).list_sets().sets[0].labels == (
        "First\ncontinued",
        "Second",
    )


def test_invalid_fields_then_successful_edit(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    original = manager.create("Original", ["A", "B"])
    untouched = manager.create("Untouched", ["C", "D"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.button[0].click().run()
    app.text_input(key="label_name").set_value("").run()
    app.text_area(key="label_values").set_value("A\n a ").run()
    app.button(key="label_save").click().run()
    assert any(
        "Name:" in error.value and "duplicate" in error.value for error in app.error
    )
    assert app.text_input(key="label_name").value == ""
    assert app.text_area(key="label_values").value == "A\n a "
    assert manager.list_sets().sets == (original, untouched)
    app.text_input(key="label_name").set_value("Edited").run()
    app.text_area(key="label_values").set_value("A\nNew").run()
    app.button(key="label_save").click().run()
    updated, other = manager.list_sets().sets
    assert (updated.name, updated.labels) == ("Edited", ("A", "New"))
    assert other == untouched


def test_precommit_write_failure_retains_draft(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    original = manager.create("Original", ["A", "B"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.button[0].click().run()
    app.text_input(key="label_name").set_value("Draft").run()
    original_replace = LabelManager._replace

    def fail_catalog_write(self, target, content):
        if target == self.path:
            raise LabelManagerError("The change was not saved; check storage.", "write")
        original_replace(self, target, content)

    monkeypatch.setattr(LabelManager, "_replace", fail_catalog_write)
    app.button(key="label_save").click().run()
    assert any("not saved" in error.value.lower() for error in app.error)
    assert app.text_input(key="label_name").value == "Draft"
    assert manager.list_sets().sets == (original,)


def test_indeterminate_write_requires_inspection_before_retry(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "labels.yaml"
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    manager = LabelManager(path)
    manager.create("Original", ["A", "B"])
    app = AppTest.from_file(str(APP_PATH)).run()
    app.switch_page(PAGE).run()
    app.button[0].click().run()
    app.text_input(key="label_name").set_value("Draft").run()

    def fail_sync(_path):
        raise OSError("private path")

    monkeypatch.setattr(LabelManager, "_sync_directory", staticmethod(fail_sync))
    app.button(key="label_save").click().run()
    assert any("uncertain" in error.value.lower() for error in app.error)
    assert app.text_input(key="label_name").value == "Draft"
    assert manager.list_sets().sets[0].name == "Draft"
    app.run()
    assert app.button(key="label_save").disabled
    monkeypatch.undo()
    monkeypatch.setenv("LABEL_CONFIG_FILE", str(path))
    next(
        button for button in app.button if button.label == "I inspected the saved sets"
    ).click().run()
    assert not app.button(key="label_save").disabled
    next(
        button
        for button in app.button
        if button.label == "Refresh selected revision while keeping draft"
    ).click().run()
    assert app.text_input(key="label_name").value == "Draft"
    app.button(key="label_save").click().run()
    assert any("saved" in item.value.lower() for item in app.success)
