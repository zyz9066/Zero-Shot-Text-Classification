import os
from pathlib import Path

DEFAULT_LABEL_PATH = Path("configs/labels.yaml")


class LabelSettingsError(ValueError):
    pass


def resolve_label_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    override = os.environ.get("LABEL_CONFIG_FILE")
    if override is None:
        return DEFAULT_LABEL_PATH
    if not override.strip():
        raise LabelSettingsError("LABEL_CONFIG_FILE must be a non-empty path.")
    return Path(override.strip())
