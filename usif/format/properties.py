"""Property encoding helpers for USIF binary payloads."""

import json
import logging
import struct
from typing import Optional, Tuple

import numpy as np

from usif.constants import BinaryFormat
from usif.exceptions import DecodingError
from usif.properties.atomic import AtomicProperties
from usif.properties.registry import PropertyRegistry
from usif.properties.serializer import PropertySerializer
from usif.properties.structure import StructureProperties

logger = logging.getLogger(__name__)
CUSTOM_JSON_PREFIX = "__USIF_JSON__:"


class PropertyCodec:
    """Encode and decode structure and atomic properties with an injectable registry."""

    def __init__(self, registry=PropertyRegistry):
        self.registry = registry

    @staticmethod
    def _json_default(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        return str(value)

    @classmethod
    def encode_custom_value(cls, value) -> bytes:
        payload = json.dumps(value, default=cls._json_default, separators=(",", ":"))
        return (CUSTOM_JSON_PREFIX + payload).encode("utf-8")

    @staticmethod
    def decode_custom_value(value_str):
        if not value_str.startswith(CUSTOM_JSON_PREFIX):
            return value_str
        payload = value_str[len(CUSTOM_JSON_PREFIX) :]
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Failed to decode custom JSON payload; returning raw string")
            return value_str

    def encode_atomic_properties(
        self, props: AtomicProperties, num_atoms: Optional[int] = None
    ) -> bytes:
        return self._encode_properties(props, atomic_only=True, num_atoms=num_atoms)

    def decode_atomic_properties(
        self, data: bytes, offset: int, num_atoms: Optional[int] = None
    ) -> Tuple[AtomicProperties, int]:
        return self._decode_properties(
            AtomicProperties(), data, offset, num_atoms=num_atoms
        )

    def encode_structure_properties(self, props: StructureProperties) -> bytes:
        return self._encode_properties(props, structure_only=True)

    def decode_structure_properties(
        self, data: bytes, offset: int
    ) -> Tuple[StructureProperties, int]:
        return self._decode_properties(StructureProperties(), data, offset)

    def _encode_properties(
        self,
        props,
        atomic_only: bool = False,
        structure_only: bool = False,
        num_atoms: Optional[int] = None,
    ) -> bytes:
        data = bytearray()
        all_props = props.get_all_properties()
        known_props = self.registry.list_properties(
            atomic_only=atomic_only, structure_only=structure_only
        )

        present_props = [p for p in known_props if p in all_props]
        data.extend(struct.pack(BinaryFormat.UINT8, len(present_props)))

        for prop_name in present_props:
            prop_def = self.registry.get(prop_name)
            if prop_def is None:
                continue

            name_bytes = prop_name.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)

            prop_data = PropertySerializer.serialize_value(
                all_props[prop_name], prop_def, num_atoms
            )
            data.extend(struct.pack(BinaryFormat.UINT32, len(prop_data)))
            data.extend(prop_data)

        built_in_props = set(self.registry.list_properties())
        custom_props = {k: v for k, v in all_props.items() if k not in built_in_props}
        data.extend(struct.pack(BinaryFormat.UINT8, len(custom_props)))

        for custom_name, custom_value in custom_props.items():
            name_bytes = custom_name.encode("utf-8")
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)

            value_bytes = self.encode_custom_value(custom_value)
            data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
            data.extend(value_bytes)

        return bytes(data)

    def _decode_properties(
        self, props, data: bytes, offset: int, num_atoms: Optional[int] = None
    ):
        try:
            num_props = struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[0]
            offset += 1

            for _ in range(num_props):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[
                    0
                ]
                offset += 1
                prop_name = data[offset : offset + name_len].decode("utf-8")
                offset += name_len

                data_len = struct.unpack(
                    BinaryFormat.UINT32, data[offset : offset + 4]
                )[0]
                offset += 4

                prop_def = self.registry.get(prop_name)
                if prop_def is None:
                    offset += data_len
                    continue

                prop_value, offset = PropertySerializer.deserialize_value(
                    prop_def, data, offset, num_atoms
                )

                if hasattr(props, prop_name):
                    setattr(props, prop_name, prop_value)
                else:
                    props.custom[prop_name] = prop_value

            num_custom = struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[0]
            offset += 1

            for _ in range(num_custom):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset : offset + 1])[
                    0
                ]
                offset += 1
                custom_name = data[offset : offset + name_len].decode("utf-8")
                offset += name_len

                value_len = struct.unpack(
                    BinaryFormat.UINT32, data[offset : offset + 4]
                )[0]
                offset += 4
                value_str = data[offset : offset + value_len].decode("utf-8")
                offset += value_len

                props.custom[custom_name] = self.decode_custom_value(value_str)

            return props, offset
        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(
                f"Failed to decode properties at offset {offset}: {e}"
            ) from e
