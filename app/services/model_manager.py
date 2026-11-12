import hashlib
import json
import os
import re
import shutil
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from app.config.model_catalog import ConfiguredModel
from app.config.settings import ModelRuntimeSettings
from app.services.huggingface_hub_adapter import (
    CacheCleanupPreview,
    HubAdapterError,
)
from app.utils.logging_config import configure_logging, log_event

Availability = Literal["missing", "downloading", "ready", "failed"]
OperationKind = Literal["download", "delete", "cache_cleanup"]
OperationState = Literal["running", "succeeded", "failed", "cancelled"]
_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_MANIFEST_NAME = ".model-manifest.json"
_LOGGER = configure_logging("model_lifecycle")
_OPERATION_EVENTS: dict[OperationKind, str] = {
    "download": "model.download",
    "delete": "model.delete",
    "cache_cleanup": "model.cache_cleanup",
}


class HubAdapter(Protocol):
    def resolve_revision(
        self, model_id: str, requested_revision: str | None = None
    ) -> str: ...

    def download_snapshot(
        self,
        model_id: str,
        revision: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> Path: ...

    def preview_cache_cleanup(self) -> CacheCleanupPreview: ...

    def clear_cache(self) -> int: ...


@dataclass(frozen=True)
class ModelOperation:
    operation_id: str
    kind: OperationKind
    model_id: str | None
    requested_revision: str | None
    resolved_revision: str | None
    state: OperationState
    progress: float | None
    safe_message: str


@dataclass(frozen=True)
class ModelStatus:
    model_id: str
    display_name: str
    task: str
    requested_revision: str | None
    availability: Availability
    resolved_revision: str | None = None
    progress: float | None = None
    safe_message: str | None = None


@dataclass
class _OperationRecord:
    operation_id: str
    kind: OperationKind
    model_id: str | None
    requested_revision: str | None
    resolved_revision: str | None
    state: OperationState
    progress: float | None
    safe_message: str

    def snapshot(self) -> ModelOperation:
        return ModelOperation(
            operation_id=self.operation_id,
            kind=self.kind,
            model_id=self.model_id,
            requested_revision=self.requested_revision,
            resolved_revision=self.resolved_revision,
            state=self.state,
            progress=self.progress,
            safe_message=self.safe_message,
        )


class ModelManagerError(RuntimeError):
    pass


class ModelManager:
    def __init__(
        self,
        catalog: tuple[ConfiguredModel, ...],
        settings: ModelRuntimeSettings,
        hub_adapter: HubAdapter,
    ) -> None:
        self._catalog = {model.model_id: model for model in catalog}
        self.settings = replace(settings, hf_token=None)
        self._hub_adapter = hub_adapter
        self._lock = threading.RLock()
        self._operations: dict[str, _OperationRecord] = {}
        self._active_downloads: dict[str, str] = {}
        self._latest_model_operations: dict[str, str] = {}

    def list_status(self) -> tuple[ModelStatus, ...]:
        with self._lock:
            return tuple(self._status_for(model) for model in self._catalog.values())

    def get_status(self, model_id: str) -> ModelStatus:
        with self._lock:
            return self._status_for(self._get_model(model_id))

    def get_operation(self, operation_id: str) -> ModelOperation:
        with self._lock:
            record = self._operations.get(operation_id)
            if record is None:
                raise ModelManagerError("The requested model operation was not found")
            return record.snapshot()

    def model_directory(self, model_id: str) -> Path:
        self._get_model(model_id)
        safe_name = model_id.replace("/", "--")
        suffix = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:12]
        return self.settings.model_dir / f"{safe_name}-{suffix}"

    def request_download(self, model_id: str) -> ModelOperation:
        model = self._get_model(model_id)
        with self._lock:
            active_operation_id = self._active_downloads.get(model_id)
            if active_operation_id is not None:
                active = self._operations[active_operation_id]
                if active.state == "running":
                    return active.snapshot()

            if self._read_manifest(model) is not None:
                return self._new_operation(
                    "download",
                    model,
                    state="succeeded",
                    progress=1.0,
                    safe_message="The complete local model is already available",
                )

            operation = self._new_operation(
                "download",
                model,
                state="running",
                progress=0.0,
                safe_message="Model download started",
            )
            self._active_downloads[model_id] = operation.operation_id
            worker = threading.Thread(
                target=self._download_model,
                args=(model, operation.operation_id),
                daemon=True,
            )
            worker.start()
            return operation

    def delete_model(self, model_id: str, *, confirmed: bool) -> ModelOperation:
        model = self._get_model(model_id)
        if not confirmed:
            return self._new_operation(
                "delete",
                model,
                state="cancelled",
                progress=None,
                safe_message="Model deletion was cancelled",
            )

        with self._lock:
            active_operation_id = self._active_downloads.get(model_id)
            if active_operation_id is not None:
                active = self._operations[active_operation_id]
                if active.state == "running":
                    return self._new_operation(
                        "delete",
                        model,
                        state="failed",
                        progress=None,
                        safe_message=(
                            "Wait for the model download to finish before deleting it"
                        ),
                    )

            operation = self._new_operation(
                "delete",
                model,
                state="running",
                progress=None,
                safe_message="Model deletion started",
            )
            try:
                model_path = self._checked_model_path(model_id)
                if model_path.is_dir():
                    shutil.rmtree(model_path)
                elif model_path.exists() or model_path.is_symlink():
                    model_path.unlink()
            except Exception:
                return self._finish_operation(
                    operation.operation_id,
                    state="failed",
                    progress=None,
                    safe_message="Unable to delete the selected app-managed model",
                )
            return self._finish_operation(
                operation.operation_id,
                state="succeeded",
                progress=1.0,
                safe_message="The selected app-managed model was deleted",
            )

    def preview_cache_cleanup(self) -> CacheCleanupPreview:
        return self._hub_adapter.preview_cache_cleanup()

    def clear_cache(self, *, confirmed: bool) -> ModelOperation:
        if not confirmed:
            return self._new_operation(
                "cache_cleanup",
                None,
                state="cancelled",
                progress=None,
                safe_message="Hugging Face cache cleanup was cancelled",
            )

        operation = self._new_operation(
            "cache_cleanup",
            None,
            state="running",
            progress=None,
            safe_message="Hugging Face cache cleanup started",
        )
        try:
            freed_bytes = self._hub_adapter.clear_cache()
        except HubAdapterError as error:
            return self._finish_operation(
                operation.operation_id,
                state="failed",
                progress=None,
                safe_message=str(error),
            )
        except Exception:
            return self._finish_operation(
                operation.operation_id,
                state="failed",
                progress=None,
                safe_message="Unable to clear the configured Hugging Face cache",
            )
        return self._finish_operation(
            operation.operation_id,
            state="succeeded",
            progress=1.0,
            safe_message=(
                f"Hugging Face cache cleanup completed; {freed_bytes} bytes reclaimed"
            ),
        )

    def _download_model(self, model: ConfiguredModel, operation_id: str) -> None:
        stage_path: Path | None = None
        try:
            resolved_revision = self._hub_adapter.resolve_revision(
                model.model_id, model.requested_revision
            )
            self._update_operation(
                operation_id,
                resolved_revision=resolved_revision,
                progress=0.2,
                safe_message="Model revision resolved; downloading snapshot",
            )
            snapshot_path = self._hub_adapter.download_snapshot(
                model.model_id,
                resolved_revision,
                progress_callback=lambda progress: self._report_download_progress(
                    operation_id, progress
                ),
            )
            if not snapshot_path.is_dir():
                raise ModelManagerError("Downloaded snapshot is incomplete")
            self._update_operation(
                operation_id,
                progress=0.65,
                safe_message="Snapshot downloaded; preparing app-managed copy",
            )

            model_root = self.settings.model_dir.resolve()
            model_root.mkdir(parents=True, exist_ok=True)
            model_path = self._checked_model_path(model.model_id)
            stage_path = model_root / f".staging-{uuid.uuid4().hex}"
            shutil.copytree(snapshot_path, stage_path)
            manifest = {
                "model_id": model.model_id,
                "requested_revision": model.requested_revision,
                "resolved_revision": resolved_revision,
                "completed_at": datetime.now(UTC).isoformat(),
            }
            (stage_path / _MANIFEST_NAME).write_text(
                json.dumps(manifest, sort_keys=True), encoding="utf-8"
            )
            self._update_operation(
                operation_id,
                progress=0.9,
                safe_message="App-managed copy verified; finalizing installation",
            )
            self._promote_stage(stage_path, model_path)
            stage_path = None
            self._finish_operation(
                operation_id,
                state="succeeded",
                progress=1.0,
                safe_message="Model download completed and the model is ready",
            )
        except HubAdapterError as error:
            self._finish_operation(
                operation_id,
                state="failed",
                progress=None,
                safe_message=str(error),
            )
        except Exception:
            self._finish_operation(
                operation_id,
                state="failed",
                progress=None,
                safe_message=(
                    "Model download failed. Check connectivity, permissions, and free "
                    "disk space, then retry"
                ),
            )
        finally:
            if stage_path is not None:
                self._remove_path(stage_path)
            with self._lock:
                if self._active_downloads.get(model.model_id) == operation_id:
                    self._active_downloads.pop(model.model_id, None)

    def _promote_stage(self, stage_path: Path, model_path: Path) -> None:
        backup_path: Path | None = None
        if model_path.exists() or model_path.is_symlink():
            self._checked_model_path(model_path.name, path=model_path)
            backup_path = model_path.parent / f".backup-{uuid.uuid4().hex}"
            os.replace(model_path, backup_path)
        try:
            os.replace(stage_path, model_path)
        except Exception:
            if backup_path is not None and backup_path.exists():
                os.replace(backup_path, model_path)
            raise
        if backup_path is not None:
            self._remove_path(backup_path)

    def _status_for(self, model: ConfiguredModel) -> ModelStatus:
        operation_id = self._latest_model_operations.get(model.model_id)
        operation = self._operations.get(operation_id) if operation_id else None
        if operation is not None and operation.kind == "download":
            if operation.state == "running":
                return ModelStatus(
                    model_id=model.model_id,
                    display_name=model.display_name,
                    task=model.task,
                    requested_revision=model.requested_revision,
                    availability="downloading",
                    resolved_revision=operation.resolved_revision,
                    progress=operation.progress,
                    safe_message=operation.safe_message,
                )
            if operation.state == "failed":
                return ModelStatus(
                    model_id=model.model_id,
                    display_name=model.display_name,
                    task=model.task,
                    requested_revision=model.requested_revision,
                    availability="failed",
                    resolved_revision=operation.resolved_revision,
                    safe_message=operation.safe_message,
                )

        manifest = self._read_manifest(model)
        if manifest is not None:
            return ModelStatus(
                model_id=model.model_id,
                display_name=model.display_name,
                task=model.task,
                requested_revision=model.requested_revision,
                availability="ready",
                resolved_revision=manifest["resolved_revision"],
            )
        return ModelStatus(
            model_id=model.model_id,
            display_name=model.display_name,
            task=model.task,
            requested_revision=model.requested_revision,
            availability="missing",
        )

    def _read_manifest(self, model: ConfiguredModel) -> dict[str, str | None] | None:
        try:
            model_path = self._checked_model_path(model.model_id)
            manifest_path = model_path / _MANIFEST_NAME
            with manifest_path.open(encoding="utf-8") as manifest_file:
                manifest = json.load(manifest_file)
        except (OSError, ValueError, ModelManagerError):
            return None

        if not isinstance(manifest, dict):
            return None
        model_id = manifest.get("model_id")
        requested_revision = manifest.get("requested_revision")
        resolved_revision = manifest.get("resolved_revision")
        completed_at = manifest.get("completed_at")
        if (
            model_id != model.model_id
            or requested_revision != model.requested_revision
            or not isinstance(resolved_revision, str)
            or _REVISION_PATTERN.fullmatch(resolved_revision) is None
            or not isinstance(completed_at, str)
        ):
            return None
        return {
            "model_id": model_id,
            "requested_revision": requested_revision,
            "resolved_revision": resolved_revision,
            "completed_at": completed_at,
        }

    def _checked_model_path(self, model_id: str, *, path: Path | None = None) -> Path:
        candidate = self.model_directory(model_id) if path is None else path
        model_root = self.settings.model_dir.resolve()
        resolved_candidate = candidate.resolve()
        try:
            resolved_candidate.relative_to(model_root)
        except ValueError:
            raise ModelManagerError(
                "Model path is outside the configured model directory"
            ) from None
        return candidate

    def _remove_path(self, path: Path) -> None:
        checked_path = self._checked_model_path(path.name, path=path)
        if checked_path.is_dir():
            shutil.rmtree(checked_path)
        elif checked_path.exists() or checked_path.is_symlink():
            checked_path.unlink()

    def _get_model(self, model_id: str) -> ConfiguredModel:
        model = self._catalog.get(model_id)
        if model is None:
            raise ModelManagerError(
                "The requested model is not in the configured catalog"
            )
        return model

    def _new_operation(
        self,
        kind: OperationKind,
        model: ConfiguredModel | None,
        *,
        state: OperationState,
        progress: float | None,
        safe_message: str,
    ) -> ModelOperation:
        record = _OperationRecord(
            operation_id=uuid.uuid4().hex,
            kind=kind,
            model_id=model.model_id if model is not None else None,
            requested_revision=(
                model.requested_revision if model is not None else None
            ),
            resolved_revision=None,
            state=state,
            progress=progress,
            safe_message=safe_message,
        )
        with self._lock:
            self._operations[record.operation_id] = record
            if model is not None:
                self._latest_model_operations[model.model_id] = record.operation_id
        if state == "running":
            log_event(
                _LOGGER,
                _OPERATION_EVENTS[kind],
                outcome="started",
                model_id=record.model_id,
            )
        elif state == "succeeded":
            log_event(
                _LOGGER,
                _OPERATION_EVENTS[kind],
                outcome="success",
                model_id=record.model_id,
            )
        elif state == "failed":
            log_event(
                _LOGGER,
                _OPERATION_EVENTS[kind],
                outcome="failure",
                model_id=record.model_id,
            )
        return record.snapshot()

    def _update_operation(
        self,
        operation_id: str,
        *,
        resolved_revision: str | None = None,
        progress: float | None,
        safe_message: str,
    ) -> None:
        with self._lock:
            record = self._operations[operation_id]
            if resolved_revision is not None:
                record.resolved_revision = resolved_revision
            record.progress = progress
            record.safe_message = safe_message

    def _report_download_progress(
        self, operation_id: str, transfer_progress: float
    ) -> None:
        bounded_progress = min(max(transfer_progress, 0.0), 1.0)
        operation_progress = 0.2 + 0.4 * bounded_progress
        with self._lock:
            record = self._operations[operation_id]
            if record.state != "running":
                return
            if record.progress is not None:
                operation_progress = max(operation_progress, record.progress)
            record.progress = operation_progress
            record.safe_message = (
                f"Downloading model snapshot ({int(bounded_progress * 100)}%)"
            )

    def _finish_operation(
        self,
        operation_id: str,
        *,
        state: OperationState,
        progress: float | None,
        safe_message: str,
    ) -> ModelOperation:
        with self._lock:
            record = self._operations[operation_id]
            record.state = state
            record.progress = progress
            record.safe_message = safe_message
            if state == "succeeded":
                log_event(
                    _LOGGER,
                    _OPERATION_EVENTS[record.kind],
                    outcome="success",
                    model_id=record.model_id,
                )
            elif state == "failed":
                log_event(
                    _LOGGER,
                    _OPERATION_EVENTS[record.kind],
                    outcome="failure",
                    model_id=record.model_id,
                )
            return record.snapshot()
