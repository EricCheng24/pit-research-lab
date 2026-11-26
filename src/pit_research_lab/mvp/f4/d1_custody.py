"""Private fixture custody with fsync, no-clobber publication and bounded recovery."""

import ctypes
import errno
import fcntl
import os
import stat
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .d1_profile import (
    LIMIT,
    Refusal,
    hex_digest,
    private_read,
    private_root,
    require,
    sha,
)


@contextmanager
def directory(path: Path, *, create: bool = False) -> Iterator[int]:
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        else:
            fd = os.open(path.parent, os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    private_root(path)
    fd = os.open(path, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def custody_lock(
    root: Path, *, budget: float = 5, on_contention: Callable[[], None] | None = None
) -> Iterator[None]:
    with directory(root) as parent:
        fd = os.open(
            ".f4-custody.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=parent,
        )
        try:
            info = os.fstat(fd)
            require(
                stat.S_ISREG(info.st_mode)
                and info.st_uid == os.geteuid()
                and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600,
                "UNSAFE_CUSTODY_LOCK",
            )
            deadline = time.monotonic() + budget
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if on_contention is not None:
                        on_contention()
                    if time.monotonic() >= deadline:
                        raise Refusal("CUSTODY_LOCK_TIMEOUT") from None
                    time.sleep(0.02)
            yield
        finally:
            os.close(fd)


def rename_exclusive(parent: int, before: str, after: str) -> None:
    # WSL/Linux renameat2 avoids the multi-link crash window of link/unlink.
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(before), parent, os.fsencode(after), 1) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise FileExistsError(error, "Destination exists")
        raise OSError(error, "No-clobber publication unavailable")


def publish(path: Path, raw: bytes) -> None:
    with directory(path.parent) as parent:
        temporary = f".stage-{uuid4()}"
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        renamed = False
        try:
            with os.fdopen(fd, "wb") as opened:
                opened.write(raw)
                opened.flush()
                os.fsync(opened.fileno())
            rename_exclusive(parent, temporary, path.name)
            renamed = True
            os.fsync(parent)
        finally:
            if not renamed:
                os.unlink(temporary, dir_fd=parent)


def blob_path(root: Path, digest: str) -> Path:
    require(hex_digest(digest), "INVALID_ARTIFACT_DIGEST")
    return root / "sha256" / digest[:2] / digest


def read_blob(root: Path, digest: str, size: int) -> bytes:
    path = blob_path(root, digest)
    try:
        body = private_read(path, LIMIT)
    except (OSError, Refusal):
        raise Refusal("MISSING_OR_UNSAFE_ARTIFACT") from None
    require(len(body) == size and sha(body) == digest, "ARTIFACT_INTEGRITY_FAILURE")
    return body


def put_blob(root: Path, body: bytes) -> tuple[str, int]:
    require(0 < len(body) <= LIMIT, "ARTIFACT_SIZE_LIMIT")
    digest, size = sha(body), len(body)
    path = blob_path(root, digest)
    with (
        directory(path.parent.parent, create=True),
        directory(path.parent, create=True),
    ):
        try:
            publish(path, body)
        except FileExistsError:
            pass
    require(read_blob(root, digest, size) == body, "ARTIFACT_PREIMAGE_MISMATCH")
    return digest, size
