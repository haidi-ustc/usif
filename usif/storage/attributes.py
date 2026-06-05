"""Typed JSON attribute codec for USIF containers."""

from __future__ import annotations

import json
from typing import Any, Dict

from usif.exceptions import ValidationError


class AttributeCodecMixin:
    """JSON-only metadata codec shared by container and group indexes."""

    @staticmethod
    def _encode_attribute_value(value: Any) -> bytes:
        """Encode container metadata as stable JSON bytes.

        Container and group attributes are intentionally restricted to
        JSON-serializable values so their Python types survive persistence
        instead of being collapsed to strings.
        """
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"Container attributes must be JSON-serializable; got {type(value).__name__}"
            ) from e

    @staticmethod
    def _decode_attribute_value(data: bytes) -> Any:
        """Decode strict JSON metadata bytes.

        Container metadata is a typed JSON contract. Malformed bytes are
        surfaced to callers as index or validation failures.
        """
        return json.loads(data.decode("utf-8"))

    @classmethod
    def _normalise_attributes(cls, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize attributes to JSON round-trip semantics."""
        normalised: Dict[str, Any] = {}
        for attr_name, attr_value in attributes.items():
            if not isinstance(attr_name, str):
                raise ValidationError(
                    f"Container attribute names must be strings; got {type(attr_name).__name__}"
                )
            normalised[attr_name] = cls._decode_attribute_value(
                cls._encode_attribute_value(attr_value)
            )
        return normalised
