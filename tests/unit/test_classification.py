from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from app.config.label_catalog import LabelSet
from app.services.classification import (
    ClassificationError,
    ClassificationService,
    SessionSubmissionCoordinator,
)
from app.services.label_manager import CatalogSnapshot, LabelManager, LabelManagerError
from app.services.model_manager import ModelStatus
from app.services.prediction_store import (
    PredictionStorageConfigurationError,
    PredictionWriteError,
)

MODEL_ID = "org/model"
MODEL_REVISION = "a" * 40
LABEL_ID = "e318e2dd-7562-4c75-84b9-c5ce29b913af"


class FakeModelManager:
    def __init__(
        self,
        status: ModelStatus | None = None,
        statuses: list[ModelStatus] | None = None,
    ) -> None:
        self.status = status or ModelStatus(
            MODEL_ID,
            "Test Model",
            "zero-shot-classification",
            None,
            "ready",
            MODEL_REVISION,
        )
        self.statuses = list(statuses) if statuses is not None else []
        self.calls = 0

    @contextmanager
    def model_use_guard(self, model_id: str) -> Iterator[ModelStatus]:
        assert model_id == MODEL_ID
        self.calls += 1
        yield self.statuses.pop(0) if self.statuses else self.status

    def get_status(self, model_id: str) -> ModelStatus:
        assert model_id == MODEL_ID
        return self.status

    def model_directory(self, model_id: str) -> Path:
        assert model_id == MODEL_ID
        return Path("models/test")


class FakeLabelManager:
    def __init__(self) -> None:
        self.saved_set = LabelSet(LABEL_ID, 1, "Topics", ("sports", "news"))
        self.final_set: LabelSet | None = None
        self.fail_finalization: LabelManagerError | None = None
        self.finalizing = threading.Event()
        self.release_finalization = threading.Event()

    def list_sets(self) -> CatalogSnapshot:
        return CatalogSnapshot((self.saved_set,))

    @contextmanager
    def finalize_set(self, identifier: str) -> Iterator[LabelSet]:
        if self.fail_finalization is not None:
            raise self.fail_finalization
        assert identifier == LABEL_ID
        self.finalizing.set()
        if self.final_set is not None:
            yield self.final_set
        else:
            yield self.saved_set


class FakeStore:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []
        self.error: (
            PredictionWriteError | PredictionStorageConfigurationError | None
        ) = None

    def save(self, record: dict[str, object]) -> None:
        if self.error is not None:
            raise self.error
        self.records.append(record)


def make_service(
    *,
    model_manager: FakeModelManager | None = None,
    label_manager: FakeLabelManager | None = None,
    store: FakeStore | None = None,
    infer=None,
) -> tuple[ClassificationService, FakeLabelManager, FakeStore]:
    labels = label_manager or FakeLabelManager()
    storage = store or FakeStore()
    service = ClassificationService(
        model_manager or FakeModelManager(),
        labels,
        storage,
        application_version="0.1.0",
        infer=infer
        or (
            lambda _text, candidates, *_args: tuple(
                (label, score)
                for label, score in zip(candidates, (0.8, 0.2), strict=True)
            )
        ),
    )
    return service, labels, storage


def test_validation_rejects_blank_and_unavailable_dependencies() -> None:
    service, labels, _store = make_service()

    with pytest.raises(ClassificationError, match="text"):
        service.prepare_request("  \n", MODEL_ID, LABEL_ID)

    labels.saved_set = LabelSet(LABEL_ID, 1, "Invalid", ("only-one",))
    with pytest.raises(ClassificationError, match="valid"):
        service.prepare_request("valid input", MODEL_ID, LABEL_ID)


def test_success_persists_snapshot_and_returns_only_after_save() -> None:
    service, _labels, store = make_service()
    request = service.prepare_request("exact submitted text", MODEL_ID, LABEL_ID)

    outcome = service.execute(request)

    assert outcome.status == "saved"
    assert outcome.result is not None
    assert outcome.result.predicted_class == "sports"
    assert [item.label for item in outcome.result.ranked_results] == ["sports", "news"]
    assert len(store.records) == 1
    assert store.records[0]["input_text"] == "exact submitted text"
    assert store.records[0]["request_id"] == request.request_id


