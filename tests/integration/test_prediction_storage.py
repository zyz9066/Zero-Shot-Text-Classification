from __future__ import annotations

import json
import os
from dataclasses import replace
from io import BytesIO
from uuid import uuid4

import pytest

from app.config.loader import load_minio_settings
from app.services.prediction_store import PredictionStore, create_minio_client


def test_minio_prediction_write_and_read() -> None:
    test_bucket = os.environ.get("MINIO_TEST_BUCKET")
    if not test_bucket:
        pytest.skip("Set MINIO_TEST_BUCKET to opt in to MinIO integration coverage")

    settings = replace(load_minio_settings(), bucket=test_bucket)
    client = create_minio_client(settings)
    request_id = str(uuid4())
    record: dict[str, object] = {
        "request_id": request_id,
        "input_text": "Integration test input",
        "predicted_class": "sports",
        "predicted_score": 0.75,
        "candidate_labels": ["sports", "news"],
        "ranked_results": [
            {"label": "sports", "score": 0.75},
            {"label": "news", "score": 0.25},
        ],
        "model_name": "Integration Model",
        "model_identifier": "org/model",
        "model_revision": "a" * 40,
        "timestamp": "2026-11-14T20:00:00+00:00",
        "application_version": "0.1.0",
    }
    key = f"predictions/{request_id}.json"
    sentinel_key = f"validation-sentinels/{uuid4()}.txt"
    sentinel_content = b"non-sensitive cleanup sentinel"
    written = False
    sentinel_written = False

    try:
        PredictionStore(settings, client=client).save(record)
        written = True
        client.put_object(
            test_bucket,
            sentinel_key,
            BytesIO(sentinel_content),
            len(sentinel_content),
            content_type="text/plain",
        )
        sentinel_written = True
        response = client.get_object(test_bucket, key)
        try:
            assert json.loads(response.read()) == record
        finally:
            response.close()
            response.release_conn()
    finally:
        try:
            if written:
                client.remove_object(test_bucket, key)
            if sentinel_written:
                response = client.get_object(test_bucket, sentinel_key)
                try:
                    assert response.read(len(sentinel_content) + 1) == sentinel_content
                finally:
                    response.close()
                    response.release_conn()
        finally:
            if sentinel_written:
                client.remove_object(test_bucket, sentinel_key)
