from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config.loader import load_minio_settings
from app.config.settings import MinIOServiceSettings
from app.services.prediction_store import (
    PredictionStorageConfigurationError,
    PredictionStore,
    PredictionWriteError,
)


def make_record(
    request_id: str = "e318e2dd-7562-4c75-84b9-c5ce29b913af",
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "input_text": "A test input",
        "predicted_class": "sports",
        "predicted_score": 0.8,
        "candidate_labels": ["sports", "news"],
        "ranked_results": [
            {"label": "sports", "score": 0.8},
            {"label": "news", "score": 0.2},
        ],
        "model_name": "Test Model",
        "model_identifier": "org/model",
        "model_revision": "a" * 40,
        "timestamp": "2026-11-14T20:00:00+00:00",
        "application_version": "0.1.0",
    }


class FakeClient:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.created: list[str] = []
        self.objects: dict[tuple[str, str], bytes] = {}
        self.put_calls = 0
        self.put_error: Exception | None = None
        self.make_bucket_error: Exception | None = None
        self.write_before_error = False

    def bucket_exists(self, bucket: str) -> bool:
        return bucket in self.buckets

    def make_bucket(self, bucket: str) -> None:
        self.created.append(bucket)
        if self.make_bucket_error is not None:
            raise self.make_bucket_error
        self.buckets.add(bucket)

    def put_object(
        self,
        bucket: str,
        key: str,
        data: io.BytesIO,
        length: int,
        content_type: str,
    ) -> object:
        self.put_calls += 1
        if self.put_error is not None and not self.write_before_error:
            raise self.put_error
        body = data.read()
        assert length == len(body)
        assert content_type == "application/json"
        self.objects[(bucket, key)] = body
        if self.put_error is not None:
            raise self.put_error
        return SimpleNamespace(etag="confirmed")


class FakeHttpError(RuntimeError):
    status_code = 403


def make_store(client: FakeClient, bucket: str = "test-bucket") -> PredictionStore:
    settings = MinIOServiceSettings(
        endpoint="localhost:9000",
        secure=False,
        access_key="access",
        secret_key="secret",
        bucket=bucket,
    )
    return PredictionStore(settings, client=client)


def test_writes_complete_record_to_exact_request_key_and_creates_bucket() -> None:
    client = FakeClient()
    store = make_store(client)
    record = make_record()

    store.save(record)

    key = "predictions/e318e2dd-7562-4c75-84b9-c5ce29b913af.json"
    saved = json.loads(client.objects[("test-bucket", key)])
    assert client.created == ["test-bucket"]
    assert client.put_calls == 1
    assert saved == record


def test_existing_bucket_is_used_without_creation() -> None:
    client = FakeClient()
    client.buckets.add("test-bucket")

    make_store(client).save(make_record())

    assert client.created == []
    assert client.put_calls == 1


def test_missing_credentials_identifies_setting_without_exposing_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import app.services.prediction_store as storage

    config_path = tmp_path / "app.yaml"
    config_path.write_text("minio:\n  bucket: test-bucket\n", encoding="utf-8")
    environment = {
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_SECURE": "false",
        "MINIO_ACCESS_KEY": "private-access-key",
    }
    monkeypatch.setattr(
        storage,
        "load_minio_settings",
        lambda: load_minio_settings(config_path, environment),
    )
    client = FakeClient()

    with pytest.raises(PredictionStorageConfigurationError) as error:
        PredictionStore(client=client).save(make_record())

    assert "MINIO_SECRET_KEY" in str(error.value)
    assert "restart" in str(error.value)
    assert "private-access-key" not in str(error.value)
    assert str(config_path) not in str(error.value)
    assert client.put_calls == 0


def test_rejects_non_finite_scores_before_storage() -> None:
    client = FakeClient()
    record = make_record()
    record["predicted_score"] = float("nan")

    with pytest.raises(PredictionWriteError) as error:
        make_store(client).save(record)

    assert error.value.kind == "failed"
    assert client.put_calls == 0


def test_authoritative_rejection_is_confirmed_failure() -> None:
    client = FakeClient()
    client.put_error = FakeHttpError("private response")

    with pytest.raises(PredictionWriteError) as error:
        make_store(client).save(make_record())

    assert error.value.kind == "failed"
    assert client.put_calls == 1
    assert "private" not in str(error.value)


def test_timeout_is_indeterminate_and_never_automatically_retried() -> None:
    client = FakeClient()
    client.put_error = TimeoutError("late write")

    with pytest.raises(PredictionWriteError) as error:
        make_store(client).save(make_record())

    assert error.value.kind == "indeterminate"
    assert client.put_calls == 1


def test_lost_acknowledgement_after_late_write_is_indeterminate() -> None:
    client = FakeClient()
    client.put_error = TimeoutError("late write")
    client.write_before_error = True

    with pytest.raises(PredictionWriteError) as error:
        make_store(client).save(make_record())

    assert error.value.kind == "indeterminate"
    assert client.put_calls == 1
    assert len(client.objects) == 1


def test_default_bucket_is_not_substituted() -> None:
    client = FakeClient()
    store = make_store(client, "zeroshot_learning_output")

    store.save(make_record())

    assert client.created == ["zeroshot_learning_output"]
    assert all(bucket == "zeroshot_learning_output" for bucket, _key in client.objects)


def test_rejected_bucket_creation_does_not_substitute_or_write() -> None:
    client = FakeClient()
    client.make_bucket_error = FakeHttpError("private response")

    with pytest.raises(PredictionWriteError) as error:
        make_store(client, "zeroshot_learning_output").save(make_record())

    assert error.value.kind == "failed"
    assert client.created == ["zeroshot_learning_output"]
    assert client.put_calls == 0
    assert client.objects == {}


def test_invalid_record_is_rejected_before_any_write() -> None:
    client = FakeClient()
    record = make_record()
    record["ranked_results"] = [{"label": "sports", "score": float("inf")}]

    with pytest.raises(PredictionWriteError) as error:
        make_store(client).save(record)

    assert error.value.kind == "failed"
    assert client.put_calls == 0


def test_minio_transport_retries_are_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.prediction_store as storage

    captured: dict[str, object] = {}

    class FakePool:
        def clear(self) -> None:
            return None

    class FakeMinio:
        def __init__(self, _endpoint: str, **options: object) -> None:
            captured.update(options)

    storage._cached_minio_client.clear()
    monkeypatch.setattr(
        storage.urllib3,
        "PoolManager",
        lambda **options: captured.update({"pool_options": options}) or FakePool(),
    )
    monkeypatch.setattr(storage, "Minio", FakeMinio)

    settings = MinIOServiceSettings(
        endpoint="localhost:9000",
        secure=False,
        access_key="access",
        secret_key="secret",
        bucket="test-bucket",
    )
    storage.create_minio_client(settings)

    assert captured["pool_options"]["retries"] is False
    storage._cached_minio_client.clear()
