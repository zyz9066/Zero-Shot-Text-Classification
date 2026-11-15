import io
import json

from app.utils.logging_config import configure_logging, log_event


def test_classification_events_keep_safe_metadata_and_drop_sensitive_values() -> None:
    output = io.StringIO()
    logger = configure_logging("test.classification", stream=output)
    log_event(
        logger,
        "classification.storage",
        outcome="indeterminate",
        request_id="e318e2dd-7562-4c75-84b9-c5ce29b913af",
        model_id="org/model",
        label_set_id="b978553d-3269-40a9-a884-1b9f53aee9da",
        bucket="zeroshot_learning_output",
        input_text="private user text",
        prediction={"label": "private prediction"},
        token="private token",
        local_path="C:\\private\\model",
        exception="private service response",
    )

    record = json.loads(output.getvalue())

    assert record == {
        "bucket": "zeroshot_learning_output",
        "event": "classification.storage",
        "label_set_id": "b978553d-3269-40a9-a884-1b9f53aee9da",
        "model_id": "org/model",
        "outcome": "indeterminate",
        "request_id": "e318e2dd-7562-4c75-84b9-c5ce29b913af",
    }
    assert "private" not in output.getvalue()
