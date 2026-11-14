import json
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from huggingface_hub import HfApi, scan_cache_dir, snapshot_download
from huggingface_hub.utils.tqdm import tqdm as hub_tqdm


class HubAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class CacheCleanupPreview:
    cache_path: Path
    repository_count: int
    revision_count: int
    expected_freed_bytes: int
    incomplete_download_count: int


class _DeleteStrategy(Protocol):
    expected_freed_size: int

    def execute(self) -> None: ...


class _CachedRevision(Protocol):
    commit_hash: str


class _CachedRepository(Protocol):
    revisions: Iterable[_CachedRevision]


class _CachedIncompleteFile(Protocol):
    file_path: Path
    size_on_disk: int


class _CacheInfo(Protocol):
    repos: Iterable[_CachedRepository]
    incomplete_files: Iterable[_CachedIncompleteFile]

    def delete_revisions(self, *revisions: str) -> _DeleteStrategy: ...


class HuggingFaceHubAdapter:
    def __init__(
        self,
        cache_dir: Path,
        token: str | None = None,
        *,
        token_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self._token = token
        self._token_provider = token_provider

    def resolve_revision(
        self, model_id: str, requested_revision: str | None = None
    ) -> str:
        try:
            model_info = HfApi(token=self._resolve_token()).model_info(
                model_id, revision=requested_revision
            )
            resolved_revision = model_info.sha
        except Exception:
            raise HubAdapterError(
                "Unable to resolve the model revision from the Hugging Face Hub"
            ) from None

        if not isinstance(resolved_revision, str) or not resolved_revision:
            raise HubAdapterError(
                "The Hugging Face Hub did not provide an immutable model revision"
            )
        return resolved_revision

    def download_snapshot(
        self,
        model_id: str,
        revision: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> Path:
        try:
            if progress_callback is None:
                snapshot_path = snapshot_download(
                    repo_id=model_id,
                    revision=revision,
                    cache_dir=self.cache_dir,
                    token=self._resolve_token(),
                )
            else:
                snapshot_path = snapshot_download(
                    repo_id=model_id,
                    revision=revision,
                    cache_dir=self.cache_dir,
                    token=self._resolve_token(),
                    tqdm_class=_progress_tqdm_class(progress_callback),
                )
        except Exception:
            raise HubAdapterError(
                "Unable to download the model snapshot from the Hugging Face Hub"
            ) from None
        return Path(snapshot_path)

    def preview_cache_cleanup(self) -> CacheCleanupPreview:
        try:
            cache_info = cast(_CacheInfo, scan_cache_dir(cache_dir=self.cache_dir))
            repositories = tuple(cache_info.repos)
            revisions = self._revision_ids(cache_info)
            revision_strategy = cache_info.delete_revisions(*revisions)
            incomplete_files = tuple(cache_info.incomplete_files)
            prune_summary = _run_cache_prune(self.cache_dir, dry_run=True)
        except Exception:
            raise HubAdapterError(
                "Unable to inspect the configured Hugging Face cache"
            ) from None

        expected_freed_bytes = revision_strategy.expected_freed_size + sum(
            incomplete_file.size_on_disk for incomplete_file in incomplete_files
        )
        incomplete_count = prune_summary.get("incomplete", len(incomplete_files))
        if not isinstance(incomplete_count, int):
            incomplete_count = len(incomplete_files)
        return CacheCleanupPreview(
            cache_path=self.cache_dir,
            repository_count=len(repositories),
            revision_count=len(revisions),
            expected_freed_bytes=expected_freed_bytes,
            incomplete_download_count=incomplete_count,
        )

    def clear_cache(self) -> int:
        try:
            cache_info = cast(_CacheInfo, scan_cache_dir(cache_dir=self.cache_dir))
            revisions = self._revision_ids(cache_info)
            incomplete_files = tuple(cache_info.incomplete_files)
            prune_executable = shutil.which("hf")
            if prune_executable is None:
                raise HubAdapterError(
                    "Hugging Face cache pruning is unavailable in this environment"
                )
            expected_freed_bytes = sum(
                incomplete_file.size_on_disk for incomplete_file in incomplete_files
            )
            if revisions:
                revision_strategy = cache_info.delete_revisions(*revisions)
                expected_freed_bytes += revision_strategy.expected_freed_size
                revision_strategy.execute()
            _run_cache_prune(
                self.cache_dir,
                dry_run=False,
                executable=prune_executable,
            )
        except Exception:
            raise HubAdapterError(
                "Unable to clear the configured Hugging Face cache"
            ) from None
        return expected_freed_bytes

    @staticmethod
    def _revision_ids(cache_info: _CacheInfo) -> tuple[str, ...]:
        return tuple(
            revision.commit_hash
            for repository in cache_info.repos
            for revision in repository.revisions
        )

    def _resolve_token(self) -> str | None:
        if self._token_provider is not None:
            return self._token_provider()
        return self._token


def _progress_tqdm_class(
    progress_callback: Callable[[float], None],
) -> type[hub_tqdm]:
    class ProgressTqdm(hub_tqdm):
        def update(self, n: int | float | None = 1) -> None:
            super().update(n)
            total = self.total
            if total:
                progress_callback(min(self.n / total, 1.0))

    return ProgressTqdm


def _run_cache_prune(
    cache_dir: Path,
    *,
    dry_run: bool,
    executable: str | None = None,
) -> dict[str, object]:
    prune_executable = executable or shutil.which("hf")
    if prune_executable is None:
        raise HubAdapterError(
            "Hugging Face cache pruning is unavailable in this environment"
        )

    command = [
        prune_executable,
        "cache",
        "prune",
        "--cache-dir",
        str(cache_dir),
        "--json",
        "--dry-run" if dry_run else "--yes",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        raise HubAdapterError(
            "Unable to prune the configured Hugging Face cache"
        ) from None

    if result.returncode != 0:
        raise HubAdapterError("Unable to prune the configured Hugging Face cache")
    if not result.stdout.strip():
        return {}
    try:
        summary = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise HubAdapterError(
            "Hugging Face cache prune returned invalid output"
        ) from None
    if not isinstance(summary, dict):
        raise HubAdapterError("Hugging Face cache prune returned invalid output")
    return summary
