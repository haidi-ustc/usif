"""USIF binary payload codec.

This module owns the structure body layout.  The public ``USIF`` class now
coordinates header/compression/integrity and delegates payload fields here.
"""

import struct
from typing import Optional, Tuple

import numpy as np

from usif.constants import StorageMode, StructureType
from usif.exceptions import CorruptedDataError, DecodingError, EncodingError, ValidationError
from usif.format.binary.limits import (
    MAX_ATOM_COUNT,
    MAX_PAYLOAD_SIZE,
    MAX_PROPERTY_SECTION_SIZE,
    MAX_STRING_LENGTH,
    MAX_SYMMETRIC_SITE_COUNT,
)
from usif.format.binary.property_codec import PropertyCodec
from usif.format.binary.reader import BinaryReader
from usif.format.binary.writer import BinaryWriter
from usif.properties.atomic import AtomicProperties
from usif.properties.registry import DEFAULT_REGISTRY
from usif.properties.structure import StructureProperties
from usif.structures.sites import AtomSite, PointGroupSite, WyckoffSite
from usif.structures.structure import USIFStructure


class StructureBinaryCodec:
    """Encode and decode the compressed USIF payload body."""

    def __init__(self, property_registry=None):
        self.property_registry = property_registry or DEFAULT_REGISTRY
        self.property_codec = PropertyCodec(self.property_registry)

    @staticmethod
    def json_default(value):
        return PropertyCodec._json_default(value)

    @staticmethod
    def encode_custom_value(value) -> bytes:
        return PropertyCodec.encode_custom_value(value)

    @staticmethod
    def decode_custom_value(value_str):
        return PropertyCodec.decode_custom_value(value_str)

    def encode_atomic_properties(
        self, props: AtomicProperties, num_atoms: Optional[int] = None
    ) -> bytes:
        return self.property_codec.encode_atomic_properties(props, num_atoms=num_atoms)

    def decode_atomic_properties(
        self, data: bytes, offset: int, num_atoms: Optional[int] = None
    ) -> Tuple[AtomicProperties, int]:
        return self.property_codec.decode_atomic_properties(
            data, offset, num_atoms=num_atoms
        )

    def encode_structure_properties(self, props: StructureProperties) -> bytes:
        return self.property_codec.encode_structure_properties(props)

    def decode_structure_properties(
        self, data: bytes, offset: int
    ) -> Tuple[StructureProperties, int]:
        return self.property_codec.decode_structure_properties(data, offset)

    def encode_body(self, structure: USIFStructure) -> bytes:
        """Encode a structure into an uncompressed USIF payload."""
        try:
            writer = BinaryWriter()
            writer.write_u8(structure.structure_type.value, "structure type")
            writer.write_u8(structure.storage_mode.value, "storage mode")

            if structure.structure_type == StructureType.MOLECULE:
                self._encode_molecule_body(writer, structure)
            else:
                self._encode_crystal_body(writer, structure)

            struct_prop_data = self.encode_structure_properties(
                structure.structure_properties
            )
            if len(struct_prop_data) > MAX_PROPERTY_SECTION_SIZE:
                raise EncodingError(
                    "Structure property section length "
                    f"{len(struct_prop_data)} exceeds maximum {MAX_PROPERTY_SECTION_SIZE}"
                )
            writer.write_u32(len(struct_prop_data), "structure property section length")
            writer.extend(struct_prop_data)
            writer.write_string_u16(structure.formula, "formula")

            payload = bytes(writer)
            if len(payload) > MAX_PAYLOAD_SIZE:
                raise EncodingError(
                    f"Raw payload size {len(payload)} exceeds maximum {MAX_PAYLOAD_SIZE}"
                )
            return payload
        except (EncodingError, ValidationError):
            raise
        except (ValueError, TypeError, struct.error) as exc:
            raise EncodingError(f"Failed to encode structure body: {exc}") from exc

    def _encode_molecule_body(self, writer: BinaryWriter, structure: USIFStructure) -> None:
        if structure.storage_mode == StorageMode.SYMMETRIC:
            point_group = structure.point_group or "C1"
            writer.write_string_u8(point_group, "point group")
            writer.write_u8(len(structure.point_group_sites), "point-group site count")
            for site in structure.point_group_sites:
                writer.write_u8(site.atomic_number, "point-group atomic number")
                writer.write_u16(site.multiplicity, "point-group multiplicity")
                writer.write_f32_tuple3(site.coords, "point-group coords")
                writer.write_f32(site.occupancy, "point-group occupancy")
        else:
            writer.write_u32(len(structure.atom_sites), "atom count")
            for site in structure.atom_sites:
                writer.write_u8(site.atomic_number, "atomic number")
                writer.write_f32_tuple3(site.coords, "atom coords")
                writer.extend(self.encode_atomic_properties(site.properties, num_atoms=1))

    def _encode_crystal_body(self, writer: BinaryWriter, structure: USIFStructure) -> None:
        lattice_array = np.asarray(structure.lattice_matrix, dtype=np.float32)
        if lattice_array.shape != (3, 3):
            raise EncodingError(
                f"lattice_matrix must have shape (3, 3), got {lattice_array.shape}"
            )
        writer.extend(lattice_array.tobytes())
        writer.write_u16(structure.spacegroup, "space group")

        if structure.storage_mode == StorageMode.SYMMETRIC:
            writer.write_u8(len(structure.wyckoff_sites), "wyckoff site count")
            for site in structure.wyckoff_sites:
                writer.write_u8(site.atomic_number, "wyckoff atomic number")
                writer.write_u16(site.multiplicity, "wyckoff multiplicity")
                writer.write_f32_tuple3(site.coords, "wyckoff coords")
                writer.write_f32(site.occupancy, "wyckoff occupancy")
        else:
            writer.write_u32(len(structure.atom_sites), "atom count")
            for site in structure.atom_sites:
                writer.write_u8(site.atomic_number, "atomic number")
                writer.write_f32_tuple3(site.coords, "atom coords")
                writer.extend(self.encode_atomic_properties(site.properties, num_atoms=1))

    def decode_body(self, payload: bytes) -> USIFStructure:
        """Decode an uncompressed USIF payload into a structure."""
        try:
            reader = BinaryReader(payload, context="USIF payload")
            try:
                structure_type = StructureType(reader.read_u8("structure type"))
                storage_mode = StorageMode(reader.read_u8("storage mode"))
            except ValueError as exc:
                raise CorruptedDataError(
                    f"Invalid structure type or storage mode: {exc}"
                ) from exc

            if structure_type == StructureType.MOLECULE:
                kwargs = self._decode_molecule_body(reader, payload, storage_mode)
            else:
                kwargs = self._decode_crystal_body(reader, payload, storage_mode)

            struct_props = self._decode_structure_property_section(reader)
            formula = self._decode_formula(reader)
            reader.assert_consumed("USIF payload")

            if structure_type == StructureType.MOLECULE:
                return USIFStructure(
                    structure_type=structure_type,
                    storage_mode=storage_mode,
                    structure_properties=struct_props,
                    formula=formula,
                    **kwargs,
                )
            return USIFStructure(
                structure_type=structure_type,
                storage_mode=storage_mode,
                structure_properties=struct_props,
                formula=formula,
                **kwargs,
            )
        except (DecodingError, CorruptedDataError, ValidationError):
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise DecodingError(f"Failed to decode structure body: {exc}") from exc

    def _decode_molecule_body(self, reader, payload, storage_mode):
        if storage_mode == StorageMode.SYMMETRIC:
            point_group = reader.read_string_u8("point group")
            num_sites = reader.read_u8("point-group site count")
            if num_sites > MAX_SYMMETRIC_SITE_COUNT:
                raise CorruptedDataError(
                    f"Point-group site count {num_sites} exceeds maximum {MAX_SYMMETRIC_SITE_COUNT}"
                )
            point_group_sites = []
            for _ in range(num_sites):
                atomic_num = reader.read_u8("point-group atomic number")
                mult = reader.read_u16("point-group multiplicity")
                coords = reader.read_f32_tuple3("point-group coords")
                occupancy = reader.read_f32("point-group occupancy")
                point_group_sites.append(PointGroupSite(atomic_num, mult, coords, occupancy))
            return {"point_group": point_group, "point_group_sites": point_group_sites, "atom_sites": None}

        num_atoms = reader.read_u32("atom count")
        if num_atoms > MAX_ATOM_COUNT:
            raise CorruptedDataError(
                f"Atom count {num_atoms} exceeds maximum {MAX_ATOM_COUNT}"
            )
        atom_sites = []
        for _ in range(num_atoms):
            atomic_num = reader.read_u8("atomic number")
            coords = reader.read_f32_tuple3("atom coords")
            atom_props, new_offset = self.decode_atomic_properties(
                payload, reader.tell(), num_atoms=1
            )
            reader.seek(new_offset)
            atom_sites.append(AtomSite(atomic_num, coords, atom_props))
        return {"point_group": None, "point_group_sites": None, "atom_sites": atom_sites}

    def _decode_crystal_body(self, reader, payload, storage_mode):
        lattice_data = reader.read_bytes(36, "lattice matrix")
        lattice_matrix = np.frombuffer(lattice_data, dtype=np.float32).reshape(3, 3)
        spacegroup = reader.read_u16("space group")

        if storage_mode == StorageMode.SYMMETRIC:
            num_sites = reader.read_u8("wyckoff site count")
            if num_sites > MAX_SYMMETRIC_SITE_COUNT:
                raise CorruptedDataError(
                    f"Wyckoff site count {num_sites} exceeds maximum {MAX_SYMMETRIC_SITE_COUNT}"
                )
            wyckoff_sites = []
            for _ in range(num_sites):
                atomic_num = reader.read_u8("wyckoff atomic number")
                mult = reader.read_u16("wyckoff multiplicity")
                coords = reader.read_f32_tuple3("wyckoff coords")
                occupancy = reader.read_f32("wyckoff occupancy")
                wyckoff_sites.append(WyckoffSite(atomic_num, mult, coords, occupancy))
            return {
                "lattice_matrix": lattice_matrix,
                "spacegroup": spacegroup,
                "wyckoff_sites": wyckoff_sites,
                "atom_sites": None,
            }

        num_atoms = reader.read_u32("atom count")
        if num_atoms > MAX_ATOM_COUNT:
            raise CorruptedDataError(
                f"Atom count {num_atoms} exceeds maximum {MAX_ATOM_COUNT}"
            )
        atom_sites = []
        for _ in range(num_atoms):
            atomic_num = reader.read_u8("atomic number")
            coords = reader.read_f32_tuple3("atom coords")
            atom_props, new_offset = self.decode_atomic_properties(
                payload, reader.tell(), num_atoms=1
            )
            reader.seek(new_offset)
            atom_sites.append(AtomSite(atomic_num, coords, atom_props))
        return {
            "lattice_matrix": lattice_matrix,
            "spacegroup": spacegroup,
            "wyckoff_sites": None,
            "atom_sites": atom_sites,
        }

    def _decode_structure_property_section(self, reader: BinaryReader) -> StructureProperties:
        props_len = reader.read_u32("structure property section length")
        if props_len > MAX_PROPERTY_SECTION_SIZE:
            raise CorruptedDataError(
                "Structure property section length "
                f"{props_len} exceeds maximum {MAX_PROPERTY_SECTION_SIZE}"
            )
        props_payload = reader.read_bytes(props_len, "structure property section")
        struct_props, props_offset = self.decode_structure_properties(props_payload, 0)
        if props_offset != len(props_payload):
            raise CorruptedDataError(
                "Structure property section was not consumed exactly: "
                f"decoded {props_offset} of {len(props_payload)} bytes"
            )
        return struct_props

    def _decode_formula(self, reader: BinaryReader) -> str:
        formula_len = reader.read_u16("formula length")
        if formula_len > MAX_STRING_LENGTH:
            raise CorruptedDataError(
                f"Formula length {formula_len} exceeds maximum {MAX_STRING_LENGTH}"
            )
        return reader.read_string(formula_len, "formula")
