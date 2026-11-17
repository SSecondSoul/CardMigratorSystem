"""Local OS lock fences graph execution, migrations and backup (not a network lock)."""
from contextlib import contextmanager
import os


class RuntimeBusyError(ValueError):
    pass


@contextmanager
def execution_guard(runtime):
    # Keep the inode/file: unlinking a lock file would break process exclusion.
    with (runtime / ".execution.lock").open("a+b") as stream:
        try:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeBusyError("runtime_in_use") from error
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
