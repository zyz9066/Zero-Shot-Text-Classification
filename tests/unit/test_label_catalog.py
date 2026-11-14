import sys

import pytest

from app.config.label_catalog import CatalogError, parse_catalog, serialize_catalog

VALID = """\
schema_version: 1
sets:
  - id: 8fbdc477-1e0f-40c8-8ff1-f6751b50ec35
    revision: 1
    name: " Topics "
    labels: [" Sports ", Technology]
"""


def test_round_trip_normalizes_and_preserves_case_and_order() -> None:
    catalog = parse_catalog(VALID)
    assert catalog.sets[0].name == "Topics"
    assert catalog.sets[0].labels == ("Sports", "Technology")
    assert parse_catalog(serialize_catalog(catalog)) == catalog
    assert not parse_catalog("schema_version: 1\nsets: []").sets


@pytest.mark.parametrize(
    "document",
    [
        VALID + "schema_version: 1\n",
        VALID.replace("Technology", "sports"),
        VALID.replace("revision: 1", "revision: true"),
        VALID.replace("schema_version: 1", "schema_version: 2"),
        VALID.replace("8fbdc477-1e0f-40c8-8ff1-f6751b50ec35", "not-a-uuid"),
        VALID.replace("sets:", "extra: value\nsets:"),
        VALID.replace('[" Sports ", Technology]', '["", Technology]'),
        VALID.replace('[" Sports ", Technology]', "[one]"),
        VALID.replace('[" Sports ", Technology]', "wrong"),
        VALID.replace("revision: 1", "revision: 0"),
        VALID.replace("revision: 1", "revision: 1\n    revision: 2"),
        VALID
        + """\
  - id: 7134a366-8945-44fd-a506-72b6c89c87de
    revision: 1
    name: topics
    labels: [A, B]
""",
        VALID
        + """\
  - id: 8fbdc477-1e0f-40c8-8ff1-f6751b50ec35
    revision: 1
    name: Other
    labels: [A, B]
""",
    ],
)
def test_invalid_catalog_is_rejected(document: str) -> None:
    with pytest.raises(CatalogError):
        parse_catalog(document)


@pytest.mark.parametrize(
    "document",
    [
        VALID.replace('name: " Topics "', r'name: "bad\uD800"'),
        VALID.replace("Technology", r'"bad\uD800"'),
    ],
)
def test_catalog_rejects_non_utf8_names_and_labels(document: str) -> None:
    with pytest.raises(CatalogError) as error:
        parse_catalog(document)
    assert "unicode" in str(error.value).lower()


def test_excessively_nested_yaml_is_rejected_safely() -> None:
    document = "schema_version: 1\nsets: " + "[" * 1500 + "x" + "]" * 1500
    with pytest.raises(CatalogError, match="repair"):
        parse_catalog(document)


def test_invalid_yaml_timestamp_is_rejected_safely() -> None:
    document = "schema_version: 1\nsets: []\ninvalid: 2024-99-99\n"
    with pytest.raises(CatalogError, match="repair"):
        parse_catalog(document)


def test_oversized_yaml_integer_is_rejected_safely() -> None:
    previous_limit = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        document = "schema_version: " + "9" * 1000 + "\nsets: []\n"
        with pytest.raises(CatalogError, match="repair"):
            parse_catalog(document)
    finally:
        sys.set_int_max_str_digits(previous_limit)
