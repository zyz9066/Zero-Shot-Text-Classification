from __future__ import annotations

import math
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from app.config.label_catalog import LabelSet
from app.services.inference import InferenceError, infer_local_model
from app.services.label_manager import LabelManager, LabelManagerError
from app.services.model_manager import ModelManager, ModelManagerError, ModelStatus
from app.services.prediction_store import (
    PredictionStorageConfigurationError,
    PredictionStore,
    PredictionWriteError,
)
from app.utils.logging_config import configure_logging, log_event

_LOGGER = configure_logging("classification")
InferenceCallable = Callable[
    [str, tuple[str, ...], str, str, str], tuple[tuple[str, float], ...]
]
OutcomeStatus = Literal["saved", "failed", "indeterminate"]


class ClassificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RequestIdentity:
    text: str
    model_id: str
    model_revision: str | None
    label_set_id: str
    label_set_revision: int


@dataclass(frozen=True)
class ModelSnapshot:
    model_id: str
    display_name: str
    revision: str | None
    artifact_path: str


@dataclass(frozen=True)
class CandidateLabelSnapshot:
    set_id: str
    revision: int
    name: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class ClassificationRequest:
    request_id: str
    text: str
    model: ModelSnapshot
    label_set: CandidateLabelSnapshot

    @property
    def identity(self) -> RequestIdentity:
        return RequestIdentity(
            self.text,
            self.model.model_id,
            self.model.revision,
            self.label_set.set_id,
            self.label_set.revision,
        )


@dataclass(frozen=True)
class RankedResult:
    label: str
    score: float


@dataclass(frozen=True)
class PredictionResult:
    request_id: str
    input_text: str
    predicted_class: str
    predicted_score: float
    candidate_labels: tuple[str, ...]
    ranked_results: tuple[RankedResult, ...]
    model_name: str
    model_identifier: str
    model_revision: str | None
    timestamp: str
    application_version: str

    def to_record(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "input_text": self.input_text,
            "predicted_class": self.predicted_class,
            "predicted_score": self.predicted_score,
            "candidate_labels": list(self.candidate_labels),
            "ranked_results": [
                {"label": item.label, "score": item.score}
                for item in self.ranked_results
            ],
            "model_name": self.model_name,
            "model_identifier": self.model_identifier,
            "model_revision": self.model_revision,
            "timestamp": self.timestamp,
            "application_version": self.application_version,
        }


@dataclass(frozen=True)
class ClassificationOutcome:
    status: OutcomeStatus
    request: ClassificationRequest
    message: str
    result: PredictionResult | None = None


@dataclass(frozen=True)
class SubmissionStatus:
    state: Literal["idle", "in_progress", "blocked", "saved", "failed", "indeterminate"]
    request_id: str | None
    message: str
    outcome: ClassificationOutcome | None = None


