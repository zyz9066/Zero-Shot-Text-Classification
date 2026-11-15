from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path
from time import monotonic, sleep

import pytest

from app.config.label_catalog import LabelSet
from app.config.model_catalog import ConfiguredModel
from app.config.settings import ModelRuntimeSettings
from app.services.label_manager import LabelManager, LabelManagerError
from app.services.model_manager import ModelManager


class EmptyHub:
    def resolve_revision(self, model_id: str, requested_revision: str | None = None):
        del model_id, requested_revision
        return "a" * 40

    def download_snapshot(self, model_id: str, revision: str, progress_callback=None):
        del model_id, revision, progress_callback
        raise AssertionError("This test must not download models")

    def preview_cache_cleanup(self):
        raise AssertionError("This test does not use cache cleanup")

    def clear_cache(self):
        raise AssertionError("This test does not use cache cleanup")


class SnapshotHub(EmptyHub):
    def __init__(self, snapshot_path: Path) -> None:
        self.snapshot_path = snapshot_path

    def download_snapshot(self, model_id: str, revision: str, progress_callback=None):
        del model_id, revision, progress_callback
        return self.snapshot_path


def make_model_manager(
    model_dir: Path, timeout: float = 10, hub_adapter=None
) -> ModelManager:
    return ModelManager(
        (ConfiguredModel("org/model", "Test Model", "zero-shot-classification"),),
        ModelRuntimeSettings(
            model_dir=model_dir,
            hf_home=model_dir.parent / "hf-home",
            transformers_cache=model_dir.parent / "hub-cache",
        ),
        hub_adapter or EmptyHub(),
        use_timeout=timeout,
    )


def _hold_model_use(model_dir: Path, ready, release) -> None:
    manager = make_model_manager(model_dir)
    with manager.model_use_guard("org/model"):
        ready.set()
        release.wait(10)


def _delete_model(model_dir: Path, result) -> None:
    operation = make_model_manager(model_dir, timeout=0.1).delete_model(
        "org/model", confirmed=True
    )
    result.put(operation.state)


def _download_while_model_is_held(model_dir: Path, snapshot_path: Path, result) -> None:
    manager = make_model_manager(
        model_dir,
        timeout=0.1,
        hub_adapter=SnapshotHub(snapshot_path),
    )
    operation = manager.request_download("org/model")
    deadline = monotonic() + 10
    while monotonic() < deadline:
        current = manager.get_operation(operation.operation_id)
        if current.state != "running":
            result.put(current.state)
            return
        sleep(0.05)
    result.put("timed_out")


def test_model_guard_serializes_app_managed_deletion(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    context = get_context("spawn")
    ready, release = context.Event(), context.Event()
    result = context.Queue()
    holder = context.Process(target=_hold_model_use, args=(model_dir, ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        deleter = context.Process(target=_delete_model, args=(model_dir, result))
        deleter.start()
        deleter.join(10)
        assert deleter.exitcode == 0
        assert result.get(timeout=5) == "failed"
    finally:
        release.set()
        holder.join(15)
    assert holder.exitcode == 0

    assert (
        make_model_manager(model_dir, timeout=0.2)
        .delete_model("org/model", confirmed=True)
        .state
        == "succeeded"
    )


def test_model_guard_serializes_download_promotion(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    snapshot_path = tmp_path / "snapshot"
    model_dir.mkdir()
    snapshot_path.mkdir()
    (snapshot_path / "config.json").write_text("{}", encoding="utf-8")
    context = get_context("spawn")
    ready, release = context.Event(), context.Event()
    result = context.Queue()
    holder = context.Process(target=_hold_model_use, args=(model_dir, ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        downloader = context.Process(
            target=_download_while_model_is_held,
            args=(model_dir, snapshot_path, result),
        )
        downloader.start()
        downloader.join(15)
        assert downloader.exitcode == 0
        assert result.get(timeout=5) == "failed"
    finally:
        release.set()
        holder.join(15)
    assert holder.exitcode == 0
    assert not list(model_dir.glob("org--model-*"))


def _hold_label_finalization(path: Path, identifier: str, ready, release) -> None:
    with LabelManager(path).finalize_set(identifier):
        ready.set()
        release.wait(10)


def _update_label(path: Path, item: LabelSet, result) -> None:
    try:
        LabelManager(path, timeout=0.1).update(
            item.id, item.revision, "Changed", ["Updated", "Labels"]
        )
        result.put("saved")
    except LabelManagerError as error:
        result.put(error.kind)


def _remove_label(path: Path, item: LabelSet, result) -> None:
    try:
        LabelManager(path, timeout=0.1).remove(
            item.id,
            item.revision,
            confirmed=True,
        )
        result.put("removed")
    except LabelManagerError as error:
        result.put(error.kind)


@pytest.mark.parametrize("operation", ["edit", "remove"])
def test_label_finalization_blocks_removal_or_edit_until_storage_finishes(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "labels.yaml"
    item = LabelManager(path).create("Topics", ["Sports", "News"])
    context = get_context("spawn")
    ready, release = context.Event(), context.Event()
    result = context.Queue()
    holder = context.Process(
        target=_hold_label_finalization, args=(path, item.id, ready, release)
    )
    holder.start()
    try:
        assert ready.wait(10)
        mutation = context.Process(
            target=_update_label if operation == "edit" else _remove_label,
            args=(path, item, result),
        )
        mutation.start()
        mutation.join(10)
        assert mutation.exitcode == 0
        assert result.get(timeout=5) == "lock"
    finally:
        release.set()
        holder.join(15)
    assert holder.exitcode == 0

    if operation == "edit":
        updated = LabelManager(path).update(
            item.id, item.revision, "Changed", ["Updated", "Labels"]
        )
        assert updated.revision == item.revision + 1
    else:
        LabelManager(path).remove(item.id, item.revision, confirmed=True)
        assert not LabelManager(path).list_sets().sets