def test_storage_configuration_detail_reaches_outcome() -> None:
    service, _labels, store = make_service()
    request = service.prepare_request("sample text", MODEL_ID, LABEL_ID)
    message = "MINIO_SECRET_KEY: must be a non-empty string"
    store.error = PredictionStorageConfigurationError(message)

    outcome = service.execute(request)

    assert outcome.status == "failed"
    assert outcome.message == message
    assert outcome.result is None
    assert not store.records


def test_valid_label_edit_does_not_change_captured_request_labels() -> None:
    service, labels, store = make_service()
    request = service.prepare_request("text", MODEL_ID, LABEL_ID)
    labels.final_set = LabelSet(LABEL_ID, 2, "Topics", ("updated", "labels"))

    outcome = service.execute(request)

    assert outcome.status == "saved"
    assert outcome.result is not None
    assert outcome.result.candidate_labels == ("sports", "news")
    assert store.records[0]["candidate_labels"] == ["sports", "news"]


def test_model_change_and_removed_label_prevent_success() -> None:
    missing = ModelStatus(
        MODEL_ID, "Test Model", "zero-shot-classification", None, "missing"
    )
    service, _labels, store = make_service(
        model_manager=FakeModelManager(
            statuses=[
                FakeModelManager().status,
                missing,
            ]
        )
    )
    request = service.prepare_request("text", MODEL_ID, LABEL_ID)
    outcome = service.execute(request)
    assert outcome.status == "failed"
    assert not store.records

    service, labels, store = make_service()
    request = service.prepare_request("text", MODEL_ID, LABEL_ID)
    labels.fail_finalization = LabelManagerError(
        "The selected label set is no longer available.", "unavailable"
    )
    outcome = service.execute(request)
    assert outcome.status == "failed"
    assert not store.records


def test_label_edit_during_inference_uses_captured_snapshot(
    tmp_path: Path,
) -> None:
    labels = LabelManager(tmp_path / "labels.yaml", timeout=0.2)
    saved = labels.create("Topics", ["sports", "news"])
    store = FakeStore()
    started = threading.Event()
    release = threading.Event()

    def slow_inference(_text: str, candidates: tuple[str, ...], *_args):
        started.set()
        assert release.wait(2)
        return ((candidates[0], 0.8), (candidates[1], 0.2))

    service = ClassificationService(
        FakeModelManager(),
        labels,
        store,
        application_version="0.1.0",
        infer=slow_inference,
    )
    request = service.prepare_request("text", MODEL_ID, saved.id)
    outcomes = []
    worker = threading.Thread(target=lambda: outcomes.append(service.execute(request)))
    worker.start()
    assert started.wait(2)
    labels.update(saved.id, saved.revision, "Topics", ["updated", "labels"])
    release.set()
    worker.join(2)

    assert not worker.is_alive()
    assert outcomes[0].status == "saved"
    assert outcomes[0].result.candidate_labels == ("sports", "news")
    assert store.records[0]["candidate_labels"] == ["sports", "news"]


def test_removed_label_set_during_inference_prevents_success(
    tmp_path: Path,
) -> None:
    labels = LabelManager(tmp_path / "labels.yaml", timeout=0.2)
    saved = labels.create("Topics", ["sports", "news"])
    store = FakeStore()
    started = threading.Event()
    release = threading.Event()

    def slow_inference(_text: str, candidates: tuple[str, ...], *_args):
        started.set()
        assert release.wait(2)
        return ((candidates[0], 0.8), (candidates[1], 0.2))

    service = ClassificationService(
        FakeModelManager(),
        labels,
        store,
        application_version="0.1.0",
        infer=slow_inference,
    )
    request = service.prepare_request("text", MODEL_ID, saved.id)
    outcomes = []
    worker = threading.Thread(target=lambda: outcomes.append(service.execute(request)))
    worker.start()
    assert started.wait(2)
    labels.remove(saved.id, saved.revision, confirmed=True)
    release.set()
    worker.join(2)

    assert not worker.is_alive()
    assert outcomes[0].status == "failed"
    assert not store.records


