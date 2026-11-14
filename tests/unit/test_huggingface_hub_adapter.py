import io
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.services.huggingface_hub_adapter as adapter_module
from app.services.huggingface_hub_adapter import (
    HubAdapterError,
    HuggingFaceHubAdapter,
)


class FakeApi:
    def __init__(self, token: str | None, revision_sha: str) -> None:
        self.token = token
        self.revision_sha = revision_sha
        self.requested: tuple[str, str | None] | None = None

    def model_info(self, model_id: str, *, revision: str | None = None) -> object:
        self.requested = (model_id, revision)
        return SimpleNamespace(sha=self.revision_sha)


def test_resolves_default_revision_and_downloads_pinned_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved_sha = "a" * 40
    fake_api = FakeApi(None, resolved_sha)
    downloads: list[dict[str, object]] = []
    snapshot_path = tmp_path / "snapshot"
    monkeypatch.setattr(adapter_module, "HfApi", lambda token: fake_api)
    monkeypatch.setattr(
        adapter_module,
        "snapshot_download",
        lambda **kwargs: downloads.append(kwargs) or str(snapshot_path),
    )
    adapter = HuggingFaceHubAdapter(tmp_path / "hub-cache")

    resolved_revision = adapter.resolve_revision("org/model")
    downloaded_path = adapter.download_snapshot("org/model", resolved_revision)

    assert fake_api.requested == ("org/model", None)
    assert resolved_revision == resolved_sha
    assert downloaded_path == snapshot_path
    assert downloads == [
        {
            "repo_id": "org/model",
            "revision": resolved_sha,
            "cache_dir": tmp_path / "hub-cache",
            "token": None,
        }
    ]


def test_resolves_configured_revision_and_passes_optional_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_api = FakeApi("test-token", "b" * 40)
    monkeypatch.setattr(adapter_module, "HfApi", lambda token: fake_api)
    adapter = HuggingFaceHubAdapter(tmp_path / "hub-cache", token="test-token")

    revision = adapter.resolve_revision("org/model", "release-tag")

    assert fake_api.requested == ("org/model", "release-tag")
    assert revision == "b" * 40
    assert fake_api.token == "test-token"


def test_token_provider_is_resolved_for_each_hub_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_values = iter(("revision-token", "download-token"))
    api_tokens: list[str | None] = []
    download_tokens: list[str | None] = []

    def create_api(token: str | None) -> FakeApi:
        api_tokens.append(token)
        return FakeApi(token, "c" * 40)

    def download_snapshot(**kwargs: object) -> str:
        download_tokens.append(kwargs["token"])
        return str(tmp_path / "snapshot")

    monkeypatch.setattr(adapter_module, "HfApi", create_api)
    monkeypatch.setattr(adapter_module, "snapshot_download", download_snapshot)
    adapter = HuggingFaceHubAdapter(
        tmp_path / "hub-cache", token_provider=lambda: next(token_values)
    )

    revision = adapter.resolve_revision("org/model")
    adapter.download_snapshot("org/model", revision)

    assert adapter._token is None
    assert api_tokens == ["revision-token"]
    assert download_tokens == ["download-token"]


def test_snapshot_download_reports_transfer_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    progress_values: list[float] = []

    def download_snapshot(**kwargs: object) -> str:
        progress_bar_class = kwargs["tqdm_class"]
        progress_bar = progress_bar_class(
            total=100, desc="Downloading bytes", file=io.StringIO()
        )
        progress_bar.update(25)
        progress_bar.update(50)
        progress_bar.close()
        return str(tmp_path / "snapshot")

    monkeypatch.setattr(adapter_module, "snapshot_download", download_snapshot)
    adapter = HuggingFaceHubAdapter(tmp_path / "hub-cache")

    adapter.download_snapshot("org/model", "a" * 40, progress_values.append)

    assert progress_values == [0.25, 0.75]


def test_hub_errors_are_translated_without_sensitive_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingApi:
        def __init__(self, token: str | None) -> None:
            del token

        def model_info(self, model_id: str, *, revision: str | None = None) -> object:
            del model_id, revision
            raise RuntimeError("token=private-value C:/private/model-cache")

    monkeypatch.setattr(adapter_module, "HfApi", FailingApi)
    adapter = HuggingFaceHubAdapter(tmp_path / "hub-cache", token="private-value")

    with pytest.raises(HubAdapterError) as error:
        adapter.resolve_revision("org/model")

    assert "private-value" not in str(error.value)
    assert "C:/private/model-cache" not in str(error.value)
    assert "revision" in str(error.value).lower()


def test_cache_preview_and_cleanup_use_hub_deletion_strategies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    prune_calls: list[tuple[Path, bool]] = []

    class Strategy:
        expected_freed_size = 512

        def __init__(self, kind: str) -> None:
            self.kind = kind

        def execute(self) -> None:
            calls.append((self.kind, ()))

    class CacheInfo:
        repos = [SimpleNamespace(revisions=[SimpleNamespace(commit_hash="a" * 40)])]
        incomplete_files = [
            SimpleNamespace(file_path=tmp_path / "partial.incomplete", size_on_disk=512)
        ]

        def delete_revisions(self, *revisions: str) -> Strategy:
            calls.append(("revisions", revisions))
            return Strategy("revision-delete")

    monkeypatch.setattr(adapter_module, "scan_cache_dir", lambda cache_dir: CacheInfo())
    monkeypatch.setattr(
        adapter_module,
        "_run_cache_prune",
        lambda cache_dir, *, dry_run, executable=None: (
            prune_calls.append((cache_dir, dry_run)) or {"incomplete": 1}
        ),
    )
    adapter = HuggingFaceHubAdapter(tmp_path / "hub-cache")

    preview = adapter.preview_cache_cleanup()
    freed_bytes = adapter.clear_cache()

    assert preview.repository_count == 1
    assert preview.revision_count == 1
    assert preview.incomplete_download_count == 1
    assert preview.expected_freed_bytes == 1024
    assert freed_bytes == 1024
    assert ("revision-delete", ()) in calls
    assert prune_calls == [
        (tmp_path / "hub-cache", True),
        (tmp_path / "hub-cache", False),
    ]


def test_incomplete_cache_preview_and_cleanup_use_hf_cache_prune(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "hub-cache"
    incomplete_file = (
        cache_dir / "models--org--model" / "blobs" / "partial-download.incomplete"
    )
    incomplete_file.parent.mkdir(parents=True)
    incomplete_file.write_bytes(b"partial model data")
    adapter = HuggingFaceHubAdapter(cache_dir)

    preview = adapter.preview_cache_cleanup()

    assert preview.incomplete_download_count == 1
    assert preview.expected_freed_bytes == len(b"partial model data")
    assert incomplete_file.exists()

    adapter.clear_cache()

    assert not incomplete_file.exists()


def test_missing_cache_is_reported_without_exposing_its_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        adapter_module,
        "scan_cache_dir",
        lambda cache_dir: (_ for _ in ()).throw(RuntimeError(f"missing {cache_dir}")),
    )
    adapter = HuggingFaceHubAdapter(tmp_path / "private-cache")

    with pytest.raises(HubAdapterError) as error:
        adapter.preview_cache_cleanup()

    assert str(tmp_path) not in str(error.value)
    assert "cache" in str(error.value).lower()
