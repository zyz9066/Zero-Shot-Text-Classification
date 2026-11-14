from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

import pytest
from filelock import FileLock

from app.services.label_manager import LabelManager, LabelManagerError


def _create(path: Path, name: str) -> str:
    try:
        LabelManager(path).create(name, ["One", "Two"])
        return "saved"
    except LabelManagerError:
        return "rejected"


def test_simultaneous_duplicate_creates(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_create, [path, path], ["Topic", " topic "]))
    assert sorted(results) == ["rejected", "saved"]
    assert len(LabelManager(path).list_sets().sets) == 1


def _update(path: Path, identifier: str, revision: int, name: str) -> str:
    try:
        LabelManager(path).update(identifier, revision, name, ["Updated", "Labels"])
        return "saved"
    except LabelManagerError:
        return "rejected"


def test_concurrent_updates_preserve_other_sets(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    one = manager.create("First", ["A", "B"])
    two = manager.create("Second", ["C", "D"])
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_update, path, one.id, one.revision, "First"),
            pool.submit(_update, path, two.id, two.revision, "Second"),
        ]
        assert [f.result() for f in futures] == ["saved", "saved"]
    assert [item.revision for item in manager.list_sets().sets] == [2, 2]


def test_concurrent_duplicate_renames(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    one = manager.create("First", ["A", "B"])
    two = manager.create("Second", ["C", "D"])
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_update, path, one.id, one.revision, "Shared"),
            pool.submit(_update, path, two.id, two.revision, " shared "),
        ]
        assert sorted(f.result() for f in futures) == ["rejected", "saved"]
    assert len(manager.list_sets().sets) == 2


def _remove(path: Path, identifier: str, revision: int) -> str:
    try:
        LabelManager(path).remove(identifier, revision, confirmed=True)
        return "removed"
    except LabelManagerError:
        return "rejected"


def test_racing_edit_and_removal_rejects_stale_operation(tmp_path: Path) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    saved = manager.create("First", ["A", "B"])
    with ProcessPoolExecutor(max_workers=2) as pool:
        edit = pool.submit(_update, path, saved.id, saved.revision, "Changed")
        delete = pool.submit(_remove, path, saved.id, saved.revision)
        results = [edit.result(), delete.result()]
    assert results in (["saved", "rejected"], ["rejected", "removed"])


def _hold_lock(path: Path, ready, release) -> None:
    with FileLock(path, preserve_lock_file=True):
        ready.set()
        release.wait(10)


def test_process_lock_timeout(tmp_path: Path) -> None:
    manager = LabelManager(tmp_path / "labels.yaml", timeout=0.1)
    context = get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(
        target=_hold_lock, args=(manager.lock_path, ready, release)
    )
    process.start()
    try:
        assert ready.wait(10)
        with pytest.raises(LabelManagerError) as error:
            manager.create("Name", ["A", "B"])
        assert error.value.kind == "lock"
    finally:
        release.set()
        process.join(10)
    assert process.exitcode == 0


def _coordinated_write(path, action, identifier, revision, name, held, release, result):
    manager = LabelManager(path)
    original_write = manager._write

    def wait_before_write(sets, state):
        held.set()
        if not release.wait(10):
            raise TimeoutError("Timed out waiting for the competing writer")
        original_write(sets, state)

    manager._write = wait_before_write
    try:
        if action == "create":
            manager.create(name, ["One", "Two"])
        else:
            manager.update(identifier, revision, name, ["Updated", "Labels"])
        result.put(("first", "saved"))
    except LabelManagerError as error:
        result.put(("first", error.kind))


def _competing_write(path, action, identifier, revision, name, attempted, done, result):
    manager = LabelManager(path)
    original_lock = manager._lock

    def observe_attempt():
        attempted.set()
        return original_lock()

    manager._lock = observe_attempt
    try:
        if action == "create":
            manager.create(name, ["One", "Two"])
        else:
            manager.update(identifier, revision, name, ["Updated", "Labels"])
        result.put(("second", "saved"))
    except LabelManagerError as error:
        result.put(("second", error.kind))
    finally:
        done.set()


@pytest.mark.parametrize("scenario", ["create", "rename", "different_updates"])
def test_competing_writers_are_serialized(tmp_path: Path, scenario: str) -> None:
    path = tmp_path / "labels.yaml"
    manager = LabelManager(path)
    first = manager.create("First", ["A", "B"])
    second = manager.create("Second", ["C", "D"])
    untouched = manager.create("Untouched", ["E", "F"])
    action = "create" if scenario == "create" else "update"
    first_name = "First" if scenario == "different_updates" else "Shared"
    second_name = "Second" if scenario == "different_updates" else " shared "
    context = get_context("spawn")
    held, release, attempted, done = (context.Event() for _ in range(4))
    result = context.Queue()
    writer_one = context.Process(
        target=_coordinated_write,
        args=(
            path,
            action,
            first.id,
            first.revision,
            first_name,
            held,
            release,
            result,
        ),
    )
    writer_two = context.Process(
        target=_competing_write,
        args=(
            path,
            action,
            second.id,
            second.revision,
            second_name,
            attempted,
            done,
            result,
        ),
    )
    writer_one.start()
    try:
        assert held.wait(10), "First writer did not reach the protected write"
        writer_two.start()
        assert attempted.wait(10), "Second writer did not attempt the lock"
        assert not done.wait(0.2), "Second writer completed while the lock was held"
    finally:
        release.set()
        writer_one.join(15)
        if writer_two.pid is not None:
            writer_two.join(15)
    assert writer_one.exitcode == 0
    assert writer_two.exitcode == 0
    results = dict(result.get(timeout=5) for _ in range(2))
    assert results == {
        "first": "saved",
        "second": "saved" if scenario == "different_updates" else "validation",
    }
    current = manager.list_sets().sets
    assert next(item for item in current if item.id == untouched.id) == untouched
    if scenario == "different_updates":
        assert [item.revision for item in current] == [2, 2, 1]
    else:
        assert sum(item.name.casefold() == "shared" for item in current) == 1