def test_model_guard_wraps_label_finalization_and_storage() -> None:
    events: list[str] = []

    class OrderedModelManager(FakeModelManager):
        @contextmanager
        def model_use_guard(self, model_id: str) -> Iterator[ModelStatus]:
            events.append("model-enter")
            try:
                yield self.status
            finally:
                events.append("model-exit")

    class OrderedLabelManager(FakeLabelManager):
        @contextmanager
        def finalize_set(self, identifier: str) -> Iterator[LabelSet]:
            events.append("labels-enter")
            try:
                yield self.saved_set
            finally:
                events.append("labels-exit")

    class OrderedStore(FakeStore):
        def save(self, record: dict[str, object]) -> None:
            events.append("storage")
            super().save(record)

    labels = OrderedLabelManager()
    service = ClassificationService(
        OrderedModelManager(),
        labels,
        OrderedStore(),
        application_version="0.1.0",
        infer=lambda _text, candidates, *_args: tuple(
            (label, score) for label, score in zip(candidates, (0.8, 0.2), strict=True)
        ),
    )
    request = service.prepare_request("text", MODEL_ID, LABEL_ID)
    events.clear()

    outcome = service.execute(request)

    assert outcome.status == "saved"
    assert events == [
        "model-enter",
        "labels-enter",
        "storage",
        "labels-exit",
        "model-exit",
    ]


@pytest.mark.parametrize(
    ("kind", "status"),
    [("failed", "failed"), ("indeterminate", "indeterminate")],
)
def test_storage_outcomes_are_not_reported_as_success(kind: str, status: str) -> None:
    service, _labels, store = make_service()
    store.error = PredictionWriteError(
        "Storage outcome is uncertain.", kind, request_id="request-id"
    )
    request = service.prepare_request("text", MODEL_ID, LABEL_ID)

    outcome = service.execute(request)

    assert outcome.status == status
    assert outcome.result is None
    assert outcome.request.text == "text"
    assert not store.records


def test_session_coordinator_reuses_exact_active_submission_and_blocks_changes() -> (
    None
):
    started = threading.Event()
    release = threading.Event()

    def slow_inference(_text: str, candidates: tuple[str, ...], *_args):
        started.set()
        assert release.wait(2)
        return tuple(
            (label, score) for label, score in zip(candidates, (0.8, 0.2), strict=True)
        )

    service, _labels, store = make_service(infer=slow_inference)
    request = service.prepare_request("text", MODEL_ID, LABEL_ID)
    coordinator = SessionSubmissionCoordinator()
    another_session = SessionSubmissionCoordinator()
    first = coordinator.start(request, service)
    assert started.wait(2)

    repeated = coordinator.check(request.identity)
    changed = coordinator.check(replace(request.identity, text="changed text"))
    changed_selections = tuple(
        coordinator.check(replace(request.identity, **values))
        for values in (
            {"model_id": "org/other"},
            {"model_revision": "b" * 40},
            {"label_set_id": "other-labels"},
            {"label_set_revision": request.identity.label_set_revision + 1},
        )
    )

    assert first.state == "in_progress"
    assert repeated.state == "in_progress"
    assert repeated.request_id == request.request_id
    assert changed.state == "blocked"
    assert all(status.state == "blocked" for status in changed_selections)
    assert another_session.check(request.identity).state == "idle"
    assert coordinator.active_request_id == request.request_id
    release.set()
    assert coordinator.wait_for_completion(timeout=2).status == "saved"
    assert len(store.records) == 1

    next_request = service.prepare_request("text", MODEL_ID, LABEL_ID)
    assert next_request.request_id != request.request_id
    assert coordinator.start(next_request, service).state == "in_progress"
    assert coordinator.wait_for_completion(timeout=2).status == "saved"
    assert len(store.records) == 2
