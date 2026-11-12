import io
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

import app.services.model_manager as model_manager_module
from app.config.model_catalog import ConfiguredModel
from app.config.settings import ModelRuntimeSettings
from app.services.huggingface_hub_adapter import CacheCleanupPreview
from app.services.model_manager import ModelManager
from app.utils.logging_config import configure_logging


class FakeHubAdapter:
    def __init__(self, snapshot_path: Path) -> None:
        self.snapshot_path = snapshot_path
        self.download_calls = 0
        self.clear_cache_calls = 0
        self.download_started = threading.Event()
        self.allow_download = threading.Event()
        self.fail_download = False

    def resolve_revision(
        self, model_id: str, requested_revision: str | None = None
    ) -> str:
        del model_id, requested_revision
        return "a" * 40

    def download_snapshot(
        self,
        model_id: str,
        revision: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> Path:
        del model_id, revision
        self.download_calls += 1
        if progress_callback is not None:
            progress_callback(0.5)
        self.download_started.set()
        self.allow_download.wait(timeout=2)
        if self.fail_download:
            raise RuntimeError("network failure with private path")
        return self.snapshot_path

    def preview_cache_cleanup(self) -> CacheCleanupPreview:
        return CacheCleanupPreview(Path("cache"), 1, 2, 1024, 1)

    def clear_cache(self) -> int:
        self.clear_cache_calls += 1
        return 1024


def make_manager(
    tmp_path: Path,
    adapter: FakeHubAdapter,
    model: ConfiguredModel | None = None,
) -> ModelManager:
    configured_model = model or ConfiguredModel(
        "org/model", "Test Model", "zero-shot-classification"
    )
    return ModelManager(
        (configured_model,),
        ModelRuntimeSettings(
            model_dir=tmp_path / "models",
            hf_home=tmp_path / "hf-home",
            transformers_cache=tmp_path / "hub-cache",
        ),
        adapter,
    )


def wait_for_state(manager: ModelManager, operation_id: str, state: str) -> object:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        operation = manager.get_operation(operation_id)
        if operation.state == state:
            return operation
        threading.Event().wait(0.01)
    raise AssertionError(f"Operation did not reach {state}")


def make_snapshot(tmp_path: Path) -> Path:
    snapshot_path = tmp_path / "snapshot"
    snapshot_path.mkdir()
    (snapshot_path / "config.json").write_text("{}", encoding="utf-8")
    return snapshot_path


def test_model_manager_does_not_retain_runtime_hf_token(tmp_path: Path) -> None:
    settings = ModelRuntimeSettings(
        model_dir=tmp_path / "models",
        hf_home=tmp_path / "hf-home",
        transformers_cache=tmp_path / "hub-cache",
        hf_token="private-token",
    )
    model = ConfiguredModel("org/model", "Test Model", "zero-shot-classification")
    manager = ModelManager((model,), settings, FakeHubAdapter(make_snapshot(tmp_path)))

    assert manager.settings.hf_token is None


def test_lifecycle_events_include_safe_model_identifier(
    tmp_path: Path, monkeypatch
) -> None:
    output = io.StringIO()
    logger = configure_logging("test.model_lifecycle", stream=output)
    monkeypatch.setattr(model_manager_module, "_LOGGER", logger)
    manager = make_manager(tmp_path, FakeHubAdapter(make_snapshot(tmp_path)))

    operation = manager.delete_model("org/model", confirmed=True)

    records = [json.loads(line) for line in output.getvalue().splitlines()]
    assert operation.state == "succeeded"
    assert [record["outcome"] for record in records] == ["started", "success"]
    assert all(record["model_id"] == "org/model" for record in records)


def test_download_promotes_manifest_and_reuses_ready_model(tmp_path: Path) -> None:
    adapter = FakeHubAdapter(make_snapshot(tmp_path))
    adapter.allow_download.set()
    manager = make_manager(tmp_path, adapter)

    operation = manager.request_download("org/model")
    completed = wait_for_state(manager, operation.operation_id, "succeeded")
    status = manager.get_status("org/model")

    assert completed.resolved_revision == "a" * 40
    assert status.availability == "ready"
    assert status.resolved_revision == "a" * 40
    manifest_path = manager.model_directory("org/model") / ".model-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["model_id"] == "org/model"
    assert manifest["resolved_revision"] == "a" * 40

    reused = manager.request_download("org/model")

    assert reused.state == "succeeded"
    assert adapter.download_calls == 1


def test_same_model_in_flight_request_reuses_existing_operation(
    tmp_path: Path,
) -> None:
    adapter = FakeHubAdapter(make_snapshot(tmp_path))
    manager = make_manager(tmp_path, adapter)

    first = manager.request_download("org/model")
    assert adapter.download_started.wait(timeout=2)
    second = manager.request_download("org/model")
    adapter.allow_download.set()

    assert second.operation_id == first.operation_id
    assert adapter.download_calls == 1
    assert wait_for_state(manager, first.operation_id, "succeeded").state == "succeeded"


def test_status_reports_hub_transfer_progress(tmp_path: Path) -> None:
    adapter = FakeHubAdapter(make_snapshot(tmp_path))
    manager = make_manager(tmp_path, adapter)

    operation = manager.request_download("org/model")
    assert adapter.download_started.wait(timeout=2)
    status = manager.get_status("org/model")
    adapter.allow_download.set()

    assert status.availability == "downloading"
    assert status.progress == 0.4
    assert status.safe_message == "Downloading model snapshot (50%)"
    completed = wait_for_state(manager, operation.operation_id, "succeeded")
    assert completed.state == "succeeded"


def test_failed_download_is_not_ready_and_preserves_existing_installation(
    tmp_path: Path,
) -> None:
    adapter = FakeHubAdapter(make_snapshot(tmp_path))
    adapter.fail_download = True
    adapter.allow_download.set()
    model = ConfiguredModel("org/model", "Test Model", "zero-shot-classification", "v2")
    manager = make_manager(tmp_path, adapter, model)
    existing_directory = manager.model_directory("org/model")
    existing_directory.mkdir(parents=True)
    (existing_directory / "existing.bin").write_text("complete", encoding="utf-8")
    (existing_directory / ".model-manifest.json").write_text(
        json.dumps(
            {
                "model_id": "org/model",
                "requested_revision": "v1",
                "resolved_revision": "b" * 40,
                "completed_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    operation = manager.request_download("org/model")
    failed = wait_for_state(manager, operation.operation_id, "failed")

    assert "private path" not in failed.safe_message
    assert manager.get_status("org/model").availability == "failed"
    assert (existing_directory / "existing.bin").read_text(
        encoding="utf-8"
    ) == "complete"

    adapter.fail_download = False
    adapter.allow_download.clear()
    adapter.download_started.clear()
    retry = manager.request_download("org/model")
    assert adapter.download_started.wait(timeout=2)
    duplicate_retry = manager.request_download("org/model")
    adapter.allow_download.set()
    completed_retry = wait_for_state(manager, retry.operation_id, "succeeded")

    assert duplicate_retry.operation_id == retry.operation_id
    assert completed_retry.state == "succeeded"
    assert adapter.download_calls == 2
    assert manager.get_status("org/model").availability == "ready"
    assert (existing_directory / "config.json").exists()


def test_deletion_requires_confirmation_and_is_limited_to_selected_model(
    tmp_path: Path,
) -> None:
    adapter = FakeHubAdapter(make_snapshot(tmp_path))
    manager = make_manager(tmp_path, adapter)
    model_directory = manager.model_directory("org/model")
    model_directory.mkdir(parents=True)
    (model_directory / "weights.bin").write_text("weights", encoding="utf-8")
    unrelated = tmp_path / "models" / "unrelated.txt"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("keep", encoding="utf-8")

    cancelled = manager.delete_model("org/model", confirmed=False)
    assert cancelled.state == "cancelled"
    assert (model_directory / "weights.bin").exists()

    deleted = manager.delete_model("org/model", confirmed=True)

    assert deleted.state == "succeeded"
    assert not model_directory.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_cache_cleanup_is_separate_and_requires_confirmation(
    tmp_path: Path,
) -> None:
    adapter = FakeHubAdapter(make_snapshot(tmp_path))
    manager = make_manager(tmp_path, adapter)
    managed_model = manager.model_directory("org/model")
    managed_model.mkdir(parents=True)
    retained_artifact = managed_model / "weights.bin"
    retained_artifact.write_text("keep", encoding="utf-8")

    preview = manager.preview_cache_cleanup()
    cancelled = manager.clear_cache(confirmed=False)

    assert preview.repository_count == 1
    assert cancelled.state == "cancelled"
    assert adapter.clear_cache_calls == 0

    cleared = manager.clear_cache(confirmed=True)

    assert cleared.state == "succeeded"
    assert adapter.clear_cache_calls == 1
    assert retained_artifact.read_text(encoding="utf-8") == "keep"
