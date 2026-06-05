"""Hashing helpers for USIF structures.

The project uses distinct hashes for distinct purposes:

* ``geometry_hash``: identifies only the structural geometry.
* ``record_hash``: identifies the full logical record, including properties.
* ``payload_digest``: identifies encoded payload bytes.
"""

import hashlib
import json
import math
import struct
from dataclasses import asdict, is_dataclass
from typing import Any

import numpy as np

from usif.constants import BinaryFormat, StorageMode
from usif.structures.structure import USIFStructure


def calculate_geometry_hash(structure: USIFStructure) -> bytes:
    """Calculate the SHA-256 hash of structure geometry only.

    This hash is suitable for geometry lookup, not record-level deduplication.
    """
    data = bytearray()
    data.extend(struct.pack(BinaryFormat.UINT8, structure.structure_type.value))
    data.extend(struct.pack(BinaryFormat.UINT8, structure.storage_mode.value))

    if structure.is_crystal():
        lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
        data.extend(lattice_data)
        data.extend(struct.pack(BinaryFormat.UINT16, structure.spacegroup))
    elif structure.is_molecular() and structure.storage_mode == StorageMode.SYMMETRIC:
        pg_bytes = (structure.point_group or "C1").encode("utf-8")
        data.extend(struct.pack(BinaryFormat.UINT8, len(pg_bytes)))
        data.extend(pg_bytes)

    if structure.storage_mode == StorageMode.SYMMETRIC:
        sites = (
            structure.wyckoff_sites
            if structure.is_crystal()
            else structure.point_group_sites
        )
        data.extend(struct.pack(BinaryFormat.UINT8, len(sites)))
        for site in sites:
            data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
            data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
            data.extend(
                struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *site.coords)
            )
            data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
    else:
        data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
        for site in structure.atom_sites:
            data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
            data.extend(
                struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *site.coords)
            )

    return hashlib.sha256(bytes(data)).digest()


def calculate_payload_digest(payload: bytes) -> bytes:
    """Calculate a SHA-256 digest for encoded payload bytes."""
    return hashlib.sha256(payload).digest()


def _normalize_value(value: Any) -> Any:
    """Convert Python/scientific values to deterministic JSON-compatible data."""
    if value is None or isinstance(value, (str, bool)):
        return value

    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return {"__int__": str(int(value))}

    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if math.isnan(numeric):
            return {"__float__": "nan"}
        if math.isinf(numeric):
            return {"__float__": "inf" if numeric > 0 else "-inf"}
        return {"__float64__": struct.pack(">d", numeric).hex()}

    if isinstance(value, np.ndarray):
        contiguous = np.ascontiguousarray(value)
        return {
            "__ndarray__": True,
            "dtype": str(contiguous.dtype),
            "shape": list(contiguous.shape),
            "data_hex": contiguous.tobytes().hex(),
        }

    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}

    if isinstance(value, tuple):
        return {"__tuple__": [_normalize_value(v) for v in value]}

    if isinstance(value, list):
        return {"__list__": [_normalize_value(v) for v in value]}

    if isinstance(value, set):
        normalized_items = [_normalize_value(v) for v in value]
        return {
            "__set__": sorted(
                normalized_items,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )
        }

    if isinstance(value, dict):
        items = []
        for key, item_value in value.items():
            items.append((_normalize_value(key), _normalize_value(item_value)))
        items.sort(
            key=lambda pair: json.dumps(pair[0], sort_keys=True, separators=(",", ":"))
        )
        return {"__dict__": items}

    if is_dataclass(value):
        return {
            "__dataclass__": f"{value.__class__.__module__}.{value.__class__.__name__}",
            "value": _normalize_value(asdict(value)),
        }

    if hasattr(value, "as_dict"):
        return {
            "__as_dict__": f"{value.__class__.__module__}.{value.__class__.__name__}",
            "value": _normalize_value(value.as_dict()),
        }

    return {
        "__repr__": repr(value),
        "__type__": f"{value.__class__.__module__}.{value.__class__.__name__}",
    }


def _structure_properties_payload(structure: USIFStructure) -> Any:
    props = structure.structure_properties
    return _normalize_value(
        {
            "energy": props.energy,
            "stress": props.stress,
            "volume": props.volume,
            "pressure": props.pressure,
            "temperature": props.temperature,
            "custom": props.custom,
        }
    )


def _atomic_properties_payload(structure: USIFStructure) -> Any:
    if structure.storage_mode != StorageMode.FULL_ATOMIC or not structure.atom_sites:
        return []

    return _normalize_value(
        [
            {
                "atomic_number": site.atomic_number,
                "coords": site.coords,
                "properties": {
                    "force": site.properties.force,
                    "charge": site.properties.charge,
                    "magmom": site.properties.magmom,
                    "velocity": site.properties.velocity,
                    "custom": site.properties.custom,
                },
            }
            for site in structure.atom_sites
        ]
    )


def calculate_record_hash(structure: USIFStructure) -> bytes:
    """Calculate a SHA-256 hash for a complete logical structure record.

    Unlike ``calculate_geometry_hash``, this includes formula, structure-level
    properties, per-atom properties, and custom properties. Containers should use
    this hash for record identity and deduplication.
    """
    payload = {
        "schema": "usif.record_hash.v1",
        "geometry_hash": calculate_geometry_hash(structure).hex(),
        "formula": structure.formula,
        "structure_properties": _structure_properties_payload(structure),
        "atomic_properties": _atomic_properties_payload(structure),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).digest()