class ClassificationService:
    def __init__(
        self,
        model_manager: ModelManager,
        label_manager: LabelManager,
        prediction_store: PredictionStore,
        *,
        application_version: str,
        infer: InferenceCallable = infer_local_model,
    ) -> None:
        self.model_manager = model_manager
        self.label_manager = label_manager
        self.prediction_store = prediction_store
        self.application_version = application_version
        self._infer = infer

    def prepare_request(
        self, text: str, model_id: str, label_set_id: str
    ) -> ClassificationRequest:
        if not isinstance(text, str) or not text.strip():
            raise ClassificationError("Enter non-blank text before classifying.")

        try:
            with self.model_manager.model_use_guard(model_id) as status:
                self._require_ready(status)
                catalog = self.label_manager.list_sets()
                selected = next(
                    (item for item in catalog.sets if item.id == label_set_id), None
                )
                if selected is None or not self._valid_labels(selected):
                    raise ClassificationError(
                        "Select a valid saved candidate-label set before classifying."
                    )
                try:
                    artifact_path = str(
                        self.model_manager.model_directory(model_id).resolve()
                    )
                except (OSError, RuntimeError, ValueError):
                    raise ClassificationError(
                        "The selected local model path is unavailable. Check Model "
                        "Management and refresh the page."
                    ) from None
                return ClassificationRequest(
                    request_id=str(uuid4()),
                    text=text,
                    model=ModelSnapshot(
                        status.model_id,
                        status.display_name,
                        status.resolved_revision,
                        artifact_path,
                    ),
                    label_set=self._label_snapshot(selected),
                )
        except ModelManagerError:
            raise ClassificationError(
                "The selected model is unavailable or busy. Refresh the model list "
                "and try again."
            ) from None
        except LabelManagerError:
            raise ClassificationError(
                "The candidate-label catalog is unavailable or invalid. Repair it "
                "before classifying."
            ) from None

    def identity_for(
        self, text: str, model_id: str, label_set_id: str
    ) -> RequestIdentity:
        try:
            status = self.model_manager.get_status(model_id)
            revision = status.resolved_revision
        except ModelManagerError:
            revision = None
        try:
            catalog = self.label_manager.list_sets()
            selected = next(
                (item for item in catalog.sets if item.id == label_set_id), None
            )
            revision_number = selected.revision if selected is not None else -1
        except LabelManagerError:
            revision_number = -1
        return RequestIdentity(text, model_id, revision, label_set_id, revision_number)

    def execute(self, request: ClassificationRequest) -> ClassificationOutcome:
        try:
            with self.model_manager.model_use_guard(request.model.model_id) as status:
                self._require_snapshot(status, request.model)
                ranked = self._infer(
                    request.text,
                    request.label_set.labels,
                    request.model.artifact_path,
                    request.model.model_id,
                    request.model.revision or "",
                )
                self._validate_ranking(request.label_set.labels, ranked)
                final_status = self.model_manager.get_status(request.model.model_id)
                self._require_snapshot(final_status, request.model)
                prediction = self._make_result(request, ranked)
                with self.label_manager.finalize_set(request.label_set.set_id):
                    self.prediction_store.save(prediction.to_record())
            log_event(
                _LOGGER,
                "classification.request",
                outcome="success",
                request_id=request.request_id,
                model_id=request.model.model_id,
                label_set_id=request.label_set.set_id,
            )
            return ClassificationOutcome(
                "saved",
                request,
                "Prediction saved to MinIO.",
                prediction,
            )
        except PredictionWriteError as error:
            log_event(
                _LOGGER,
                "classification.request",
                outcome=error.kind,
                request_id=request.request_id,
                model_id=request.model.model_id,
                label_set_id=request.label_set.set_id,
            )
            return ClassificationOutcome(error.kind, request, str(error))
        except InferenceError as error:
            log_event(
                _LOGGER,
                "classification.request",
                outcome="failure",
                request_id=request.request_id,
                model_id=request.model.model_id,
                label_set_id=request.label_set.set_id,
            )
            return ClassificationOutcome("failed", request, str(error))
        except (ClassificationError, ModelManagerError) as error:
            log_event(
                _LOGGER,
                "classification.request",
                outcome="failure",
                request_id=request.request_id,
                model_id=request.model.model_id,
                label_set_id=request.label_set.set_id,
            )
            return ClassificationOutcome(
                "failed",
                request,
                str(error),
            )
        except LabelManagerError:
            log_event(
                _LOGGER,
                "classification.request",
                outcome="failure",
                request_id=request.request_id,
                model_id=request.model.model_id,
                label_set_id=request.label_set.set_id,
            )
            return ClassificationOutcome(
                "failed",
                request,
                "The selected label set is no longer available or valid. Select it "
                "again before submitting.",
            )
        except PredictionStorageConfigurationError as error:
            log_event(
                _LOGGER,
                "classification.request",
                outcome="failure",
                request_id=request.request_id,
                model_id=request.model.model_id,
                label_set_id=request.label_set.set_id,
            )
            return ClassificationOutcome(
                "failed",
                request,
                str(error),
            )
        except Exception:
            log_event(
                _LOGGER,
                "classification.request",
                outcome="failure",
                request_id=request.request_id,
                model_id=request.model.model_id,
                label_set_id=request.label_set.set_id,
            )
            return ClassificationOutcome(
                "failed",
                request,
                "Classification could not be completed. Check service availability "
                "and try again.",
            )

    def _require_ready(self, status: ModelStatus) -> None:
        if status.availability != "ready":
            raise ClassificationError("Select a ready local model before classifying.")

    def _require_snapshot(self, status: ModelStatus, snapshot: ModelSnapshot) -> None:
        if (
            status.availability != "ready"
            or status.model_id != snapshot.model_id
            or status.resolved_revision != snapshot.revision
        ):
            raise ClassificationError(
                "The selected model changed or became unavailable. Refresh it before "
                "submitting again."
            )

    @staticmethod
    def _valid_labels(item: LabelSet) -> bool:
        return (
            len(item.labels) >= 2
            and all(isinstance(label, str) and label.strip() for label in item.labels)
            and len(set(item.labels)) == len(item.labels)
        )

    @staticmethod
    def _label_snapshot(item: LabelSet) -> CandidateLabelSnapshot:
        return CandidateLabelSnapshot(item.id, item.revision, item.name, item.labels)

    @staticmethod
    def _validate_ranking(
        candidates: tuple[str, ...], ranked: tuple[tuple[str, float], ...]
    ) -> None:
        if len(ranked) != len(candidates):
            raise InferenceError("The selected model returned malformed scores.")
        labels: list[str] = []
        scores: list[float] = []
        for label, score in ranked:
            if (
                not isinstance(label, str)
                or not math.isfinite(score)
                or isinstance(score, bool)
            ):
                raise InferenceError("The selected model returned malformed scores.")
            labels.append(label)
            scores.append(score)
        if (
            len(set(labels)) != len(labels)
            or set(labels) != set(candidates)
            or any(
                scores[index] < scores[index + 1] for index in range(len(scores) - 1)
            )
        ):
            raise InferenceError("The selected model returned malformed scores.")

    def _make_result(
        self, request: ClassificationRequest, ranked: tuple[tuple[str, float], ...]
    ) -> PredictionResult:
        if request.model.revision is not None and not request.model.revision:
            raise ClassificationError("The selected model revision is invalid.")
        items = tuple(RankedResult(label, score) for label, score in ranked)
        top = items[0]
        return PredictionResult(
            request_id=request.request_id,
            input_text=request.text,
            predicted_class=top.label,
            predicted_score=top.score,
            candidate_labels=request.label_set.labels,
            ranked_results=items,
            model_name=request.model.display_name,
            model_identifier=request.model.model_id,
            model_revision=request.model.revision,
            timestamp=datetime.now(UTC).isoformat(),
            application_version=self.application_version,
        )


