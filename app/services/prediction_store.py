from __future__ import annotations

import json
import math
import re
import ssl
from collections.abc import Mapping
from datetime import UTC, datetime
from io import BytesIO
from typing import Literal, Protocol, cast
from uuid import UUID

import streamlit as st
import urllib3
from minio import Minio
from minio.error import S3Error

from app.config.loader import load_minio_settings
from app.config.settings import MinIOServiceSettings
from app.utils.logging_config import configure_logging, log_event

_LOGGER = configure_logging("prediction_storage")
_REQUEST_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_RECORD_FIELDS = {
    "request_id",
    "input_text",
    "predicted_class",
    "predicted_score",
    "candidate_labels",
    "ranked_results",
    "model_name",
    "model_identifier",
    "model_revision",
    "timestamp",
    "application_version",
}


class PredictionWriteError(RuntimeError):
    def __init__(
        self, message: str, kind: Literal["failed", "indeterminate"], request_id: str
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.request_id = request_id


class PredictionStorageConfigurationError(RuntimeError):
    pass


class MinioClient(Protocol):
    def bucket_exists(self, bucket_name: str) -> bool: ...

    def make_bucket(self, bucket_name: str) -> object: ...

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
    ) -> object: ...


def _cached_minio_client(
    endpoint: str,
    secure: bool,
    access_key: str,
    secret_key: str,
) -> MinioClient:
    http_client = urllib3.PoolManager(
        cert_reqs=ssl.CERT_REQUIRED,
        retries=False,
        timeout=urllib3.Timeout(connect=5.0, read=30.0),
    )
    try:
        return cast(
            MinioClient,
            Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
                http_client=http_client,
            ),
        )
    except Exception:
        http_client.clear()
        raise PredictionStorageConfigurationError(
            "Prediction storage configuration is invalid. Check the MinIO endpoint "
            "and credentials."
        ) from None


_cached_minio_client = st.cache_resource(show_spinner=False)(_cached_minio_client)


def create_minio_client(settings: MinIOServiceSettings) -> MinioClient:
    return _cached_minio_client(
        settings.endpoint,
        settings.secure,
        settings.access_key,
        settings.secret_key,
    )


