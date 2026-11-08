import os
from collections.abc import Mapping
from pathlib import Path

import yaml

from app.config.settings import (
    AppSettings,
    ConfigurationError,
    ConfigurationIssue,
    ConfigurationScope,
    ConfigurationSourceKind,
    MinIOServiceSettings,
    ModelRuntimeSettings,
)

DEFAULT_CONFIG_PATH = Path("configs/app.yaml")
_ROOT_KEYS = {"app", "model", "minio"}
_SECTION_KEYS = {
    "app": {"version"},
    "model": {"model_dir", "hf_home", "transformers_cache"},
    "minio": {"endpoint", "secure", "bucket"},
}


def load_app_settings(
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AppSettings:
    environment = os.environ if environ is None else environ
    configuration, selected_path = _load_configuration(config_path, environment)
    app_values = _section(configuration, "app", "application")
    value, source = _resolve_value(
        environment, app_values, "version", "APP_VERSION", "0.1.0"
    )
    app_version = _required_string("APP_VERSION", value, "application", source)
    return AppSettings(app_version=app_version, config_file=selected_path)


def load_model_settings(
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ModelRuntimeSettings:
    environment = os.environ if environ is None else environ
    configuration, _ = _load_configuration(config_path, environment)
    model_values = _section(configuration, "model", "model")

    model_dir, model_dir_source = _resolve_value(
        environment, model_values, "model_dir", "MODEL_DIR", "./models"
    )
    hf_home, hf_home_source = _resolve_value(
        environment, model_values, "hf_home", "HF_HOME", "./.cache/huggingface"
    )
    transformers_cache, transformers_cache_source = _resolve_value(
        environment,
        model_values,
        "transformers_cache",
        "TRANSFORMERS_CACHE",
        "./.cache/huggingface/transformers",
    )
    hf_token = environment.get("HF_TOKEN")

    return ModelRuntimeSettings(
        model_dir=_required_path("MODEL_DIR", model_dir, "model", model_dir_source),
        hf_home=_required_path("HF_HOME", hf_home, "model", hf_home_source),
        transformers_cache=_required_path(
            "TRANSFORMERS_CACHE", transformers_cache, "model", transformers_cache_source
        ),
        hf_token=hf_token if hf_token else None,
    )


def load_minio_settings(
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> MinIOServiceSettings:
    environment = os.environ if environ is None else environ
    configuration, _ = _load_configuration(config_path, environment)
    minio_values = _section(configuration, "minio", "minio")

    endpoint, endpoint_source = _resolve_value(
        environment, minio_values, "endpoint", "MINIO_ENDPOINT", None
    )
    secure, secure_source = _resolve_value(
        environment, minio_values, "secure", "MINIO_SECURE", None
    )
    bucket, bucket_source = _resolve_value(
        environment,
        minio_values,
        "bucket",
        "MINIO_BUCKET",
        "zeroshot_learning_output",
    )
    access_key = environment.get("MINIO_ACCESS_KEY")
    secret_key = environment.get("MINIO_SECRET_KEY")

    return MinIOServiceSettings(
        endpoint=_required_string("MINIO_ENDPOINT", endpoint, "minio", endpoint_source),
        secure=_required_bool("MINIO_SECURE", secure, "minio", secure_source),
        access_key=_required_string(
            "MINIO_ACCESS_KEY", access_key, "minio", "environment"
        ),
        secret_key=_required_string(
            "MINIO_SECRET_KEY", secret_key, "minio", "environment"
        ),
        bucket=_required_string("MINIO_BUCKET", bucket, "minio", bucket_source),
    )


def _load_configuration(
    config_path: Path | None,
    environment: Mapping[str, str],
) -> tuple[dict[str, object], Path]:
    if config_path is not None:
        selected_path = config_path
        explicitly_selected = True
    elif "APP_CONFIG_FILE" in environment:
        selected_value = environment["APP_CONFIG_FILE"]
        if not selected_value.strip():
            raise _configuration_error(
                "APP_CONFIG_FILE",
                "must be a non-empty path",
                "application",
                "environment",
            )
        selected_path = Path(selected_value)
        explicitly_selected = True
    else:
        selected_path = DEFAULT_CONFIG_PATH
        explicitly_selected = False

    if not selected_path.exists():
        if explicitly_selected:
            raise _configuration_error(
                "APP_CONFIG_FILE",
                "selected configuration file does not exist",
                "application",
                "environment",
            )
        return {}, selected_path

    try:
        with selected_path.open(encoding="utf-8") as config_file:
            document = yaml.safe_load(config_file)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        if mark is None:
            message = "contains invalid YAML syntax"
        else:
            message = (
                f"contains invalid YAML syntax at line {mark.line + 1}, "
                f"column {mark.column + 1}"
            )
        raise _configuration_error(
            "APP_CONFIG_FILE", message, "application", "yaml"
        ) from None
    except (OSError, UnicodeError):
        raise _configuration_error(
            "APP_CONFIG_FILE", "could not be read as UTF-8", "application", "yaml"
        ) from None

    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise _configuration_error(
            "APP_CONFIG_FILE", "YAML root must be a mapping", "application", "yaml"
        )

    configuration: dict[str, object] = {}
    for key, value in document.items():
        if not isinstance(key, str) or key not in _ROOT_KEYS:
            raise _configuration_error(
                "APP_CONFIG_FILE",
                "contains an unknown top-level key",
                "application",
                "yaml",
            )
        configuration[key] = value
    return configuration, selected_path


def _section(
    configuration: Mapping[str, object],
    name: str,
    scope: ConfigurationScope,
) -> dict[str, object]:
    value = configuration.get(name, {})
    if not isinstance(value, dict):
        raise _configuration_error(name, "section must be a mapping", scope, "yaml")

    section: dict[str, object] = {}
    allowed_keys = _SECTION_KEYS[name]
    for key, item in value.items():
        if not isinstance(key, str) or key not in allowed_keys:
            raise _configuration_error(
                name, "section contains an unknown key", scope, "yaml"
            )
        section[key] = item
    return section


def _resolve_value(
    environment: Mapping[str, str],
    yaml_values: Mapping[str, object],
    yaml_key: str,
    environment_key: str,
    default: object,
) -> tuple[object, ConfigurationSourceKind]:
    if environment_key in environment:
        return environment[environment_key], "environment"
    if yaml_key in yaml_values:
        return yaml_values[yaml_key], "yaml"
    return default, "default"


def _required_string(
    setting_name: str,
    value: object,
    scope: ConfigurationScope,
    source: ConfigurationSourceKind,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _configuration_error(
            setting_name, "must be a non-empty string", scope, source
        )
    return value.strip()


def _required_path(
    setting_name: str,
    value: object,
    scope: ConfigurationScope,
    source: ConfigurationSourceKind,
) -> Path:
    path_value = _required_string(setting_name, value, scope, source)
    return Path(path_value)


def _required_bool(
    setting_name: str,
    value: object,
    scope: ConfigurationScope,
    source: ConfigurationSourceKind,
) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
    raise _configuration_error(setting_name, "must be true or false", scope, source)


def _configuration_error(
    setting_name: str,
    message: str,
    scope: ConfigurationScope,
    source: ConfigurationSourceKind | None,
) -> ConfigurationError:
    return ConfigurationError(
        ConfigurationIssue(
            setting_name=setting_name,
            scope=scope,
            message=message,
            source_kind=source,
        )
    )
