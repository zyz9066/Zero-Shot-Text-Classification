from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ConfigurationScope = Literal["application", "model", "minio"]
ConfigurationSourceKind = Literal["environment", "yaml", "default"]


@dataclass(frozen=True)
class ConfigurationIssue:
    setting_name: str
    scope: ConfigurationScope
    message: str
    source_kind: ConfigurationSourceKind | None = None

    def __str__(self) -> str:
        return f"{self.setting_name}: {self.message}"


class ConfigurationError(ValueError):
    def __init__(self, issue: ConfigurationIssue) -> None:
        self.issue = issue
        super().__init__(str(issue))


@dataclass(frozen=True)
class AppSettings:
    app_version: str = "0.1.0"
    config_file: Path = field(default=Path("configs/app.yaml"), repr=False)


@dataclass(frozen=True)
class ModelRuntimeSettings:
    model_dir: Path = Path("./models")
    hf_home: Path = Path("./.cache/huggingface")
    transformers_cache: Path = Path("./.cache/huggingface/transformers")
    hf_token: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class MinIOServiceSettings:
    endpoint: str
    secure: bool
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    bucket: str = "zeroshot_learning_output"
