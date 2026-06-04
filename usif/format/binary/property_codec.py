"""Binary property codec facade.

The historical implementation lives in :mod:`usif.format.properties`.  This
module gives the binary codec layer its own import boundary while preserving
that implementation and API.
"""

from usif.format.properties import PropertyCodec

__all__ = ["PropertyCodec"]
