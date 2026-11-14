import json
import logging
import re
import sys
from typing import TextIO

_ALLOWED_FIELDS = {"setting_name", "source_kind", "outcome", "model_id"}
_SAFE_SETTING_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_SAFE_SOURCE_KINDS = {"environment", "yaml", "default"}
_SAFE_OUTCOMES = {"success", "failure", "invalid", "unavailable", "started"}
_SAFE_MODEL_ID = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?\Z"
)
_SAFE_EVENT_NAME = re.compile(r"[a-z][a-z0-9_.-]*\Z")


def configure_logging(
    logger_name: str = "zero_shot_app",
    stream: TextIO | None = None,
) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stderr if stream is None else stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, event_name: str, **fields: object) -> None:
    safe_event_name = (
        event_name if _SAFE_EVENT_NAME.fullmatch(event_name) else "application.event"
    )
    record: dict[str, str] = {"event": safe_event_name}

    for key, value in fields.items():
        if key not in _ALLOWED_FIELDS or not isinstance(value, str):
            continue
        if key == "setting_name" and _SAFE_SETTING_NAME.fullmatch(value):
            record[key] = value
        elif key == "source_kind" and value in _SAFE_SOURCE_KINDS:
            record[key] = value
        elif key == "outcome" and value in _SAFE_OUTCOMES:
            record[key] = value
        elif (
            key == "model_id"
            and len(value) <= 200
            and ".." not in value
            and _SAFE_MODEL_ID.fullmatch(value)
        ):
            record[key] = value

    logger.info(json.dumps(record, sort_keys=True))
