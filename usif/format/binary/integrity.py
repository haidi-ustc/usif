"""Integrity helpers for USIF binary codec."""

import logging

from usif.exceptions import IntegrityError
from usif.format.hashing import calculate_geometry_hash

logger = logging.getLogger(__name__)


def validate_geometry_hash(structure, expected_hash: bytes, *, strict: bool = True) -> None:
    """Validate the decoded structure against the header geometry hash."""
    actual_hash = calculate_geometry_hash(structure)
    if expected_hash == actual_hash:
        return

    message = (
        "USIF integrity check failed: header geometry hash "
        f"{expected_hash.hex()} != decoded geometry hash {actual_hash.hex()}"
    )
    if strict:
        raise IntegrityError(message)
    logger.warning(message)
