from pathlib import Path

import pytest

from app.config.model_catalog import (
    ConfiguredModel,
    ModelCatalogError,
    load_model_catalog,
)


def write_catalog(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_catalog_entries_and_optional_revision(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path / "models.yaml",
        "models:\n"
        "  - model_id: org/model-a\n"
        "    display_name: Model A\n"
        "    task: zero-shot-classification\n"
        "  - model_id: org/model-b\n"
        "    display_name: Model B\n"
        "    task: zero-shot-classification\n"
        "    revision: v1.2\n",
    )

    catalog = load_model_catalog(catalog_path)

    assert catalog == (
        ConfiguredModel("org/model-a", "Model A", "zero-shot-classification"),
        ConfiguredModel("org/model-b", "Model B", "zero-shot-classification", "v1.2"),
    )


def test_empty_catalog_is_valid(tmp_path: Path) -> None:
    catalog_path = write_catalog(tmp_path / "models.yaml", "models: []\n")

    assert load_model_catalog(catalog_path) == ()


@pytest.mark.parametrize(
    "entry",
    [
        "display_name: Missing ID\ntask: zero-shot-classification",
        "model_id: org/model\ntask: zero-shot-classification",
        "model_id: org/model\ndisplay_name: Missing task",
    ],
)
def test_rejects_missing_required_fields(tmp_path: Path, entry: str) -> None:
    indented_entry = entry.replace("\n", "\n    ")
    catalog_path = write_catalog(
        tmp_path / "models.yaml", f"models:\n  - {indented_entry}\n"
    )

    with pytest.raises(ModelCatalogError, match="required"):
        load_model_catalog(catalog_path)


def test_rejects_duplicate_model_identifiers(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path / "models.yaml",
        "models:\n"
        "  - model_id: org/model\n"
        "    display_name: First\n"
        "    task: zero-shot-classification\n"
        "  - model_id: org/model\n"
        "    display_name: Second\n"
        "    task: zero-shot-classification\n",
    )

    with pytest.raises(ModelCatalogError, match="duplicate"):
        load_model_catalog(catalog_path)


def test_rejects_unsupported_tasks(tmp_path: Path) -> None:
    catalog_path = write_catalog(
        tmp_path / "models.yaml",
        "models:\n"
        "  - model_id: org/model\n"
        "    display_name: Model\n"
        "    task: text-generation\n",
    )

    with pytest.raises(ModelCatalogError, match="unsupported task"):
        load_model_catalog(catalog_path)


@pytest.mark.parametrize(
    "content",
    [
        "models:\n  - model_id: org/model\n    display_name: Model\n"
        "    task: zero-shot-classification\n    unexpected: true\n",
        "models: []\nunexpected: true\n",
    ],
)
def test_rejects_unknown_keys(tmp_path: Path, content: str) -> None:
    catalog_path = write_catalog(tmp_path / "models.yaml", content)

    with pytest.raises(ModelCatalogError, match="unknown"):
        load_model_catalog(catalog_path)


@pytest.mark.parametrize("content", ["models: [\n", "- not-a-mapping\n"])
def test_rejects_malformed_or_non_mapping_yaml(tmp_path: Path, content: str) -> None:
    catalog_path = write_catalog(tmp_path / "models.yaml", content)

    with pytest.raises(ModelCatalogError):
        load_model_catalog(catalog_path)
