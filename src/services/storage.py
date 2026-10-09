import hashlib
import os
import re
from pathlib import Path

from src.errors import InputError

FILE_ID = re.compile(r"[0-9a-f]{32}\.(?:csv|tsv|xlsx|parquet)")


class FileStorage:
    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve() / "files"

    def path(self, file_id: str) -> Path:
        if not FILE_ID.fullmatch(file_id):
            raise InputError("storage_unavailable", "Stored file identity is invalid.", 503)
        return self.directory / file_id

    def publish(self, file_id: str, content: bytes) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.path(file_id)
        pending = destination.with_suffix(".pending")
        with pending.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Link publication is atomic and cannot overwrite an immutable file.
        os.link(pending, destination)
        pending.unlink()

    def read(self, file_id: str, expected_hash: str) -> bytes:
        content = self.path(file_id).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise InputError("file_integrity_error", "Stored file content does not match its hash.", 503)
        return content

    def reconcile(self, referenced_files: set[str]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        for path in self.directory.iterdir():
            managed = FILE_ID.fullmatch(path.name) or re.fullmatch(r"[0-9a-f]{32}\.pending", path.name)
            if managed and path.name not in referenced_files:
                path.unlink()

