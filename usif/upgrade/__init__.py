"""Readers for files written by USIF 0.8 and earlier.

* :mod:`usif.upgrade.format6`: ``.usif`` records of formats 5 and 6;
* :mod:`usif.upgrade.container_v2`: ``.usifc`` version-2 containers.

Both are frozen and read-only. ``usif.read`` (and so every ``usif`` command)
uses them transparently, and :meth:`usif.dataset.Dataset.import_v2` copies a
container into a dataset.
"""

from usif.upgrade.container_v2 import V2Container, V2Entry, is_container_v2, open_container_v2
from usif.upgrade.format6 import Format6Info, is_format6

__all__ = [
    "Format6Info",
    "V2Container",
    "V2Entry",
    "is_container_v2",
    "is_format6",
    "open_container_v2",
]
