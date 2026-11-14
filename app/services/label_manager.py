import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from filelock import FileLock, SoftFileLock, Timeout

from app.config.label_catalog import (
    CatalogError,
    LabelCatalog,
    LabelSet,
    parse_catalog,
    parse_yaml,
    serialize_catalog,
    validate_values,
)
from app.config.label_settings import resolve_label_path
from app.utils.logging_config import configure_logging, log_event

logger = configure_logging("label_management")

_label_lock_paths: set[str] = set()


class _LabelLockLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            isinstance(record.args, tuple)
            and any(
                isinstance(value, str) and value in _label_lock_paths
                for value in record.args
            )
        )


logging.getLogger("filelock").addFilter(_LabelLockLogFilter())


class LabelManagerError(Exception):
    def __init__(self, message: str, kind: str, field: str | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.field = field


@dataclass(frozen=True)
class CatalogSnapshot:
    sets: tuple[LabelSet, ...]
    warning: str | None = None


@dataclass
class _CommitState:
    may_have_committed: bool = False


class LabelManager:
    def __init__(self, path: Path | None = None, *, timeout: float = 10) -> None:
        configured_path = resolve_label_path(path)
        try:
            self.path = Path(os.path.normcase(str(configured_path.resolve())))
            self.marker = self.path.with_name(self.path.name + ".initialized")
            self.lock_path = self.path.with_name(self.path.name + ".lock")
        except (OSError, RuntimeError, ValueError):
            log_event(logger, "label_configuration.path", outcome="failure")
            raise LabelManagerError(
                "Label configuration path is invalid or unavailable. Choose a "
                "file path in LABEL_CONFIG_FILE and check storage access.",
                "recovery",
            ) from None
        _label_lock_paths.add(str(self.lock_path))
        self.timeout = timeout

    def _lock(self) -> FileLock:
        if FileLock is SoftFileLock:
            raise LabelManagerError(
                "Native locking is unavailable. Use a supported local filesystem.",
                "lock",
            )
        return FileLock(
            self.lock_path,
            timeout=self.timeout,
            preserve_lock_file=True,
            fallback_to_soft=False,
        )

    @staticmethod
    def _exists(path: Path) -> bool:
        try:
            path.stat()
            return True
        except FileNotFoundError:
            return False

    def _read(self) -> CatalogSnapshot:
        try:
            has_catalog = self._exists(self.path)
            has_marker = self._exists(self.marker)
            if has_marker:
                marker = parse_yaml(self.marker.read_text(encoding="utf-8"))
                if (
                    not isinstance(marker, dict)
                    or set(marker) != {"schema_version"}
                    or type(marker["schema_version"]) is not int
                    or marker["schema_version"] != 1
                ):
                    raise LabelManagerError(
                        "Initialization evidence is invalid; recover from a backup.",
                        "recovery",
                    )
            if not has_catalog:
                if has_marker:
                    raise LabelManagerError(
                        "Catalog is missing; stop writers and recover from a backup.",
                        "recovery",
                    )
                return CatalogSnapshot(
                    (),
                    "No catalog or initialization evidence was found. Prior total "
                    "data loss cannot be detected; restore a backup if needed.",
                )
            catalog = parse_catalog(self.path.read_text(encoding="utf-8"))
            warning = None
            if not has_marker:
                self._establish_marker()
                warning = (
                    "Initialization evidence was missing and has been created. "
                    "Check backups if previous data may have been lost."
                )
            return CatalogSnapshot(catalog.sets, warning)
        except (CatalogError, OSError, UnicodeError):
            log_event(logger, "label_configuration.read", outcome="failure")
            raise LabelManagerError(
                "Label configuration cannot be read or is invalid. Stop writers "
                "and repair or recover it from a backup.",
                "recovery",
            ) from None

    def _establish_marker(self) -> None:
        try:
            self._replace(self.marker, "schema_version: 1\n")
        except LabelManagerError as error:
            log_event(
                logger,
                "label_configuration.initialization",
                outcome="indeterminate" if error.kind == "indeterminate" else "failure",
            )
            raise LabelManagerError(
                "Initialization evidence could not be established. Stop writers "
                "and inspect the configuration before recovery.",
                "recovery",
            ) from None

    @staticmethod
    def _sync_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _replace(self, path: Path, content: str) -> None:
        temporary: Path | None = None
        replacing = False
        try:
            descriptor, temp_name = tempfile.mkstemp(
                prefix=path.name + ".", suffix=".tmp", dir=path.parent
            )
            temporary = Path(temp_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            replacing = True
            os.replace(temporary, path)
            temporary = None
            self._sync_directory(path.parent)
        except OSError:
            if replacing:
                raise LabelManagerError(
                    "The write outcome is uncertain. Inspect saved configuration "
                    "before retrying.",
                    "indeterminate",
                ) from None
            raise LabelManagerError(
                "The change was not saved. Check storage access and retry.",
                "write",
            ) from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    log_event(logger, "label_configuration.cleanup", outcome="failure")

    def _write(self, sets: tuple[LabelSet, ...], state: _CommitState) -> None:
        if not self._exists(self.marker):
            self._establish_marker()
        try:
            self._replace(self.path, serialize_catalog(LabelCatalog(sets)))
        except LabelManagerError as error:
            state.may_have_committed = error.kind == "indeterminate"
            raise
        state.may_have_committed = True

    @staticmethod
    def _write_error(state: _CommitState) -> LabelManagerError:
        if state.may_have_committed:
            return LabelManagerError(
                "The write outcome is uncertain. Inspect saved configuration "
                "before retrying.",
                "indeterminate",
            )
        return LabelManagerError(
            "The change was not saved. Check storage access and retry.", "write"
        )

    @staticmethod
    def _log_write_error(error: LabelManagerError) -> None:
        if error.kind in {"write", "indeterminate"}:
            outcome = "indeterminate" if error.kind == "indeterminate" else "failure"
            log_event(logger, "label_configuration.write", outcome=outcome)

    def _lock_timeout_error(self, state: _CommitState) -> LabelManagerError:
        if state.may_have_committed:
            error = self._write_error(state)
            self._log_write_error(error)
            return error
        return LabelManagerError("Label configuration is busy. Wait and retry.", "lock")

    def list_sets(self) -> CatalogSnapshot:
        try:
            with self._lock():
                return self._read()
        except Timeout:
            raise LabelManagerError(
                "Label configuration is busy. Wait and retry.", "lock"
            ) from None
        except OSError:
            raise LabelManagerError(
                "Label configuration is unavailable. Check storage access.", "recovery"
            ) from None

    def create(self, name: str, labels: list[str]) -> LabelSet:
        state = _CommitState()
        try:
            with self._lock():
                snapshot = self._read()
                clean_name, clean_labels = validate_values(name, labels, snapshot.sets)
                item = LabelSet(str(uuid4()), 1, clean_name, clean_labels)
                self._write((*snapshot.sets, item), state)
            log_event(logger, "label_configuration.write", outcome="success")
            return item
        except CatalogError as error:
            raise LabelManagerError(str(error), "validation", error.field) from None
        except LabelManagerError as error:
            self._log_write_error(error)
            raise
        except Timeout:
            raise self._lock_timeout_error(state) from None
        except OSError:
            write_error = self._write_error(state)
            self._log_write_error(write_error)
            raise write_error from None

    def update(
        self, identifier: str, revision: int, name: str, labels: list[str]
    ) -> LabelSet:
        state = _CommitState()
        try:
            with self._lock():
                snapshot = self._read()
                previous = self._current(snapshot, identifier, revision)
                others = tuple(item for item in snapshot.sets if item.id != identifier)
                clean_name, clean_labels = validate_values(name, labels, others)
                item = LabelSet(
                    identifier, previous.revision + 1, clean_name, clean_labels
                )
                self._write(
                    tuple(
                        item if old.id == identifier else old for old in snapshot.sets
                    ),
                    state,
                )
            log_event(logger, "label_configuration.write", outcome="success")
            return item
        except CatalogError as error:
            raise LabelManagerError(str(error), "validation", error.field) from None
        except LabelManagerError as error:
            self._log_write_error(error)
            raise
        except Timeout:
            raise self._lock_timeout_error(state) from None
        except OSError:
            write_error = self._write_error(state)
            self._log_write_error(write_error)
            raise write_error from None

    @staticmethod
    def _current(snapshot: CatalogSnapshot, identifier: str, revision: int) -> LabelSet:
        for item in snapshot.sets:
            if item.id == identifier and item.revision == revision:
                return item
        log_event(logger, "label_configuration.conflict", outcome="failure")
        raise LabelManagerError(
            "This set changed or was removed. Refresh before retrying.", "stale"
        )

    def remove(self, identifier: str, revision: int, *, confirmed: bool) -> None:
        if not confirmed:
            return
        state = _CommitState()
        try:
            with self._lock():
                snapshot = self._read()
                self._current(snapshot, identifier, revision)
                self._write(
                    tuple(item for item in snapshot.sets if item.id != identifier),
                    state,
                )
            log_event(logger, "label_configuration.write", outcome="success")
        except LabelManagerError as error:
            self._log_write_error(error)
            raise
        except Timeout:
            raise self._lock_timeout_error(state) from None
        except OSError:
            write_error = self._write_error(state)
            self._log_write_error(write_error)
            raise write_error from None
