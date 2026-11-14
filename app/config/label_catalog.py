from collections.abc import Hashable
from dataclasses import dataclass
from uuid import UUID

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


class CatalogError(ValueError):
    def __init__(self, message: str, field: str = "catalog") -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class LabelSet:
    id: str
    revision: int
    name: str
    labels: tuple[str, ...]


@dataclass(frozen=True)
class LabelCatalog:
    sets: tuple[LabelSet, ...] = ()


class _UniqueLoader(yaml.SafeLoader):
    def construct_mapping(
        self, node: MappingNode, deep: bool = False
    ) -> dict[Hashable, object]:
        self.flatten_mapping(node)
        result: dict[Hashable, object] = {}
        for key_node, value_node in node.value:
            key: object = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                raise ConstructorError(
                    None, None, "Invalid mapping key", node.start_mark
                )
            if key in result:
                raise ConstructorError(
                    None, None, "Duplicate mapping key", node.start_mark
                )
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse_yaml(document: str) -> object:
    try:
        return yaml.load(document, Loader=_UniqueLoader)
    except (yaml.YAMLError, RecursionError, ValueError):
        raise CatalogError("Configuration contains invalid YAML; repair it.") from None


def _is_utf8_encodable(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def validate_values(
    name: object, labels: object, existing: tuple[LabelSet, ...] = ()
) -> tuple[str, tuple[str, ...]]:
    errors: list[str] = []
    if not isinstance(name, str) or not name.strip():
        errors.append("Name: enter a non-blank set name.")
        name = ""
    else:
        name = name.strip()
        if not _is_utf8_encodable(name):
            errors.append("Name: replace invalid Unicode characters.")
        elif any(item.name.casefold() == name.casefold() for item in existing):
            errors.append("Name: choose a unique set name.")
    if not isinstance(labels, (list, tuple)) or len(labels) < 2:
        errors.append("Labels: enter at least two labels.")
        if not isinstance(labels, (list, tuple)):
            labels = ()
    cleaned: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(labels, 1):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Label {index}: enter a non-blank label or remove it.")
            continue
        value = value.strip()
        if not _is_utf8_encodable(value):
            errors.append(f"Label {index}: replace invalid Unicode characters.")
            continue
        if value.casefold() in seen:
            errors.append(f"Label {index}: remove or change the duplicate label.")
            continue
        seen.add(value.casefold())
        cleaned.append(value)
    if errors:
        name_error = any(error.startswith("Name:") for error in errors)
        label_error = any(error.startswith("Label") for error in errors)
        field = (
            "multiple"
            if name_error and label_error
            else ("name" if name_error else "labels")
        )
        raise CatalogError(" ".join(errors), field)
    return name, tuple(cleaned)


def parse_catalog(document: str) -> LabelCatalog:
    root = parse_yaml(document)
    if (
        not isinstance(root, dict)
        or set(root) != {"schema_version", "sets"}
        or type(root["schema_version"]) is not int
        or root["schema_version"] != 1
        or not isinstance(root["sets"], list)
    ):
        raise CatalogError("Configuration has an invalid catalog structure; repair it.")
    result: list[LabelSet] = []
    ids: set[str] = set()
    for entry in root["sets"]:
        if not isinstance(entry, dict) or set(entry) != {
            "id",
            "revision",
            "name",
            "labels",
        }:
            raise CatalogError("Configuration has an invalid set; repair it.")
        identifier = entry["id"]
        revision = entry["revision"]
        if not isinstance(identifier, str):
            raise CatalogError("Configuration has an invalid set ID; repair it.")
        try:
            identifier = str(UUID(identifier))
        except ValueError:
            raise CatalogError(
                "Configuration has an invalid set ID; repair it."
            ) from None
        if identifier in ids or type(revision) is not int or revision < 1:
            raise CatalogError("Configuration has invalid IDs or revisions; repair it.")
        if not isinstance(entry["labels"], list):
            raise CatalogError("Configuration has invalid labels; repair it.")
        name, labels = validate_values(entry["name"], entry["labels"], tuple(result))
        result.append(LabelSet(identifier, revision, name, labels))
        ids.add(identifier)
    return LabelCatalog(tuple(result))


def serialize_catalog(catalog: LabelCatalog) -> str:
    document = {
        "schema_version": 1,
        "sets": [
            {
                "id": item.id,
                "revision": item.revision,
                "name": item.name,
                "labels": list(item.labels),
            }
            for item in catalog.sets
        ],
    }
    return yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
