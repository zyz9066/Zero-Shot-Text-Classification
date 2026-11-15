import logging
from contextlib import contextmanager
from pathlib import Path

import pytest
from filelock import FileLock, Timeout

from app.config.label_catalog import LabelCatalog, LabelSet, serialize_catalog
from app.services.label_manager import LabelManager, LabelManagerError


def test_lifecycle_and_stale_changes(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    assert not manager.list_sets().sets
    first = manager.create("Topics", ["Sports", "Tech"])
    second = manager.create("Other", ["A", "B"])
    assert LabelManager(path).list_sets().sets == (first, second)
    changed = manager.update(first.id, first.revision, "TOPICS", ["A", "C"])
    with pytest.raises(LabelManagerError, match="(?i)refresh"):
        manager.update(first.id, first.revision, "Draft", ["A", "B"])
    with pytest.raises(LabelManagerError, match="(?i)refresh"):
        manager.remove(first.id, first.revision, confirmed=True)
    manager.remove(second.id, second.revision, confirmed=False)
    assert manager.list_sets().sets == (changed, second)
    manager.remove(first.id, changed.revision, confirmed=True)
    manager.remove(second.id, second.revision, confirmed=True)
    assert not LabelManager(path).list_sets().sets
    path.unlink()
    with pytest.raises(LabelManagerError, match="recover"):
        LabelManager(path).list_sets()


def test_finalization_uses_captured_identity_after_valid_edit(
    tmp_path: Path,
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    original = manager.create("Topics", ["Sports", "Tech"])
    edited = manager.update(original.id, original.revision, "Topics", ["News", "Tech"])

    with manager.finalize_set(original.id) as current:
        assert current == edited
        assert current.revision != original.revision


def test_finalization_rejects_removed_set(tmp_path: Path) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    saved = manager.create("Topics", ["Sports", "Tech"])
    manager.remove(saved.id, saved.revision, confirmed=True)

    with pytest.raises(LabelManagerError) as error:
        with manager.finalize_set(saved.id):
            pytest.fail("Removed label set must not be finalized")

    assert error.value.kind == "unavailable"
    assert "no longer available" in str(error.value)


def test_invalid_and_duplicate_changes_preserve_saved_data(tmp_path: Path) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    saved = manager.create("Topics", ["Sports", "Tech"])
    for name, labels in [
        ("topics", ["A", "B"]),
        ("", ["A", "B"]),
        ("New", ["A", " a "]),
        ("New", ["A", ""]),
    ]:
        with pytest.raises(LabelManagerError):
            manager.create(name, labels)
    assert manager.list_sets().sets == (saved,)


def test_validation_reports_all_affected_fields(tmp_path: Path) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    with pytest.raises(LabelManagerError) as error:
        manager.create("", ["", "A", "a"])
    assert "Name:" in str(error.value)
    assert "Label 1:" in str(error.value)
    assert "Label 3:" in str(error.value)


def test_non_utf8_values_are_rejected_without_changing_saved_data(
    tmp_path: Path,
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    saved = manager.create("Valid", ["A", "B"])
    with pytest.raises(LabelManagerError) as error:
        manager.create("bad\ud800", ["Valid", "bad\udfff"])
    assert error.value.kind == "validation"
    assert "Name:" in str(error.value)
    assert "Label 2:" in str(error.value)
    assert "\ud800" not in str(error.value)
    with pytest.raises(LabelManagerError):
        manager.update(saved.id, saved.revision, "Valid", ["A", "bad\ud800"])
    assert manager.list_sets().sets == (saved,)
    multilingual = manager.create("主题", ["体育", "科技 \U0001f4bb"])
    assert manager.list_sets().sets == (saved, multilingual)


def test_non_utf8_saved_catalog_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    saved = manager.create("Valid", ["A", "B"])
    invalid = LabelSet(
        "8fbdc477-1e0f-40c8-8ff1-f6751b50ec35", 1, "Other", ("bad\ud800", "B")
    )
    path.write_text(serialize_catalog(LabelCatalog((saved, invalid))), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(LabelManagerError) as error:
        manager.list_sets()
    assert error.value.kind == "recovery"
    with pytest.raises(LabelManagerError):
        manager.create("New", ["A", "B"])
    assert path.read_bytes() == before


def test_invalid_catalog_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    manager.create("Valid", ["A", "B"])
    path.write_text("schema_version: 1\nsets: [invalid]\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(LabelManagerError):
        manager.list_sets()
    with pytest.raises(LabelManagerError):
        manager.create("New", ["A", "B"])
    assert path.read_bytes() == before


@pytest.mark.parametrize("invalid_file", ["catalog", "marker"])
def test_nested_yaml_fails_closed_and_preserves_files(
    tmp_path: Path, invalid_file: str
) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    manager.create("Valid", ["A", "B"])
    target = path if invalid_file == "catalog" else manager.marker
    target.write_text("value: " + "[" * 1500 + "x" + "]" * 1500, encoding="utf-8")
    before_catalog = path.read_bytes()
    before_marker = manager.marker.read_bytes()
    with pytest.raises(LabelManagerError) as error:
        manager.list_sets()
    assert error.value.kind == "recovery"
    assert "repair" in str(error.value).lower()
    assert str(tmp_path).casefold() not in str(error.value).casefold()
    with pytest.raises(LabelManagerError):
        manager.create("New", ["A", "B"])
    assert path.read_bytes() == before_catalog
    assert manager.marker.read_bytes() == before_marker


@pytest.mark.parametrize("invalid_file", ["catalog", "marker"])
def test_invalid_yaml_scalar_fails_closed_and_preserves_files(
    tmp_path: Path, invalid_file: str
) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    manager.create("Valid", ["A", "B"])
    target = path if invalid_file == "catalog" else manager.marker
    target.write_text("invalid: 2024-99-99\n", encoding="utf-8")
    before_catalog = path.read_bytes()
    before_marker = manager.marker.read_bytes()
    with pytest.raises(LabelManagerError) as error:
        manager.list_sets()
    assert error.value.kind == "recovery"
    assert "repair" in str(error.value).lower()
    assert str(tmp_path).casefold() not in str(error.value).casefold()
    with pytest.raises(LabelManagerError):
        manager.create("New", ["A", "B"])
    assert path.read_bytes() == before_catalog
    assert manager.marker.read_bytes() == before_marker


def test_provisioned_catalog_and_invalid_marker(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    item = LabelSet("8fbdc477-1e0f-40c8-8ff1-f6751b50ec35", 1, "T", ("A", "B"))
    path.write_text(serialize_catalog(LabelCatalog((item,))), encoding="utf-8")
    manager = LabelManager(path)
    snapshot = manager.list_sets()
    assert snapshot.sets == (item,)
    assert snapshot.warning
    manager.marker.write_text("schema_version: true", encoding="utf-8")
    with pytest.raises(LabelManagerError, match="(?i)recover"):
        manager.list_sets()
    with pytest.raises(LabelManagerError):
        manager.create("Other", ["A", "B"])
    assert path.read_text(encoding="utf-8") == serialize_catalog(LabelCatalog((item,)))


def test_precommit_failure_and_interrupted_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    original = manager.create("Original", ["A", "B"])

    def fail_sync(_fd: int) -> None:
        raise OSError("sensitive path")

    monkeypatch.setattr("app.services.label_manager.os.fsync", fail_sync)
    with pytest.raises(LabelManagerError) as error:
        manager.create("New", ["A", "B"])
    assert error.value.kind == "write"
    assert "sensitive path" not in str(error.value)
    assert manager.list_sets().sets == (original,)

    other = LabelManager(tmp_path / "other.yaml")
    monkeypatch.undo()
    other._establish_marker()
    with pytest.raises(LabelManagerError, match="(?i)recover"):
        other.list_sets()


def test_indeterminate_outcome_after_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    manager.create("Original", ["A", "B"])

    def fail_directory_sync(_path: Path) -> None:
        raise OSError("secret")

    monkeypatch.setattr(manager, "_sync_directory", fail_directory_sync)
    with pytest.raises(LabelManagerError) as error:
        manager.create("New", ["A", "B"])
    assert error.value.kind == "indeterminate"
    assert "inspect" in str(error.value).lower()
    assert "secret" not in str(error.value)
    assert len(manager.list_sets().sets) == 2


def test_lock_timeout_fails_closed(tmp_path: Path) -> None:
    manager = LabelManager(tmp_path / "labels.yaml", timeout=0.05)
    with FileLock(manager.lock_path, preserve_lock_file=True):
        with pytest.raises(LabelManagerError) as error:
            manager.create("Name", ["A", "B"])
    assert error.value.kind == "lock"
    assert not manager.path.exists()


def test_unreadable_catalog_and_failed_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    saved = manager.create("Name", ["A", "B"])
    original = manager.path.read_bytes()
    real_read = Path.read_text

    def fail_read(path: Path, *args, **kwargs):
        if path == manager.path:
            raise PermissionError("secret path")
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    with pytest.raises(LabelManagerError) as error:
        manager.list_sets()
    assert error.value.kind == "recovery"
    assert "secret" not in str(error.value)
    monkeypatch.undo()

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("private")

    monkeypatch.setattr("app.services.label_manager.os.replace", fail_replace)
    with pytest.raises(LabelManagerError) as error:
        manager.remove(saved.id, saved.revision, confirmed=True)
    assert error.value.kind == "indeterminate"
    assert manager.path.read_bytes() == original
    assert "private" not in str(error.value)


def test_marker_write_failure_blocks_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")

    def fail_sync(_fd: int) -> None:
        raise OSError("private")

    monkeypatch.setattr("app.services.label_manager.os.fsync", fail_sync)
    with pytest.raises(LabelManagerError) as error:
        manager.create("Name", ["A", "B"])
    assert error.value.kind == "recovery"
    assert "private" not in str(error.value)
    assert not manager.path.exists()
    assert not manager.marker.exists()


def test_debug_logging_does_not_expose_lock_path(tmp_path: Path, caplog) -> None:
    manager = LabelManager(tmp_path / "sensitive" / "labels.yaml")
    manager.path.parent.mkdir()
    with caplog.at_level(logging.DEBUG):
        manager.create("Name", ["A", "B"])
    assert str(manager.lock_path) not in caplog.text


@pytest.mark.parametrize("error_type", [OSError, RuntimeError, ValueError])
def test_path_resolution_failure_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    def fail_resolve(_path: Path) -> Path:
        raise error_type("private path")

    monkeypatch.setattr(Path, "resolve", fail_resolve)
    with pytest.raises(LabelManagerError) as error:
        LabelManager(tmp_path / "labels.yaml")
    assert error.value.kind == "recovery"
    assert "private path" not in str(error.value)
    assert "configuration" in str(error.value).lower()


def test_root_catalog_path_is_a_safe_configuration_error() -> None:
    root = Path(Path.cwd().anchor)
    with pytest.raises(LabelManagerError) as error:
        LabelManager(root)
    assert error.value.kind == "recovery"
    assert "configuration" in str(error.value).lower()
    assert str(root).casefold() not in str(error.value).casefold()


def test_sidecar_path_failure_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_with_name(_path: Path, _name: str) -> Path:
        raise ValueError("private path")

    monkeypatch.setattr(Path, "with_name", fail_with_name)
    with pytest.raises(LabelManagerError) as error:
        LabelManager(tmp_path / "labels.yaml")
    assert error.value.kind == "recovery"
    assert "private path" not in str(error.value)


@pytest.mark.parametrize("operation", ["create", "update", "remove"])
@pytest.mark.parametrize("release_error", [OSError, Timeout])
def test_lock_release_failure_after_commit_is_indeterminate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    release_error: type[Exception],
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    saved = manager.create("Original", ["A", "B"])
    real_lock = manager._lock

    @contextmanager
    def failing_release():
        with real_lock():
            yield
        raise release_error("private lock failure")

    monkeypatch.setattr(manager, "_lock", failing_release)
    with pytest.raises(LabelManagerError) as error:
        if operation == "create":
            manager.create("New", ["C", "D"])
        elif operation == "update":
            manager.update(saved.id, saved.revision, "Changed", ["A", "B"])
        else:
            manager.remove(saved.id, saved.revision, confirmed=True)
    assert error.value.kind == "indeterminate"
    assert "inspect" in str(error.value).lower()
    assert "private" not in str(error.value)
    monkeypatch.undo()
    names = [item.name for item in manager.list_sets().sets]
    assert (
        names
        == {
            "create": ["Original", "New"],
            "update": ["Changed"],
            "remove": [],
        }[operation]
    )


@pytest.mark.parametrize(
    "failure_point", ["before_replace", "after_replace", "release"]
)
def test_write_logs_match_actual_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    manager = LabelManager(tmp_path / "labels.yaml")
    manager.create("Original", ["A", "B"])
    events: list[tuple[str, str]] = []

    def capture_event(_logger, name, **fields):
        events.append((name, fields["outcome"]))

    monkeypatch.setattr("app.services.label_manager.log_event", capture_event)
    if failure_point == "before_replace":

        def fail_sync(_fd):
            raise OSError("private path")

        monkeypatch.setattr("app.services.label_manager.os.fsync", fail_sync)
    elif failure_point == "after_replace":

        def fail_directory_sync(_path):
            raise OSError("private path")

        monkeypatch.setattr(manager, "_sync_directory", fail_directory_sync)
    else:
        real_lock = manager._lock

        @contextmanager
        def fail_release():
            with real_lock():
                yield
            raise OSError("private path")

        monkeypatch.setattr(manager, "_lock", fail_release)

    with pytest.raises(LabelManagerError) as error:
        manager.create("New", ["C", "D"])
    expected = "failure" if failure_point == "before_replace" else "indeterminate"
    assert error.value.kind == ("write" if expected == "failure" else expected)
    assert events == [("label_configuration.write", expected)]
