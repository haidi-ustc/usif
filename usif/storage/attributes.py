"""Typed JSON attribute codec for USIF containers."""

from __future__ import annotations

import json
from typing import Any, Dict

from usif.exceptions import ValidationError

# Index fields are length-prefixed: strings and per-structure attribute counts
# with uint16, attribute values with uint32.
MAX_INDEX_TEXT_BYTES = 0xFFFF
MAX_INDEX_ENTRIES_U16 = 0xFFFF
MAX_ATTRIBUTE_VALUE_BYTES = 0xFFFFFFFF


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

    @staticmethod
    def _validate_index_text(value: Any, what: str) -> str:
        """Check that ``value`` fits a uint16 length-prefixed UTF-8 index field.

        Validation happens when data enters the container so the index can
        always be persisted later; a failure at ``close()`` would lose the
        whole session's index.
        """
        if not isinstance(value, str):
            raise ValidationError(f"{what} must be a string; got {type(value).__name__}")
        if len(value.encode("utf-8")) > MAX_INDEX_TEXT_BYTES:
            raise ValidationError(
                f"{what} is longer than {MAX_INDEX_TEXT_BYTES} UTF-8 bytes"
            )
        return value

    @classmethod
    def _normalise_attribute_value(cls, value: Any) -> Any:
        """Return ``value`` with JSON round-trip semantics, or raise ValidationError."""
        encoded = cls._encode_attribute_value(value)
        if len(encoded) > MAX_ATTRIBUTE_VALUE_BYTES:
            raise ValidationError("Container attribute value is too large to persist")
        return cls._decode_attribute_value(encoded)

    @classmethod
    def _normalise_attributes(cls, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize attributes to JSON round-trip semantics."""
        if not isinstance(attributes, dict):
            raise ValidationError(
                f"Container attributes must be a dict; got {type(attributes).__name__}"
            )
        if len(attributes) > MAX_INDEX_ENTRIES_U16:
            raise ValidationError(
                f"At most {MAX_INDEX_ENTRIES_U16} attributes are supported per structure"
            )
        normalised: Dict[str, Any] = {}
        for attr_name, attr_value in attributes.items():
            cls._validate_index_text(attr_name, "Container attribute name")
            normalised[attr_name] = cls._normalise_attribute_value(attr_value)
        return normalised