def get_prediction_store() -> PredictionStore:
    return PredictionStore()


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_record(record: Mapping[str, object]) -> tuple[str, bytes]:
    if set(record) != _RECORD_FIELDS:
        raise ValueError("record fields")
    request_id = record.get("request_id")
    if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
        raise ValueError("request identifier")
    UUID(request_id)

    input_text = record.get("input_text")
    predicted_class = record.get("predicted_class")
    predicted_score = record.get("predicted_score")
    candidate_labels = record.get("candidate_labels")
    ranked_results = record.get("ranked_results")
    model_name = record.get("model_name")
    model_identifier = record.get("model_identifier")
    model_revision = record.get("model_revision")
    timestamp = record.get("timestamp")
    application_version = record.get("application_version")

    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("input text")
    if (
        not isinstance(predicted_class, str)
        or not predicted_class
        or not _finite_number(predicted_score)
    ):
        raise ValueError("prediction")
    if (
        not isinstance(candidate_labels, list)
        or len(candidate_labels) < 2
        or any(
            not isinstance(label, str) or not label.strip()
            for label in candidate_labels
        )
        or len(set(candidate_labels)) != len(candidate_labels)
    ):
        raise ValueError("candidate labels")
    if not isinstance(ranked_results, list) or len(ranked_results) != len(
        candidate_labels
    ):
        raise ValueError("ranked results")

    ranked_labels: list[str] = []
    ranked_scores: list[float] = []
    for result in ranked_results:
        if (
            not isinstance(result, Mapping)
            or set(result) != {"label", "score"}
            or not isinstance(result.get("label"), str)
            or not _finite_number(result.get("score"))
        ):
            raise ValueError("ranked result")
        ranked_labels.append(cast(str, result["label"]))
        ranked_scores.append(float(cast(int | float, result["score"])))
    if (
        set(ranked_labels) != set(candidate_labels)
        or len(set(ranked_labels)) != len(ranked_labels)
        or any(
            ranked_scores[index] < ranked_scores[index + 1]
            for index in range(len(ranked_scores) - 1)
        )
        or predicted_class != ranked_labels[0]
        or float(cast(int | float, predicted_score)) != ranked_scores[0]
    ):
        raise ValueError("rank consistency")

    if (
        not isinstance(model_name, str)
        or not model_name
        or not isinstance(model_identifier, str)
        or not model_identifier
    ):
        raise ValueError("model provenance")
    if model_revision is not None and (
        not isinstance(model_revision, str)
        or _REVISION.fullmatch(model_revision) is None
    ):
        raise ValueError("model revision")
    if (
        not isinstance(timestamp, str)
        or not isinstance(application_version, str)
        or not application_version.strip()
    ):
        raise ValueError("timestamp or application version")
    parsed_timestamp = datetime.fromisoformat(timestamp)
    if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() != UTC.utcoffset(
        parsed_timestamp
    ):
        raise ValueError("timestamp timezone")

    payload = json.dumps(
        dict(record),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return request_id, payload


def _status_code(error: Exception) -> int | None:
    direct_status = getattr(error, "status_code", None)
    if isinstance(direct_status, int):
        return direct_status
    response = getattr(error, "response", None)
    status = getattr(response, "status", None)
    return status if isinstance(status, int) else None


class PredictionStore:
    def __init__(
        self,
        settings: MinIOServiceSettings | None = None,
        *,
        client: MinioClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client

    def _ensure_bucket(
        self, settings: MinIOServiceSettings, client: MinioClient, request_id: str
    ) -> None:
        try:
            if client.bucket_exists(settings.bucket):
                return
            try:
                client.make_bucket(settings.bucket)
            except S3Error:
                if not client.bucket_exists(settings.bucket):
                    raise
            if not client.bucket_exists(settings.bucket):
                raise RuntimeError("bucket unavailable")
        except Exception:
            log_event(
                _LOGGER,
                "prediction_storage.bucket",
                outcome="failure",
                request_id=request_id,
                bucket=settings.bucket,
            )
            raise PredictionWriteError(
                "The configured prediction bucket is unavailable or cannot be "
                "created. Configure a compatible bucket and check permissions.",
                "failed",
                request_id,
            ) from None

    def save(self, record: Mapping[str, object]) -> None:
        try:
            request_id, payload = _validate_record(record)
        except (TypeError, ValueError, UnicodeError, OverflowError):
            raise PredictionWriteError(
                "The prediction record is invalid and was not written.",
                "failed",
                _record_request_id(record),
            ) from None

        try:
            settings = self.settings or load_minio_settings()
            client = self._client or create_minio_client(settings)
        except Exception:
            raise PredictionStorageConfigurationError(
                "Prediction storage configuration is unavailable. Check MinIO "
                "settings and credentials."
            ) from None

        self._ensure_bucket(settings, client, request_id)
        key = f"predictions/{request_id}.json"
        log_event(
            _LOGGER,
            "prediction_storage.write",
            outcome="started",
            request_id=request_id,
            bucket=settings.bucket,
        )
        try:
            client.put_object(
                settings.bucket,
                key,
                BytesIO(payload),
                len(payload),
                content_type="application/json",
            )
        except Exception as error:
            status = _status_code(error)
            kind: Literal["failed", "indeterminate"] = (
                "failed"
                if status is not None and 400 <= status < 500
                else "indeterminate"
            )
            message = (
                "Prediction storage rejected the write. Check bucket access and "
                "configuration; the record was not saved."
                if kind == "failed"
                else "Prediction storage did not confirm the write. Ask an authorized "
                "operator to inspect this request before retrying."
            )
            log_event(
                _LOGGER,
                "prediction_storage.write",
                outcome=kind,
                request_id=request_id,
                bucket=settings.bucket,
            )
            raise PredictionWriteError(message, kind, request_id) from None

        log_event(
            _LOGGER,
            "prediction_storage.write",
            outcome="success",
            request_id=request_id,
            bucket=settings.bucket,
        )


def _record_request_id(record: Mapping[str, object]) -> str:
    value = record.get("request_id")
    if isinstance(value, str) and _REQUEST_ID.fullmatch(value) is not None:
        return value
    return "00000000-0000-4000-8000-000000000000"
