"""USIF exception hierarchy.

::

    USIFError
    ├── ValidationError (ValueError)        invalid model input
    ├── FormatError (ValueError)            malformed or unsupported bytes/documents
    │   ├── ChecksumError                   stored digest does not match the payload
    │   └── UnsupportedVersionError         record/dataset version this reader cannot read
    ├── DatasetError                        dataset file problems (locked, read-only, schema)
    ├── AgentError                          LLM service, agent configuration or change plan problems
    └── MissingDependencyError (ImportError) optional package not installed
"""

from __future__ import annotations

__all__ = [
    "AgentError",
    "ChecksumError",
    "DatasetError",
    "FormatError",
    "MissingDependencyError",
    "USIFError",
    "UnsupportedVersionError",
    "ValidationError",
]


class USIFError(Exception):
    """Base class of every error raised by USIF."""


class ValidationError(USIFError, ValueError):
    """A structure, property or argument is invalid."""


class FormatError(USIFError, ValueError):
    """Bytes or a document are malformed, truncated or exceed a safety limit."""


class ChecksumError(FormatError):
    """A stored digest does not match the data it protects."""


class UnsupportedVersionError(FormatError):
    """The data was written in a version this reader does not support."""


class DatasetError(USIFError):
    """A dataset cannot be opened, written or queried."""


class AgentError(USIFError):
    """The LLM service, the agent configuration or a change plan cannot be used."""


class MissingDependencyError(USIFError, ImportError):
    """An optional dependency needed for the requested operation is not installed."""

    def __init__(self, package: str, purpose: str, extra: str | None = None) -> None:
        hint = f"pip install usif[{extra}]" if extra else f"pip install {package}"
        super().__init__(f"{purpose} requires {package} ({hint})")
        self.package = package
