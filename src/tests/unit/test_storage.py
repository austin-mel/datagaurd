import hashlib
from pathlib import Path

import pytest

from src.errors import InputError
from src.services.storage import FileStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def storage(tmp_path: Path) -> FileStorage:
    return FileStorage(tmp_path)


@pytest.mark.parametrize("extension", ["csv", "tsv", "xlsx", "parquet"])
def test_atomic_publish_and_verified_read(storage: FileStorage, extension: str) -> None:
    identity = "a" * 32 + "." + extension
    content = b"id,value\n1,\x00\xff"
    storage.publish(identity, content)
    assert storage.read(identity, hashlib.sha256(content).hexdigest()) == content
    assert list(storage.directory.iterdir()) == [storage.path(identity)]


@pytest.mark.parametrize("identity", [
    "", "../outside.csv", "..\\outside.csv", "C:\\outside.csv", "/tmp/outside.csv",
    "a" * 31 + ".csv", "A" * 32 + ".csv", "g" * 32 + ".csv", "a" * 32 + ".exe",
    "a" * 32 + ".csv/other", "a" * 32 + ".csv\n",
])
def test_file_identity_is_restricted(storage: FileStorage, identity: str) -> None:
    with pytest.raises(InputError) as caught:
        storage.path(identity)
    assert caught.value.code == "storage_unavailable"
    assert caught.value.status_code == 503


def test_publish_never_overwrites_existing_content(storage: FileStorage) -> None:
    identity = "a" * 32 + ".csv"
    storage.publish(identity, b"original")
    with pytest.raises(FileExistsError):
        storage.publish(identity, b"replacement")
    assert storage.path(identity).read_bytes() == b"original"
    storage.reconcile({identity})
    assert list(storage.directory.iterdir()) == [storage.path(identity)]


def test_read_detects_tampering(storage: FileStorage) -> None:
    identity = "a" * 32 + ".csv"
    storage.publish(identity, b"tampered")
    with pytest.raises(InputError) as caught:
        storage.read(identity, hashlib.sha256(b"original").hexdigest())
    assert caught.value.code == "file_integrity_error"
    assert caught.value.status_code == 503


def test_missing_file_is_not_returned_as_empty(storage: FileStorage) -> None:
    with pytest.raises(FileNotFoundError):
        storage.read("a" * 32 + ".csv", hashlib.sha256(b"").hexdigest())


def test_reconcile_preserves_references_and_unmanaged_files(storage: FileStorage) -> None:
    keep, orphan = "a" * 32 + ".csv", "b" * 32 + ".xlsx"
    storage.publish(keep, b"keep")
    storage.publish(orphan, b"orphan")
    (storage.directory / ("c" * 32 + ".pending")).write_bytes(b"partial")
    (storage.directory / "notes.txt").write_text("user file", encoding="utf-8")
    (storage.directory / "unmanaged").mkdir()
    storage.reconcile({keep})
    assert {path.name for path in storage.directory.iterdir()} == {keep, "notes.txt", "unmanaged"}
    storage.reconcile({keep})
    assert storage.path(keep).read_bytes() == b"keep"


def test_failed_publication_leaves_recoverable_pending_file(storage: FileStorage, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_link(source: Path, destination: Path) -> None:
        raise OSError("publication interrupted")

    monkeypatch.setattr("src.services.storage.os.link", fail_link)
    identity = "a" * 32 + ".csv"
    with pytest.raises(OSError, match="publication interrupted"):
        storage.publish(identity, b"data")
    assert not storage.path(identity).exists()
    assert storage.path(identity).with_suffix(".pending").read_bytes() == b"data"
    storage.reconcile(set())
    assert list(storage.directory.iterdir()) == []
