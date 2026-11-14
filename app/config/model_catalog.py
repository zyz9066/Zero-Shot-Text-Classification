import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_MODEL_CATALOG_PATH = Path("configs/models.yaml")
_ROOT_KEYS = {"models"}
_MODEL_KEYS = {"model_id", "display_name", "task", "revision"}
_SUPPORTED_TASKS = {"zero-shot-classification"}
_REPOSITORY_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


@dataclass(frozen=True)
class ConfiguredModel:
    model_id: str
    display_name: str
    task: str
    requested_revision: str | None = None


class ModelCatalogError(ValueError):
    pass


def load_model_catalog(
    catalog_path: Path = DEFAULT_MODEL_CATALOG_PATH,
) -> tuple[ConfiguredModel, ...]:
    try:
        with catalog_path.open(encoding="utf-8") as catalog_file:
            document = yaml.safe_load(catalog_file)
    except yaml.YAMLError:
        raise ModelCatalogError("Model catalog contains invalid YAML") from None
    except (OSError, UnicodeError):
        raise ModelCatalogError("Model catalog could not be read") from None

    if not isinstance(document, dict):
        raise ModelCatalogError("Model catalog root must be a mapping")
    if set(document) != _ROOT_KEYS:
        raise ModelCatalogError("Model catalog contains unknown or missing keys")

    entries = document["models"]
    if not isinstance(entries, list):
        raise ModelCatalogError("Model catalog models value must be a list")

    models: list[ConfiguredModel] = []
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ModelCatalogError("Each model catalog entry must be a mapping")
        if set(entry) - _MODEL_KEYS:
            raise ModelCatalogError("Model catalog entry contains unknown keys")

        model_id = _required_string(entry, "model_id")
        display_name = _required_string(entry, "display_name")
        task = _required_string(entry, "task")
        revision = _optional_string(entry, "revision")

        if not _is_repository_id(model_id):
            raise ModelCatalogError("Model identifier is invalid")
        if model_id in seen_ids:
            raise ModelCatalogError("Model catalog contains a duplicate identifier")
        if task not in _SUPPORTED_TASKS:
            raise ModelCatalogError("Model catalog contains an unsupported task")

        seen_ids.add(model_id)
        models.append(ConfiguredModel(model_id, display_name, task, revision))

    return tuple(models)


def _required_string(entry: dict[object, object], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ModelCatalogError(f"Model catalog field '{key}' is required")
    return value.strip()


def _optional_string(entry: dict[object, object], key: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ModelCatalogError(
            f"Model catalog field '{key}' must be a non-empty string"
        )
    return value.strip()


def _is_repository_id(model_id: str) -> bool:
    parts = model_id.split("/")
    return len(parts) in {1, 2} and all(
        _REPOSITORY_PART.fullmatch(part) is not None
        and not part.endswith((".", "-"))
        and ".." not in part
        for part in parts
    )
