import io
import json
from pathlib import Path

from app.utils.logging_config import configure_logging, log_event


def test_structured_events_exclude_secrets_input_text_and_absolute_paths() -> None:
    output = io.StringIO()
    logger = configure_logging(logger_name="test.safe_logging", stream=output)

    log_event(
        logger,
        "configuration.validation_failed",
        setting_name="MINIO_SECRET_KEY",
        source_kind="environment",
        outcome="invalid",
        secret="super-secret-value",
        access_key="access-value",
        input_text="sensitive user input",
        path=str(Path("C:/Users/private/local-settings.yaml")),
    )

    record = json.loads(output.getvalue())
    serialized = json.dumps(record)

    assert record["event"] == "configuration.validation_failed"
    assert record["setting_name"] == "MINIO_SECRET_KEY"
    assert record["outcome"] == "invalid"
    assert "super-secret-value" not in serialized
    assert "access-value" not in serialized
    assert "sensitive user input" not in serialized
    assert "C:/Users/private/local-settings.yaml" not in serialized


def test_model_identifiers_are_logged_only_when_they_match_repository_syntax() -> None:
    output = io.StringIO()
    logger = configure_logging(
        logger_name="test.model_identifier_logging", stream=output
    )

    log_event(logger, "model.download", model_id="org/public-model", outcome="success")
    log_event(
        logger, "model.download", model_id="token=private-value", outcome="failure"
    )

    records = [json.loads(line) for line in output.getvalue().splitlines()]

    assert records[0]["model_id"] == "org/public-model"
    assert "model_id" not in records[1]
    assert "private-value" not in output.getvalue()
