import os
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parents[2] / "app" / "streamlit_app.py"


def test_initial_shell_renders_without_model_or_minio_credentials(monkeypatch) -> None:
    for key in (
        "HF_TOKEN",
        "MINIO_ENDPOINT",
        "MINIO_SECURE",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    app = AppTest.from_file(str(APP_PATH)).run()

    assert not app.exception
    assert app.title[0].value == "Zero-Shot Text Classification"


def test_app_package_is_importable_outside_repository(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