@dataclass
class _ActiveSubmission:
    request: ClassificationRequest
    future: Future[ClassificationOutcome]
    executor: ThreadPoolExecutor


class SessionSubmissionCoordinator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: _ActiveSubmission | None = None
        self._last_outcome: ClassificationOutcome | None = None

    @property
    def active_request_id(self) -> str | None:
        with self._lock:
            self._collect_finished()
            return self._active.request.request_id if self._active else None

    def check(self, identity: RequestIdentity) -> SubmissionStatus:
        with self._lock:
            self._collect_finished()
            if self._active is None:
                return SubmissionStatus("idle", None, "")
            if self._active.request.identity == identity:
                return SubmissionStatus(
                    "in_progress",
                    self._active.request.request_id,
                    "This identical classification is already processing.",
                )
            return SubmissionStatus(
                "blocked",
                self._active.request.request_id,
                "A classification is already processing. Submit this text and "
                "selections after it finishes.",
            )

    def start(
        self, request: ClassificationRequest, service: ClassificationService
    ) -> SubmissionStatus:
        with self._lock:
            self._collect_finished()
            if self._active is not None:
                if self._active.request.identity == request.identity:
                    return SubmissionStatus(
                        "in_progress",
                        self._active.request.request_id,
                        "This identical classification is already processing.",
                    )
                return SubmissionStatus(
                    "blocked",
                    self._active.request.request_id,
                    "A classification is already processing. Submit this text and "
                    "selections after it finishes.",
                )
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(service.execute, request)
            self._active = _ActiveSubmission(request, future, executor)
            return SubmissionStatus(
                "in_progress",
                request.request_id,
                "Classification is processing.",
            )

    def poll(self) -> SubmissionStatus:
        with self._lock:
            self._collect_finished()
            if self._active is not None:
                return SubmissionStatus(
                    "in_progress",
                    self._active.request.request_id,
                    "Classification is processing.",
                )
            if self._last_outcome is not None:
                return SubmissionStatus(
                    self._last_outcome.status,
                    self._last_outcome.request.request_id,
                    self._last_outcome.message,
                    self._last_outcome,
                )
            return SubmissionStatus("idle", None, "")

    def wait_for_completion(self, timeout: float) -> ClassificationOutcome | None:
        with self._lock:
            active = self._active
        if active is None:
            return self._last_outcome
        try:
            active.future.result(timeout=timeout)
        except FutureTimeout:
            return None
        with self._lock:
            self._collect_finished()
            return self._last_outcome

    def _collect_finished(self) -> None:
        if self._active is None or not self._active.future.done():
            return
        active = self._active
        self._last_outcome = active.future.result()
        self._active = None
        active.executor.shutdown(wait=False)
