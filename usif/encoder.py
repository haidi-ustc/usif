#!/usr/bin/env python3
"""
USIF Encoder/Decoder
Main encoder and decoder for USIF format
"""

import struct
import hashlib
import gzip
import logging
import numpy as np
from typing import Optional, Tuple, Union
from pathlib import Path

from usif.constants import BinaryFormat

logger = logging.getLogger(__name__)
from usif.enums import CompressionType, StructureType, StorageMode
from usif.exceptions import EncodingError, DecodingError, CorruptedDataError, ValidationError
from usif.structures.structure import USIFStructure
from usif.structures.sites import WyckoffSite, PointGroupSite, AtomSite
from usif.properties.serializer import PropertySerializer
from usif.properties.registry import PropertyRegistry
from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties

class USIF:
    """USIF (Universal Structure Interchange Format) Encoder/Decoder"""
    
    VERSION = 4
    HEADER_SIZE = 64
    
    def __init__(self, compression: CompressionType = CompressionType.GZIP):
        self.compression = compression
    
    def _calculate_hash(self, structure: USIFStructure) -> bytes:
        """Calculate SHA-256 hash of structure"""
        data = bytearray()
        data.extend(struct.pack(BinaryFormat.UINT8, structure.structure_type.value))
        data.extend(struct.pack(BinaryFormat.UINT8, structure.storage_mode.value))
        
        if structure.is_crystal():
            lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
            data.extend(lattice_data)
            data.extend(struct.pack(BinaryFormat.UINT16, structure.spacegroup))
        elif structure.is_molecular() and structure.storage_mode == StorageMode.SYMMETRIC:
            pg_bytes = (structure.point_group or "C1").encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(pg_bytes)))
            data.extend(pg_bytes)
        
        if structure.storage_mode == StorageMode.SYMMETRIC:
            if structure.is_crystal():
                data.extend(struct.pack(BinaryFormat.UINT8, len(structure.wyckoff_sites)))
                for site in structure.wyckoff_sites:
                    data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                    coords = tuple(round(c, 5) for c in site.coords)
                    data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *coords))
            else:
                data.extend(struct.pack(BinaryFormat.UINT8, len(structure.point_group_sites)))
                for site in structure.point_group_sites:
                    data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                    coords = tuple(round(c, 5) for c in site.coords)
                    data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *coords))
        else:
            data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
            for site in structure.atom_sites:
                data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                coords = tuple(round(c, 5) for c in site.coords)
                data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), *coords))
        
        return hashlib.sha256(bytes(data)).digest()
    
    def _compress_data(self, data: bytes) -> bytes:
        """Compress data based on compression type"""
        try:
            if self.compression == CompressionType.GZIP:
                return gzip.compress(data, compresslevel=6)
            return data
        except (OSError, MemoryError) as e:
            raise EncodingError(f"Compression failed: {e}") from e
    
    def _decompress_data(self, data: bytes, comp_type: CompressionType) -> bytes:
        """Decompress data based on compression type"""
        try:
            if comp_type == CompressionType.GZIP:
                return gzip.decompress(data)
            return data
        except gzip.BadGzipFile as e:
            raise CorruptedDataError(f"Corrupted gzip data: {e}") from e
        except Exception as e:
            raise DecodingError(f"Decompression failed: {e}") from e
    
    def _encode_atomic_properties(self, props: AtomicProperties, 
                                  num_atoms: Optional[int] = None) -> bytes:
        """Encode atomic properties using modular system"""
        data = bytearray()
        
        all_props = props.get_all_properties()
        built_in_props = list(PropertyRegistry._properties.keys())
        atomic_props = [p for p in built_in_props if PropertyRegistry.is_atomic_property(p)]
        
        present_props = [p for p in atomic_props if p in all_props]
        data.extend(struct.pack(BinaryFormat.UINT8, len(present_props)))
        
        for prop_name in present_props:
            prop_def = PropertyRegistry.get(prop_name)
            if prop_def is None:
                continue
            
            name_bytes = prop_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            prop_value = all_props[prop_name]
            prop_data = PropertySerializer.serialize_value(prop_value, prop_def, num_atoms)
            data.extend(struct.pack(BinaryFormat.UINT32, len(prop_data)))
            data.extend(prop_data)
        
        custom_props = {k: v for k, v in all_props.items() if k not in built_in_props}
        data.extend(struct.pack(BinaryFormat.UINT8, len(custom_props)))
        
        for custom_name, custom_value in custom_props.items():
            name_bytes = custom_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            value_str = str(custom_value)
            value_bytes = value_str.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
            data.extend(value_bytes)
        
        return bytes(data)
    
    def _decode_atomic_properties(self, data: bytes, offset: int, 
                                  num_atoms: Optional[int] = None) -> Tuple[AtomicProperties, int]:
        """Decode atomic properties using modular system"""
        props = AtomicProperties()
        
        try:
            num_props = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_props):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                prop_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                prop_def = PropertyRegistry.get(prop_name)
                if prop_def is None:
                    data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4 + data_len
                    continue
                
                data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                
                prop_value, new_offset = PropertySerializer.deserialize_value(
                    prop_def, data, offset, num_atoms
                )
                offset = new_offset
                
                setattr(props, prop_name, prop_value)
            
            num_custom = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_custom):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                custom_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                value_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                value_str = data[offset:offset+value_len].decode('utf-8')
                offset += value_len
                
                props.custom[custom_name] = value_str
            
            return props, offset
        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(f"Failed to decode atomic properties at offset {offset}: {e}") from e
    
    def _encode_structure_properties(self, props: StructureProperties) -> bytes:
        """Encode structure properties using modular system"""
        data = bytearray()
        
        all_props = props.get_all_properties()
        built_in_props = list(PropertyRegistry._properties.keys())
        struct_props = [p for p in built_in_props if PropertyRegistry.is_structure_property(p)]
        
        present_props = [p for p in struct_props if p in all_props]
        data.extend(struct.pack(BinaryFormat.UINT8, len(present_props)))
        
        for prop_name in present_props:
            prop_def = PropertyRegistry.get(prop_name)
            if prop_def is None:
                continue
            
            name_bytes = prop_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            prop_value = all_props[prop_name]
            prop_data = PropertySerializer.serialize_value(prop_value, prop_def)
            data.extend(struct.pack(BinaryFormat.UINT32, len(prop_data)))
            data.extend(prop_data)
        
        custom_props = {k: v for k, v in all_props.items() if k not in built_in_props}
        data.extend(struct.pack(BinaryFormat.UINT8, len(custom_props)))
        
        for custom_name, custom_value in custom_props.items():
            name_bytes = custom_name.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT8, len(name_bytes)))
            data.extend(name_bytes)
            
            value_str = str(custom_value)
            value_bytes = value_str.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT32, len(value_bytes)))
            data.extend(value_bytes)
        
        return bytes(data)
    
    def _decode_structure_properties(self, data: bytes, 
                                    offset: int) -> Tuple[StructureProperties, int]:
        """Decode structure properties using modular system"""
        props = StructureProperties()
        
        try:
            num_props = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_props):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                prop_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                prop_def = PropertyRegistry.get(prop_name)
                if prop_def is None:
                    data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4 + data_len
                    continue
                
                data_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                
                prop_value, new_offset = PropertySerializer.deserialize_value(
                    prop_def, data, offset
                )
                offset = new_offset
                
                setattr(props, prop_name, prop_value)
            
            num_custom = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
            offset += 1
            
            for _ in range(num_custom):
                name_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                offset += 1
                custom_name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                
                value_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                offset += 4
                value_str = data[offset:offset+value_len].decode('utf-8')
                offset += value_len
                
                props.custom[custom_name] = value_str
            
            return props, offset
        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(
                f"Failed to decode structure properties at offset {offset}: {e}"
            ) from e
    
    def encode(self, structure: USIFStructure) -> bytes:
        """
        Encode USIFStructure to bytes
        
        Args:
            structure: USIF structure to encode
            
        Returns:
            Encoded bytes
            
        Raises:
            EncodingError: If encoding fails
        """
        try:
            data = bytearray()
            
            data.extend(struct.pack(BinaryFormat.UINT8, structure.structure_type.value))
            data.extend(struct.pack(BinaryFormat.UINT8, structure.storage_mode.value))
            
            if structure.structure_type == StructureType.MOLECULE:
                if structure.storage_mode == StorageMode.SYMMETRIC:
                    point_group = structure.point_group or "C1"
                    pg_bytes = point_group.encode('utf-8')
                    data.extend(struct.pack(BinaryFormat.UINT8, len(pg_bytes)))
                    data.extend(pg_bytes)
                    
                    data.extend(struct.pack(BinaryFormat.UINT8, len(structure.point_group_sites)))
                    for site in structure.point_group_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
                else:
                    data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
                    for site in structure.atom_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        atom_prop_data = self._encode_atomic_properties(site.properties, num_atoms=1)
                        data.extend(atom_prop_data)
            else:
                lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
                data.extend(lattice_data)
                data.extend(struct.pack(BinaryFormat.UINT16, structure.spacegroup))
                
                if structure.storage_mode == StorageMode.SYMMETRIC:
                    data.extend(struct.pack(BinaryFormat.UINT8, len(structure.wyckoff_sites)))
                    for site in structure.wyckoff_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.UINT16, site.multiplicity))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        data.extend(struct.pack(BinaryFormat.FLOAT32, site.occupancy))
                else:
                    data.extend(struct.pack(BinaryFormat.UINT32, len(structure.atom_sites)))
                    for site in structure.atom_sites:
                        data.extend(struct.pack(BinaryFormat.UINT8, site.atomic_number))
                        data.extend(struct.pack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                              *site.coords))
                        atom_prop_data = self._encode_atomic_properties(site.properties, num_atoms=1)
                        data.extend(atom_prop_data)
            
            struct_prop_data = self._encode_structure_properties(structure.structure_properties)
            data.extend(struct.pack(BinaryFormat.UINT32, len(struct_prop_data)))
            data.extend(struct_prop_data)
            
            formula_bytes = structure.formula.encode('utf-8')
            data.extend(struct.pack(BinaryFormat.UINT16, len(formula_bytes)))
            data.extend(formula_bytes)
            
            raw_data = bytes(data)
            compressed_data = self._compress_data(raw_data)
            
            header = bytearray(self.HEADER_SIZE)
            header[0:7] = b'USIF\x00\x00\x00'
            header[7:8] = struct.pack(BinaryFormat.UINT8, self.VERSION)
            header[8:12] = struct.pack(BinaryFormat.UINT32, len(raw_data))
            header[12:16] = struct.pack(BinaryFormat.UINT32, len(compressed_data))
            header[16:17] = struct.pack(BinaryFormat.UINT8, self.compression.value)
            
            hash_value = self._calculate_hash(structure)
            header[17:49] = hash_value
            
            return bytes(header) + compressed_data
            
        except (EncodingError, ValidationError):
            raise
        except (ValueError, TypeError, struct.error) as e:
            raise EncodingError(f"Failed to encode structure: {e}") from e
        except Exception as e:
            raise EncodingError(f"Unexpected error during encoding: {e}") from e
    
    def decode(self, data: bytes) -> Tuple[USIFStructure, bytes]:
        """
        Decode bytes to USIFStructure
        
        Args:
            data: Encoded bytes
            
        Returns:
            Tuple of (USIFStructure, hash)
            
        Raises:
            DecodingError: If decoding fails
            CorruptedDataError: If data is corrupted
        """
        try:
            if len(data) < self.HEADER_SIZE:
                raise CorruptedDataError(f"Data too short: {len(data)} < {self.HEADER_SIZE}")
            
            magic = data[0:7]
            if magic != b'USIF\x00\x00\x00':
                raise CorruptedDataError(f"Invalid magic bytes: {magic}")
            
            version = struct.unpack(BinaryFormat.UINT8, data[7:8])[0]
            if version != self.VERSION:
                logger.warning(f"Version mismatch: file version {version}, expected {self.VERSION}")
            
            raw_size = struct.unpack(BinaryFormat.UINT32, data[8:12])[0]
            compressed_size = struct.unpack(BinaryFormat.UINT32, data[12:16])[0]
            comp_type = CompressionType(struct.unpack(BinaryFormat.UINT8, data[16:17])[0])
            hash_value = data[17:49]
            
            compressed_data = data[self.HEADER_SIZE:self.HEADER_SIZE + compressed_size]
            data = self._decompress_data(compressed_data, comp_type)
            
            offset = 0
            structure_type = StructureType(struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0])
            offset += 1
            storage_mode = StorageMode(struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0])
            offset += 1
            
            lattice_matrix = None
            spacegroup = 1
            point_group = None
            wyckoff_sites = None
            point_group_sites = None
            atom_sites = None
            
            if structure_type == StructureType.MOLECULE:
                if storage_mode == StorageMode.SYMMETRIC:
                    pg_len = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                    offset += 1
                    point_group = data[offset:offset+pg_len].decode('utf-8')
                    offset += pg_len
                    
                    num_sites = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                    offset += 1
                    
                    point_group_sites = []
                    for _ in range(num_sites):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        mult = struct.unpack(BinaryFormat.UINT16, data[offset+1:offset+3])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+3:offset+15])
                        occupancy = struct.unpack(BinaryFormat.FLOAT32, data[offset+15:offset+19])[0]
                        offset += 19
                        point_group_sites.append(
                            PointGroupSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4
                    
                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+1:offset+13])
                        offset += 13
                        atom_props, offset = self._decode_atomic_properties(data, offset, num_atoms=1)
                        atom_sites.append(AtomSite(atomic_num, (x, y, z_coord), atom_props))
            else:
                lattice_data = data[offset:offset+36]
                lattice_matrix = np.frombuffer(lattice_data, dtype=np.float32).reshape(3, 3)
                offset += 36
                
                spacegroup = struct.unpack(BinaryFormat.UINT16, data[offset:offset+2])[0]
                offset += 2
                
                if storage_mode == StorageMode.SYMMETRIC:
                    num_sites = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                    offset += 1
                    
                    wyckoff_sites = []
                    for _ in range(num_sites):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        mult = struct.unpack(BinaryFormat.UINT16, data[offset+1:offset+3])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+3:offset+15])
                        occupancy = struct.unpack(BinaryFormat.FLOAT32, data[offset+15:offset+19])[0]
                        offset += 19
                        wyckoff_sites.append(
                            WyckoffSite(atomic_num, mult, (x, y, z_coord), occupancy)
                        )
                else:
                    num_atoms = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
                    offset += 4
                    
                    atom_sites = []
                    for _ in range(num_atoms):
                        atomic_num = struct.unpack(BinaryFormat.UINT8, data[offset:offset+1])[0]
                        x, y, z_coord = struct.unpack(BinaryFormat.array(BinaryFormat.FLOAT32, 3), 
                                                      data[offset+1:offset+13])
                        offset += 13
                        atom_props, offset = self._decode_atomic_properties(data, offset, num_atoms=1)
                        atom_sites.append(AtomSite(atomic_num, (x, y, z_coord), atom_props))
            
            props_len = struct.unpack(BinaryFormat.UINT32, data[offset:offset+4])[0]
            offset += 4
            struct_props, offset = self._decode_structure_properties(data, offset)
            
            formula_len = struct.unpack(BinaryFormat.UINT16, data[offset:offset+2])[0]
            offset += 2
            formula = data[offset:offset+formula_len].decode('utf-8')
            
            if structure_type == StructureType.MOLECULE:
                structure = USIFStructure(
                    structure_type=structure_type,
                    storage_mode=storage_mode,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    atom_sites=atom_sites,
                    structure_properties=struct_props,
                    formula=formula
                )
            else:
                structure = USIFStructure(
                    structure_type=structure_type,
                    lattice_matrix=lattice_matrix,
                    spacegroup=spacegroup,
                    storage_mode=storage_mode,
                    wyckoff_sites=wyckoff_sites,
                    atom_sites=atom_sites,
                    structure_properties=struct_props,
                    formula=formula
                )
            
            return structure, hash_value
            
        except (struct.error, UnicodeDecodeError) as e:
            raise DecodingError(f"Failed to decode data: {e}") from e
        except (DecodingError, CorruptedDataError, ValidationError):
            raise
        except (ValueError, TypeError, KeyError) as e:
            raise DecodingError(f"Failed to decode structure: {e}") from e
        except Exception as e:
            raise DecodingError(f"Unexpected error during decoding: {e}") from e
    
    def get_structure_hash(self, structure: USIFStructure) -> str:
        """Get hexadecimal hash of structure"""
        return self._calculate_hash(structure).hex()
    
    def save(self, structure: USIFStructure, filename: Union[str, Path]) -> None:
        """Save structure to file"""
        try:
            with open(filename, 'wb') as f:
                f.write(self.encode(structure))
        except IOError as e:
            raise StorageError(f"Failed to save structure to {filename}: {e}") from e
    
    def load(self, filename: Union[str, Path]) -> USIFStructure:
        """Load structure from file"""
        try:
            with open(filename, 'rb') as f:
                structure, _ = self.decode(f.read())
            return structure
        except (IOError, FileNotFoundError) as e:
            raise StorageError(f"Failed to load structure from {filename}: {e}") from e

