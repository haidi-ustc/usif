"""Crash-safe file writing helpers.

Every whole-file write in USIF goes through :func:`atomic_write_bytes` so a
failed encode, an exception, or a crash never leaves a truncated or empty file
in place of a previously valid one.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Union

PathLike = Union[str, "os.PathLike[str]"]


def fsync_directory(directory: Path) -> None:
    """Flush directory metadata so a completed rename survives power loss."""
    if os.name != "posix":
        return
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_bytes(path: PathLike, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically.

    The bytes are written to a temporary file in the destination directory,
    flushed to disk, and moved over ``path`` with :func:`os.replace`. Either the
    old file or the complete new file is visible; never a partial one.
    """
    target = Path(path)
    directory = target.parent if str(target.parent) else Path(".")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    fsync_directory(directory)


def atomic_write_text(path: PathLike, text: str, encoding: str = "utf-8") -> None:
    """Text variant of :func:`atomic_write_bytes`."""
    atomic_write_bytes(path, text.encode(encoding))
