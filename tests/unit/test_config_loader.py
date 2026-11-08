from pathlib import Path

import pytest

from app.config.loader import (
    ConfigurationError,
    load_app_settings,
    load_minio_settings,
    load_model_settings,
)


def write_config(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_environment_overrides_yaml_and_yaml_overrides_defaults(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path / "app.yaml",
        "app:\n  version: yaml-version\nmodel:\n  model_dir: ./yaml-models\n",
    )

    app_settings = load_app_settings(config_path, {"APP_VERSION": "env-version"})
    model_settings = load_model_settings(config_path, {"MODEL_DIR": "./env-models"})
    defaults = load_app_settings(environ={})

    assert app_settings.app_version == "env-version"
    assert model_settings.model_dir == Path("./env-models")
    assert defaults.app_version == "0.1.0"


def test_service_configuration_uses_shared_yaml_and_environment_values(
    tmp_path: Path,
) -> None:
    config_path = write_config(
        tmp_path / "app.yaml",
        "model:\n  hf_home: ./shared-cache\n"
        "minio:\n  endpoint: yaml-endpoint\n  secure: false\n",
    )

    model_settings = load_model_settings(config_path, {})
    minio_settings = load_minio_settings(
        config_path,
        {
            "MINIO_ENDPOINT": "env-endpoint",
            "MINIO_SECURE": "true",
            "MINIO_ACCESS_KEY": "access-value",
            "MINIO_SECRET_KEY": "secret-value",
        },
    )

    assert model_settings.hf_home == Path("./shared-cache")
    assert minio_settings.endpoint == "env-endpoint"
    assert minio_settings.secure is True
    assert minio_settings.bucket == "zeroshot_learning_output"


def test_minio_settings_are_not_required_for_application_shell() -> None:
    app_settings = load_app_settings(environ={})

    assert app_settings.app_version == "0.1.0"
    with pytest.raises(ConfigurationError, match="MINIO_ENDPOINT"):
        load_minio_settings(environ={})


def test_malformed_yaml_error_does_not_expose_config_path(tmp_path: Path) -> None:
    config_path = write_config(tmp_path / "private" / "app.yaml", "app: [\n")

    with pytest.raises(ConfigurationError) as error:
        load_app_settings(config_path, {})

    assert str(config_path) not in str(error.value)
    assert "line" in str(error.value).lower()


def test_yaml_root_must_be_a_mapping(tmp_path: Path) -> None:
    config_path = write_config(tmp_path / "app.yaml", "- a-list\n")

    with pytest.raises(ConfigurationError, match="mapping"):
        load_app_settings(config_path, {})


def test_explicit_missing_config_path_is_an_error(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigurationError, match="APP_CONFIG_FILE"):
        load_app_settings(missing_path, {})


def test_invalid_setting_types_are_reported_without_values(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path / "app.yaml",
        "app:\n  version: 42\nminio:\n  endpoint: endpoint\n  secure: maybe\n",
    )

    with pytest.raises(ConfigurationError, match="APP_VERSION"):
        load_app_settings(config_path, {})
    with pytest.raises(ConfigurationError, match="MINIO_SECURE"):
        load_minio_settings(
            config_path,
            {
                "MINIO_ACCESS_KEY": "access-value",
                "MINIO_SECRET_KEY": "secret-value",
            },
        )


def test_unknown_yaml_keys_are_rejected(tmp_path: Path) -> None:
    config_path = write_config(tmp_path / "app.yaml", "app:\n  typo: value\n")

    with pytest.raises(ConfigurationError, match="unknown"):
        load_app_settings(config_path, {})


def test_service_secrets_are_hidden_from_settings_representation(
    tmp_path: Path,
) -> None:
    minio_settings = load_minio_settings(
        environ={
            "MINIO_ENDPOINT": "minio.local:9000",
            "MINIO_SECURE": "false",
            "MINIO_ACCESS_KEY": "access-value",
            "MINIO_SECRET_KEY": "super-secret-value",
        },
    )

    assert "access-value" not in repr(minio_settings)
    assert "super-secret-value" not in repr(minio_settings)


def test_invalid_boolean_and_missing_minio_credentials_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="MINIO_SECURE"):
        load_minio_settings(
            environ={
                "MINIO_ENDPOINT": "minio.local:9000",
                "MINIO_SECURE": "sometimes",
                "MINIO_ACCESS_KEY": "access-value",
                "MINIO_SECRET_KEY": "secret-value",
            }
        )
    with pytest.raises(ConfigurationError, match="MINIO_ACCESS_KEY"):
        load_minio_settings(
            environ={"MINIO_ENDPOINT": "minio.local:9000", "MINIO_SECURE": "false"}
        )
