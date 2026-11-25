"""Fixed operator entry point for a private, dated static export."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from . import archive, projection, render
from . import contract as c
from .archive import Budget, Directory
from .contract import Refusal, fail, require


@dataclass(frozen=True)
class Delivery:
    code: int
    line: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _failure(reason: str) -> Delivery:
    if reason in c.OUTPUT_FAILURES:
        return Delivery(4, "FAILED " + reason)
    if reason == "INVALID_INVOCATION":
        return Delivery(2, "UNAVAILABLE " + reason)
    return Delivery(3 if reason in c.FAILED else 2, c.refusal_status(reason) + " " + reason)


def _require_absent(directory: Directory, leaf: str) -> None:
    try:
        os.stat(leaf, dir_fd=directory.fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    fail("UNSAFE_OUTPUT")


def _remove_own_staging(directory: Directory, st: os.stat_result) -> None:
    try:
        named = os.stat("page.part", dir_fd=directory.fd, follow_symlinks=False)
        if (named.st_dev, named.st_ino) == (st.st_dev, st.st_ino):
            os.unlink("page.part", dir_fd=directory.fd)
    except OSError:
        return


def _publish(
    output: Directory,
    snapshot_id: str,
    body: bytes,
    budget: Budget,
    recheck_input: Callable[[], None],
) -> str:
    require(len(body) <= c.MAX_HTML, "BOUNDS_EXCEEDED")
    budget.check()
    output.recheck("UNSAFE_OUTPUT")
    leaf = "snapshot-" + c.text(snapshot_id, c.HEX64)
    try:
        # An exclusive fresh leaf ensures earlier snapshots stay disjoint.
        os.mkdir(leaf, 0o700, dir_fd=output.fd)
    except FileExistsError:
        fail("UNSAFE_OUTPUT")
    except OSError:
        fail("OUTPUT_IO")
    with ExitStack() as stack:
        folder = archive.open_directory(stack, output, leaf, "UNSAFE_OUTPUT", private=True)
        st: os.stat_result | None = None
        published = False
        try:
            fd = os.open(
                "page.part",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=folder.fd,
            )
            stack.callback(os.close, fd)
            st = os.fstat(fd)
            require(
                stat.S_ISREG(st.st_mode)
                and st.st_nlink == 1
                and st.st_uid == os.getuid()
                and stat.S_IMODE(st.st_mode) == 0o600,
                "UNSAFE_OUTPUT",
            )
            position = 0
            while position < len(body):
                budget.check()
                written = os.write(fd, body[position : position + archive.CHUNK])
                require(written > 0, "OUTPUT_IO")
                position += written
            os.fsync(fd)
            recheck_input()
            folder.recheck("UNSAFE_OUTPUT")
            current = os.fstat(fd)
            named = os.stat("page.part", dir_fd=folder.fd, follow_symlinks=False)
            require(
                archive.file_identity(named) == archive.file_identity(current)
                and current.st_nlink == 1
                and current.st_size == len(body),
                "UNSAFE_OUTPUT",
            )
            _require_absent(folder, "index.html")
            budget.check()
            os.rename("page.part", "index.html", src_dir_fd=folder.fd, dst_dir_fd=folder.fd)
            published = True
        except OSError:
            fail("OUTPUT_IO")
        finally:
            if st is not None and not published:
                _remove_own_staging(folder, st)
    return f"{leaf}/index.html"


def _attempt(build: str, output: Directory, app: Directory, budget: Budget) -> Delivery:
    attempt = str(uuid4())
    validation = "NOT_RUN"
    try:
        release = archive._gate(archive._RELEASE, c.EDITION)
        with ExitStack() as selection:
            custody = archive.open_directory(
                selection,
                app,
                "custody",
                "UNSAFE_INPUT",
                private=True,
                missing="ARCHIVE_MISSING",
            )
            require(custody.identity[:2] != output.identity[:2], "UNSAFE_OUTPUT")
            validation = "FAILED"
            source = archive.open_input(selection, custody, release, budget)
            try:
                checked = archive._inspect(source.raw, release, budget)
            except (KeyError, TypeError, ValueError, IndexError):
                fail("UNSUPPORTED_SCHEMA")
            validated_at = _now()
            validation = "PASSED_NO_DISCLOSURE"
            budget.check()
            view = projection.historical(checked, build, attempt, validated_at, _now())
            body = render.static_html(view)
            location = _publish(output, view["snapshot_id"], body, budget, source.recheck)
        return Delivery(0, "AVAILABLE_HISTORICAL " + location)
    except Refusal as error:
        if error.code in c.OUTPUT_FAILURES:
            return _failure(error.code)
        if error.code in ("ARCHIVE_MISSING", "EDITION_WITHHELD") and validation == "FAILED":
            validation = "NOT_RUN"
        refusal = _failure(error.code)
        try:
            view = projection.refusal(error.code, validation, build, attempt, _now())
            body = render.static_html(view)
            location = _publish(output, view["snapshot_id"], body, budget, lambda: None)
        except Refusal as publication:
            return _failure(publication.code)
        return Delivery(refusal.code, refusal.line + " REFUSAL_PAGE " + location)


def _export(home: Path) -> Delivery:
    budget = Budget()
    try:
        build = archive.build_identity()
        with ExitStack() as stack:
            app = archive.open_application(stack, home)
            output = archive.open_directory(stack, app, "snapshots", "UNSAFE_OUTPUT", private=True)
            return _attempt(build, output, app, budget)
    except Refusal as error:
        return _failure(error.code)
    except OSError:
        return _failure("OUTPUT_IO")


def _deliver(result: Delivery) -> int:
    message = (result.line + "\n").encode("ascii")
    try:
        # One small write, with no buffered retry or exception echo at interpreter exit.
        if os.write(1 if result.code == 0 else 2, message) != len(message):
            return 4
    except OSError:
        return 4
    return result.code


def main(args: Sequence[str] | None = None) -> int:
    if sys.argv[1:] if args is None else args:
        return _deliver(_failure("INVALID_INVOCATION"))
    try:
        os.write(2, b"VALIDATING\n")
        home = archive.account_home()
    except Refusal as error:
        return _deliver(_failure(error.code))
    except OSError:
        return 4
    return _deliver(_export(home))


if __name__ == "__main__":
    raise SystemExit(main())
