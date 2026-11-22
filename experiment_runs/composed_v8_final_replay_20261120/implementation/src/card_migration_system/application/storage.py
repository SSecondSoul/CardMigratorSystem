"""Bounded, non-overwriting byte artifacts; no component execution."""
from hashlib import sha256
import os
from pathlib import Path
import tempfile


class StorageError(ValueError):
    pass


class Storage:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def locate(self, relative):
        if (type(relative) is not str or not relative or "\\" in relative
                or Path(relative).is_absolute() or ".." in Path(relative).parts):
            raise StorageError("invalid_artifact_path")
        path = (self.root / relative).resolve()
        if path == self.root or not path.is_relative_to(self.root):
            raise StorageError("artifact_path_escapes_root")
        return path

    def put(self, relative, content):
        path = self.locate(relative)
        digest = sha256(content).hexdigest()
        if path.exists():
            self.read(relative, digest)
            return digest
        path.parent.mkdir(parents=True, exist_ok=True)
        path = self.locate(relative)
        descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)  # Atomic no-replace on the same filesystem.
            except FileExistsError:
                self.read(relative, digest)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return digest

    def read(self, relative, expected):
        try:
            content = self.locate(relative).read_bytes()
        except OSError as error:
            raise StorageError("artifact_missing") from error
        if sha256(content).hexdigest() != expected:
            raise StorageError("artifact_hash_mismatch")
        return content
