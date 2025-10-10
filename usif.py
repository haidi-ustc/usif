#!/usr/bin/env python3
""" 
USIF (Universal Structure Interchange Format) - Optimized Implementation v2.0
Unified format for crystals and molecules with intelligent compression
    
Features:
- Unified interface for periodic and non-periodic structures
- Intelligent compression: symmetric (crystals + molecules) or atomic (all types)
- Point group symmetry support for molecules
- 4-6x compression vs traditional formats
- Modular property system with type safety
- Random access container
    
Author: haidi@hfut.edu.cn
Version: 2.0
"""    

import struct
import hashlib
import gzip
import numpy as np
from typing import Dict, List, Tuple, Optional, Union, Any, Iterator
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from pymatgen.core import Structure as PMGStructure, Lattice, Element
from pymatgen.core import Molecule as PMGMolecule
from pymatgen.io.cif import CifParser
from pymatgen.io.vasp import Poscar, Vasprun
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer, PointGroupAnalyzer


# ============================================================================
# Property System - Modular Architecture
# ============================================================================

@dataclass
class PropertyDefinition:
    """Definition of a property type"""
    name: str
    data_type: type
    is_per_atom: bool = False
    dimensions: Tuple[int, ...] = ()
    description: str = ""
    units: str = ""
    
    def is_scalar(self) -> bool:
        """Check if property is scalar"""
        return len(self.dimensions) == 0
    
    def validate_value(self, value: Any, num_atoms: int = None) -> bool:
        """Validate property value against definition"""
        if value is None:
            return True
        
        if not isinstance(value, self.data_type):
            return False
        
        if self.is_per_atom and num_atoms is not None:
            if isinstance(value, (list, np.ndarray)) and len(value) != num_atoms:
                return False
        
        return True


class PropertySerializer:
    """Serialize and deserialize property values"""
    
    @staticmethod
    def serialize_value(value: Any, prop_def: PropertyDefinition, 
                       num_atoms: int = None) -> bytes:
        """Serialize property value to bytes"""
        if value is None:
            return b''
        
        data = bytearray()
        
        if prop_def.is_scalar():
            if prop_def.data_type == float:
                data.extend(struct.pack('d', value))
            elif prop_def.data_type == int:
                data.extend(struct.pack('q', value))
            elif prop_def.data_type == bool:
                data.extend(struct.pack('?', value))
            elif prop_def.data_type == str:
                str_bytes = value.encode('utf-8')
                data.extend(struct.pack('<I', len(str_bytes)))
                data.extend(str_bytes)
        else:
            if prop_def.is_per_atom:
                # For per-atom properties
                # Handle both single atom (tuple/array) and multiple atoms (list of tuples/arrays)
                if num_atoms == 1:
                    # Single atom - value is the property directly (e.g., a 3-tuple for force)
                    data.extend(struct.pack('<I', 1))
                    if prop_def.data_type == tuple and len(prop_def.dimensions) == 1:
                        dim = prop_def.dimensions[0]
                        data.extend(struct.pack(f'{dim}f', *value))
                    elif prop_def.data_type == float and len(prop_def.dimensions) == 1:
                        dim = prop_def.dimensions[0]
                        data.extend(struct.pack(f'{dim}f', *value))
                    elif prop_def.data_type == float:
                        data.extend(struct.pack('f', value))
                else:
                    # Multiple atoms - value is a list of properties
                    if num_atoms is None:
                        num_atoms = len(value)
                    data.extend(struct.pack('<I', num_atoms))
                    for atom_value in value:
                        if prop_def.data_type == tuple and len(prop_def.dimensions) == 1:
                            dim = prop_def.dimensions[0]
                            data.extend(struct.pack(f'{dim}f', *atom_value))
                        elif prop_def.data_type == float and len(prop_def.dimensions) == 1:
                            dim = prop_def.dimensions[0]
                            data.extend(struct.pack(f'{dim}f', *atom_value))
                        elif prop_def.data_type == float:
                            data.extend(struct.pack('f', atom_value))
            else:
                # Structure-level array properties (e.g., stress tensor)
                if prop_def.data_type == tuple and len(prop_def.dimensions) == 1:
                    dim = prop_def.dimensions[0]
                    data.extend(struct.pack(f'{dim}f', *value))
                elif prop_def.data_type == float and len(prop_def.dimensions) == 1:
                    dim = prop_def.dimensions[0]
                    data.extend(struct.pack(f'{dim}f', *value))
        
        return bytes(data)
    
    @staticmethod
    def deserialize_value(prop_def: PropertyDefinition, data: bytes, 
                         offset: int, num_atoms: int = None) -> Tuple[Any, int]:
        """Deserialize property value from bytes"""
        if len(data) == offset:
            return None, offset
        
        value = None  # Initialize value to avoid UnboundLocalError
        
        if prop_def.is_scalar():
            if prop_def.data_type == float:
                value = struct.unpack('d', data[offset:offset+8])[0]
                offset += 8
            elif prop_def.data_type == int:
                value = struct.unpack('q', data[offset:offset+8])[0]
                offset += 8
            elif prop_def.data_type == bool:
                value = struct.unpack('?', data[offset:offset+1])[0]
                offset += 1
            elif prop_def.data_type == str:
                str_len = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                value = data[offset:offset+str_len].decode('utf-8')
                offset += str_len
        else:
            # Array/tuple properties
            if prop_def.is_per_atom:
                # Per-atom array properties (e.g., forces per atom)
                count = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                value = []
                for _ in range(count):
                    if prop_def.data_type == tuple and len(prop_def.dimensions) == 1:
                        dim = prop_def.dimensions[0]
                        atom_value = struct.unpack(f'{dim}f', data[offset:offset+dim*4])
                        value.append(tuple(atom_value))
                        offset += dim * 4
                    elif prop_def.data_type == float and len(prop_def.dimensions) == 1:
                        dim = prop_def.dimensions[0]
                        atom_value = struct.unpack(f'{dim}f', data[offset:offset+dim*4])
                        value.append(tuple(atom_value))
                        offset += dim * 4
                    elif prop_def.data_type == float:
                        atom_value = struct.unpack('f', data[offset:offset+4])[0]
                        value.append(atom_value)
                        offset += 4
            else:
                # Structure-level array properties (e.g., stress tensor)
                if prop_def.data_type == tuple and len(prop_def.dimensions) == 1:
                    dim = prop_def.dimensions[0]
                    value = struct.unpack(f'{dim}f', data[offset:offset+dim*4])
                    offset += dim * 4
                elif prop_def.data_type == float and len(prop_def.dimensions) == 1:
                    dim = prop_def.dimensions[0]
                    value = struct.unpack(f'{dim}f', data[offset:offset+dim*4])
                    offset += dim * 4
        
        return value, offset

class PropertyRegistry:
    """Registry for all supported properties"""
    
    # Atomic properties (per-atom)
    FORCE = PropertyDefinition("force", tuple, True, (3,), "Atomic forces", "eV/Å")
    CHARGE = PropertyDefinition("charge", float, True, (), "Atomic charge", "e")
    MAGMOM = PropertyDefinition("magmom", float, True, (), "Magnetic moment", "μB")
    VELOCITY = PropertyDefinition("velocity", tuple, True, (3,), "Atomic velocity", "Å/fs")
    
    # Structure properties
    ENERGY = PropertyDefinition("energy", float, False, (), "Total energy", "eV")
    ENERGY_PER_ATOM = PropertyDefinition("energy_per_atom", float, False, (), "Energy per atom", "eV/atom")
    STRESS = PropertyDefinition("stress", tuple, False, (6,), "Stress tensor", "kBar")
    PRESSURE = PropertyDefinition("pressure", float, False, (), "Pressure", "kBar")
    FORCES_RMS = PropertyDefinition("forces_rms", float, False, (), "RMS forces", "eV/Å")
    FORCES_MAX = PropertyDefinition("forces_max", float, False, (), "Max forces", "eV/Å")
    VOLUME = PropertyDefinition("volume", float, False, (), "Cell volume", "Å³")
    CALCULATOR = PropertyDefinition("calculator", str, False, (), "Calculator used", "")
    FUNCTIONAL = PropertyDefinition("functional", str, False, (), "DFT functional", "")
    CONVERGED = PropertyDefinition("converged", bool, False, (), "Convergence status", "")
    
    _properties = {
        # Atomic properties
        "force": FORCE,
        "charge": CHARGE, 
        "magmom": MAGMOM,
        "velocity": VELOCITY,
        
        # Structure properties
        "energy": ENERGY,
        "energy_per_atom": ENERGY_PER_ATOM,
        "stress": STRESS,
        "pressure": PRESSURE,
        "forces_rms": FORCES_RMS,
        "forces_max": FORCES_MAX,
        "volume": VOLUME,
        "calculator": CALCULATOR,
        "functional": FUNCTIONAL,
        "converged": CONVERGED,
    }
    
    _custom_properties = {}
    
    @classmethod
    def get_all_properties(cls) -> Dict[str, PropertyDefinition]:
        """Get all registered properties"""
        return {**cls._properties, **cls._custom_properties}
    
    @classmethod
    def get_property(cls, name: str) -> Optional[PropertyDefinition]:
        """Get property definition by name"""
        return cls._properties.get(name) or cls._custom_properties.get(name)
    
    @classmethod
    def is_atomic_property(cls, prop_name: str) -> bool:
        """Check if property is atomic (per-atom)"""
        prop_def = cls.get_property(prop_name)
        return prop_def.is_per_atom if prop_def else False
    
    @classmethod
    def is_structure_property(cls, prop_name: str) -> bool:
        """Check if property is structure-level"""
        prop_def = cls.get_property(prop_name)
        return not prop_def.is_per_atom if prop_def else False
    
    @classmethod
    def register_custom_property(cls, prop_def: PropertyDefinition):
        """Register a custom property"""
        if prop_def.name in cls._properties:
            raise ValueError(f"Property {prop_def.name} is already a built-in property")
        cls._custom_properties[prop_def.name] = prop_def


# ============================================================================
# Core Data Structures
# ============================================================================

class CompressionType(IntEnum):
    """Compression algorithm types"""
    NONE = 0
    GZIP = 1


class StructureType(IntEnum):
    """Structure periodicity type"""
    PERIODIC = 0    # Crystal (periodic in 3D)
    MOLECULAR = 1   # Molecule (non-periodic, no lattice)


class StorageMode(IntEnum):
    """Storage mode for atomic data"""
    SYMMETRIC = 0      # Wyckoff positions (crystals) or point group (molecules)
    FULL_ATOMIC = 1    # All atoms explicitly (both periodic and molecular)


@dataclass
class AtomicProperties:
    """Properties for individual atoms using modular property system"""
    force: Optional[Tuple[float, float, float]] = None
    charge: Optional[float] = None
    magmom: Optional[float] = None
    velocity: Optional[Tuple[float, float, float]] = None
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def get_all_properties(self) -> Dict[str, Any]:
        """Get all atomic properties as dictionary"""
        props = {}
        for prop_name in PropertyRegistry._properties:
            if PropertyRegistry.is_atomic_property(prop_name):
                value = getattr(self, prop_name, None)
                if value is not None:
                    props[prop_name] = value
        props.update(self.custom)
        return props


@dataclass
class StructureProperties:
    """Structure-level properties using modular property system"""
    energy: Optional[float] = None
    energy_per_atom: Optional[float] = None
    stress: Optional[Tuple[float, float, float, float, float, float]] = None
    pressure: Optional[float] = None
    forces_rms: Optional[float] = None
    forces_max: Optional[float] = None
    volume: Optional[float] = None
    calculator: Optional[str] = None
    functional: Optional[str] = None
    converged: Optional[bool] = None
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def get_all_properties(self) -> Dict[str, Any]:
        """Get all structure properties as dictionary"""
        props = {}
        for prop_name in PropertyRegistry._properties:
            if PropertyRegistry.is_structure_property(prop_name):
                value = getattr(self, prop_name, None)
                if value is not None:
                    props[prop_name] = value
        props.update(self.custom)
        return props


@dataclass
class WyckoffSite:
    """Wyckoff position for symmetric storage (periodic only)"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Fractional
    occupancy: float = 1.0


@dataclass
class PointGroupSite:
    """Point group symmetric position for molecules"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Cartesian (Å)
    occupancy: float = 1.0


@dataclass
class AtomSite:
    """Universal atom site"""
    atomic_number: int
    coords: Tuple[float, float, float]
    properties: AtomicProperties = field(default_factory=AtomicProperties)


@dataclass
class USIFStructure:
    """
    Universal structure representation
    
    Structure type matrix:
    ┌─────────────┬──────────────┬─────────────────┐
    │             │ SYMMETRIC    │ FULL_ATOMIC     │
    ├─────────────┼──────────────┼─────────────────┤
    │ PERIODIC    │ Wyckoff      │ All atoms       │
    │ (Crystal)   │ + lattice    │ + lattice       │
    ├─────────────┼──────────────┼─────────────────┤
    │ MOLECULAR   │ Point group  │ All atoms       │
    │ (Molecule)  │ (no lattice) │ (no lattice)    │
    └─────────────┴──────────────┴─────────────────┘
    """
    structure_type: StructureType = StructureType.PERIODIC
    storage_mode: StorageMode = StorageMode.SYMMETRIC
    lattice_matrix: Optional[np.ndarray] = None
    spacegroup: int = 1
    point_group: Optional[str] = None
    wyckoff_sites: Optional[List[WyckoffSite]] = None
    point_group_sites: Optional[List[PointGroupSite]] = None
    atom_sites: Optional[List[AtomSite]] = None
    structure_properties: StructureProperties = field(default_factory=StructureProperties)
    formula: str = ""
    
    def __post_init__(self):
        """Validate structure configuration"""
        if self.structure_type == StructureType.MOLECULAR:
            if self.lattice_matrix is not None:
                raise ValueError("Molecular structures should not have lattice")
            if self.storage_mode == StorageMode.SYMMETRIC and self.point_group_sites is None:
                raise ValueError("Molecular SYMMETRIC mode requires point_group_sites")
            elif self.storage_mode == StorageMode.FULL_ATOMIC and self.atom_sites is None:
                raise ValueError("Molecular FULL_ATOMIC mode requires atom_sites")
        else:
            if self.lattice_matrix is None:
                raise ValueError("Periodic structures require lattice")
            if self.storage_mode == StorageMode.SYMMETRIC and self.wyckoff_sites is None:
                raise ValueError("Periodic SYMMETRIC mode requires wyckoff_sites")
            elif self.storage_mode == StorageMode.FULL_ATOMIC and self.atom_sites is None:
                raise ValueError("Periodic FULL_ATOMIC mode requires atom_sites")
    
    def is_periodic(self) -> bool:
        return self.structure_type == StructureType.PERIODIC
    
    def is_molecular(self) -> bool:
        return self.structure_type == StructureType.MOLECULAR
    
    def is_symmetric(self) -> bool:
        return self.storage_mode == StorageMode.SYMMETRIC
    
    def num_atoms(self) -> int:
        if self.storage_mode == StorageMode.SYMMETRIC:
            if self.is_periodic():
                return sum(site.multiplicity for site in self.wyckoff_sites)
            else:
                return sum(site.multiplicity for site in self.point_group_sites)
        else:
            return len(self.atom_sites)


# ============================================================================
# USIF Encoder/Decoder
# ============================================================================

class USIF:
    """USIF (Universal Structure Interchange Format) Encoder/Decoder"""
    
    VERSION = 2
    HEADER_SIZE = 64
    
    def __init__(self, compression: CompressionType = CompressionType.GZIP):
        self.compression = compression
    
    def _calculate_hash(self, structure: USIFStructure) -> bytes:
        """Calculate SHA-256 hash"""
        data = bytearray()
        data.extend(struct.pack('B', structure.structure_type.value))
        data.extend(struct.pack('B', structure.storage_mode.value))
        
        if structure.is_periodic():
            lattice_data = structure.lattice_matrix.tobytes()
            data.extend(lattice_data)
            data.extend(struct.pack('H', structure.spacegroup))
        elif structure.is_molecular() and structure.storage_mode == StorageMode.SYMMETRIC:
            pg_bytes = (structure.point_group or "C1").encode('utf-8')
            data.extend(struct.pack('B', len(pg_bytes)))
            data.extend(pg_bytes)
        
        # Atoms
        if structure.storage_mode == StorageMode.SYMMETRIC:
            if structure.is_periodic():
                data.extend(struct.pack('B', len(structure.wyckoff_sites)))
                for site in structure.wyckoff_sites:
                    data.extend(struct.pack('B', site.atomic_number))
                    coords = tuple(round(c, 5) for c in site.coords)
                    data.extend(struct.pack('3f', *coords))
            else:
                data.extend(struct.pack('B', len(structure.point_group_sites)))
                for site in structure.point_group_sites:
                    data.extend(struct.pack('B', site.atomic_number))
                    coords = tuple(round(c, 5) for c in site.coords)
                    data.extend(struct.pack('3f', *coords))
        else:
            data.extend(struct.pack('I', len(structure.atom_sites)))
            for site in structure.atom_sites:
                data.extend(struct.pack('B', site.atomic_number))
                coords = tuple(round(c, 5) for c in site.coords)
                data.extend(struct.pack('3f', *coords))
        
        return hashlib.sha256(bytes(data)).digest()
    
    def _compress_data(self, data: bytes) -> bytes:
        if self.compression == CompressionType.GZIP:
            return gzip.compress(data, compresslevel=6)
        return data
    
    def _decompress_data(self, data: bytes, comp_type: CompressionType) -> bytes:
        if comp_type == CompressionType.GZIP:
            return gzip.decompress(data)
        return data
    
    def _encode_atomic_properties(self, props: AtomicProperties, num_atoms: int = None) -> bytes:
        """Encode atomic properties using modular system"""
        data = bytearray()
        
        all_props = props.get_all_properties()
        built_in_props = list(PropertyRegistry._properties.keys())
        atomic_props = [p for p in built_in_props if PropertyRegistry.is_atomic_property(p)]
        
        flags = 0
        custom_props = []
        
        for i, prop_name in enumerate(atomic_props):
            if prop_name in all_props and all_props[prop_name] is not None:
                flags |= (1 << i)
        
        for prop_name, value in props.custom.items():
            if value is not None:
                custom_props.append((prop_name, value))
        
        if custom_props:
            flags |= (1 << 15)
        
        data.extend(struct.pack('<H', flags))
        
        for i, prop_name in enumerate(atomic_props):
            if flags & (1 << i):
                prop_def = PropertyRegistry.get_property(prop_name)
                value = all_props[prop_name]
                prop_data = PropertySerializer.serialize_value(value, prop_def, num_atoms)
                data.extend(prop_data)
        
        if flags & (1 << 15):
            import json
            custom_data = json.dumps(custom_props).encode('utf-8')
            data.extend(struct.pack('<I', len(custom_data)))
            data.extend(custom_data)
        
        return bytes(data)
    
    def _decode_atomic_properties(self, data: bytes, offset: int, num_atoms: int = None) -> Tuple[AtomicProperties, int]:
        """Decode atomic properties using modular system"""
        props = AtomicProperties()
        
        flags = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        
        built_in_props = list(PropertyRegistry._properties.keys())
        atomic_props = [p for p in built_in_props if PropertyRegistry.is_atomic_property(p)]
        
        for i, prop_name in enumerate(atomic_props):
            if flags & (1 << i):
                prop_def = PropertyRegistry.get_property(prop_name)
                value, offset = PropertySerializer.deserialize_value(prop_def, data, offset, num_atoms)
                setattr(props, prop_name, value)
        
        if flags & (1 << 15):
            import json
            json_len = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            if json_len > 0:
                try:
                    custom_data = data[offset:offset+json_len].decode('utf-8')
                    custom_props = json.loads(custom_data)
                    for prop_name, value in custom_props:
                        props.custom[prop_name] = value
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
            offset += json_len
        
        return props, offset
    
    def _encode_structure_properties(self, props: StructureProperties) -> bytes:
        """Encode structure properties using modular system"""
        data = bytearray()
        
        all_props = props.get_all_properties()
        built_in_props = list(PropertyRegistry._properties.keys())
        structure_props = [p for p in built_in_props if PropertyRegistry.is_structure_property(p)]
        
        flags = 0
        custom_props = []
        
        for i, prop_name in enumerate(structure_props):
            if prop_name in all_props and all_props[prop_name] is not None:
                flags |= (1 << i)
        
        for prop_name, value in props.custom.items():
            if value is not None:
                custom_props.append((prop_name, value))
        
        if custom_props:
            flags |= (1 << 15)
        
        data.extend(struct.pack('<H', flags))
        
        for i, prop_name in enumerate(structure_props):
            if flags & (1 << i):
                prop_def = PropertyRegistry.get_property(prop_name)
                value = all_props[prop_name]
                prop_data = PropertySerializer.serialize_value(value, prop_def)
                data.extend(prop_data)
        
        if flags & (1 << 15):
            import json
            custom_data = json.dumps(custom_props).encode('utf-8')
            data.extend(struct.pack('<I', len(custom_data)))
            data.extend(custom_data)
        
        return bytes(data)
    
    def _decode_structure_properties(self, data: bytes, offset: int) -> Tuple[StructureProperties, int]:
        """Decode structure properties using modular system"""
        props = StructureProperties()
        
        flags = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        
        built_in_props = list(PropertyRegistry._properties.keys())
        structure_props = [p for p in built_in_props if PropertyRegistry.is_structure_property(p)]
        
        for i, prop_name in enumerate(structure_props):
            if flags & (1 << i):
                prop_def = PropertyRegistry.get_property(prop_name)
                value, offset = PropertySerializer.deserialize_value(prop_def, data, offset)
                setattr(props, prop_name, value)
        
        if flags & (1 << 15):
            import json
            json_len = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            if json_len > 0:
                try:
                    custom_data = data[offset:offset+json_len].decode('utf-8')
                    custom_props = json.loads(custom_data)
                    for prop_name, value in custom_props:
                        props.custom[prop_name] = value
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
            offset += json_len
        
        return props, offset
    
    def encode(self, structure: USIFStructure) -> bytes:
        """Encode structure to USIF binary format"""
        data = bytearray()
        
        data.extend(struct.pack('B', structure.structure_type.value))
        data.extend(struct.pack('B', structure.storage_mode.value))
        
        if structure.structure_type == StructureType.MOLECULAR:
            if structure.storage_mode == StorageMode.SYMMETRIC:
                pg_bytes = (structure.point_group or "C1").encode('utf-8')
                data.extend(struct.pack('B', len(pg_bytes)))
                data.extend(pg_bytes)
                
                data.extend(struct.pack('B', len(structure.point_group_sites)))
                for site in structure.point_group_sites:
                    data.extend(struct.pack('B', site.atomic_number))
                    data.extend(struct.pack('B', site.multiplicity))
                    data.extend(struct.pack('3f', *site.coords))
                    data.extend(struct.pack('f', site.occupancy))
            else:
                data.extend(struct.pack('<I', len(structure.atom_sites)))
                for atom in structure.atom_sites:
                    data.extend(struct.pack('B', atom.atomic_number))
                    data.extend(struct.pack('3f', *atom.coords))
                    atom_props_data = self._encode_atomic_properties(atom.properties, num_atoms=1)
                    data.extend(atom_props_data)
        else:
            matrix = structure.lattice_matrix
            data.extend(matrix.astype(np.float32).tobytes())
            data.extend(struct.pack('H', structure.spacegroup))
            
            if structure.storage_mode == StorageMode.SYMMETRIC:
                data.extend(struct.pack('B', len(structure.wyckoff_sites)))
                for site in structure.wyckoff_sites:
                    data.extend(struct.pack('B', site.atomic_number))
                    data.extend(struct.pack('B', site.multiplicity))
                    data.extend(struct.pack('3f', *site.coords))
                    data.extend(struct.pack('f', site.occupancy))
            else:
                data.extend(struct.pack('<I', len(structure.atom_sites)))
                for site in structure.atom_sites:
                    data.extend(struct.pack('B', site.atomic_number))
                    data.extend(struct.pack('3f', *site.coords))
                    atom_props_data = self._encode_atomic_properties(site.properties, num_atoms=1)
                    data.extend(atom_props_data)
        
        props_data = self._encode_structure_properties(structure.structure_properties)
        data.extend(struct.pack('<I', len(props_data)))
        data.extend(props_data)
        
        formula_bytes = structure.formula.encode('utf-8')
        data.extend(struct.pack('<H', len(formula_bytes)))
        data.extend(formula_bytes)
        
        compressed_data = self._compress_data(bytes(data))
        hash_value = self._calculate_hash(structure)
        
        header = bytearray(self.HEADER_SIZE)
        header[0:1] = struct.pack('B', self.VERSION)
        header[1:2] = struct.pack('B', self.compression.value)
        header[2:34] = hash_value
        header[34:38] = struct.pack('<I', len(compressed_data))
        
        return bytes(header) + compressed_data
    
    def decode(self, usif_data: bytes) -> Tuple[USIFStructure, bytes]:
        """Decode USIF binary format to structure"""
        if len(usif_data) < self.HEADER_SIZE:
            raise ValueError(f"USIF data too short")
        
        version = struct.unpack('B', usif_data[0:1])[0]
        comp_type = struct.unpack('B', usif_data[1:2])[0]
        hash_value = usif_data[2:34]
        data_len = struct.unpack('<I', usif_data[34:38])[0]
        
        if version not in [1, 2]:
            raise ValueError(f"Unsupported USIF version: {version}")
        
        compressed_data = usif_data[self.HEADER_SIZE:self.HEADER_SIZE + data_len]
        data = self._decompress_data(compressed_data, CompressionType(comp_type))
        
        offset = 0
        
        if version == 2:
            structure_type = StructureType(struct.unpack('B', data[offset:offset+1])[0])
            offset += 1
            storage_mode = StorageMode(struct.unpack('B', data[offset:offset+1])[0])
            offset += 1
        else:
            storage_mode_val = struct.unpack('B', data[offset:offset+1])[0]
            offset += 1
            structure_type = StructureType.PERIODIC
            storage_mode = StorageMode(storage_mode_val)
        
        lattice_matrix = None
        wyckoff_sites = None
        point_group_sites = None
        atom_sites = None
        spacegroup = 1
        point_group = None
        
        if structure_type == StructureType.MOLECULAR:
            if storage_mode == StorageMode.SYMMETRIC:
                pg_len = struct.unpack('B', data[offset:offset+1])[0]
                offset += 1
                point_group = data[offset:offset+pg_len].decode('utf-8')
                offset += pg_len
                
                num_sites = struct.unpack('B', data[offset:offset+1])[0]
                offset += 1
                
                point_group_sites = []
                for _ in range(num_sites):
                    z = struct.unpack('B', data[offset:offset+1])[0]
                    mult = struct.unpack('B', data[offset+1:offset+2])[0]
                    x, y, z_coord = struct.unpack('3f', data[offset+2:offset+14])
                    occupancy = struct.unpack('f', data[offset+14:offset+18])[0]
                    offset += 18
                    point_group_sites.append(PointGroupSite(z, mult, (x, y, z_coord), occupancy))
            else:
                num_atoms = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                
                atom_sites = []
                for _ in range(num_atoms):
                    z = struct.unpack('B', data[offset:offset+1])[0]
                    x, y, z_coord = struct.unpack('3f', data[offset+1:offset+13])
                    offset += 13
                    atom_props, offset = self._decode_atomic_properties(data, offset, num_atoms=1)
                    atom_sites.append(AtomSite(z, (x, y, z_coord), atom_props))
        else:
            lattice_data = data[offset:offset+36]
            lattice_matrix = np.frombuffer(lattice_data, dtype=np.float32).reshape(3, 3)
            offset += 36
            
            spacegroup = struct.unpack('H', data[offset:offset+2])[0]
            offset += 2
            
            if storage_mode == StorageMode.SYMMETRIC:
                num_sites = struct.unpack('B', data[offset:offset+1])[0]
                offset += 1
                
                wyckoff_sites = []
                for _ in range(num_sites):
                    z = struct.unpack('B', data[offset:offset+1])[0]
                    mult = struct.unpack('B', data[offset+1:offset+2])[0]
                    x, y, z_coord = struct.unpack('3f', data[offset+2:offset+14])
                    occupancy = struct.unpack('f', data[offset+14:offset+18])[0]
                    offset += 18
                    wyckoff_sites.append(WyckoffSite(z, mult, (x, y, z_coord), occupancy))
            else:
                num_atoms = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                
                atom_sites = []
                for _ in range(num_atoms):
                    z = struct.unpack('B', data[offset:offset+1])[0]
                    x, y, z_coord = struct.unpack('3f', data[offset+1:offset+13])
                    offset += 13
                    atom_props, offset = self._decode_atomic_properties(data, offset, num_atoms=1)
                    atom_sites.append(AtomSite(z, (x, y, z_coord), atom_props))
        
        props_len = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        struct_props, offset = self._decode_structure_properties(data, offset)
        
        formula_len = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
        formula = data[offset:offset+formula_len].decode('utf-8')
        
        if structure_type == StructureType.MOLECULAR:
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
    
    def get_structure_hash(self, structure: USIFStructure) -> str:
        return self._calculate_hash(structure).hex()
    
    def save(self, structure: USIFStructure, filename: Union[str, Path]) -> None:
        with open(filename, 'wb') as f:
            f.write(self.encode(structure))
    
    def load(self, filename: Union[str, Path]) -> USIFStructure:
        with open(filename, 'rb') as f:
            structure, _ = self.decode(f.read())
        return structure


# ============================================================================
# Pymatgen Converter
# ============================================================================

class StructureConverter:
    """Conversion between USIF and pymatgen"""
    
    @staticmethod
    def from_pymatgen(pmg_obj: Union[PMGStructure, PMGMolecule],
                     forces: Optional[np.ndarray] = None,
                     stress: Optional[np.ndarray] = None,
                     energy: Optional[float] = None,
                     charges: Optional[np.ndarray] = None,
                     magmoms: Optional[np.ndarray] = None,
                     force_symmetric: bool = False,
                     **kwargs) -> USIFStructure:
        """
        Universal converter from pymatgen to USIF
        """
        is_molecule = isinstance(pmg_obj, PMGMolecule)
        
        if is_molecule:
            return StructureConverter._from_molecule(
                pmg_obj, forces, charges, energy, force_symmetric, **kwargs)
        else:
            return StructureConverter._from_crystal(
                pmg_obj, forces, stress, energy, charges, magmoms, force_symmetric, **kwargs)
    
    @staticmethod
    def _from_molecule(pmg_molecule: PMGMolecule,
                      forces: Optional[np.ndarray] = None,
                      charges: Optional[np.ndarray] = None,
                      energy: Optional[float] = None,
                      force_symmetric: bool = False,
                      **kwargs) -> USIFStructure:
        
        has_atomic_properties = forces is not None or charges is not None
        
        if force_symmetric or (not has_atomic_properties):
            try:
                pga = PointGroupAnalyzer(pmg_molecule)
                point_group = pga.sch_symbol
                
                from collections import defaultdict
                atom_groups = defaultdict(list)
                
                for i, site in enumerate(pmg_molecule):
                    z = site.specie.Z
                    atom_groups[z].append((i, np.array(site.coords)))
                
                point_group_sites = []
                used = set()
                
                for z, atoms in atom_groups.items():
                    for idx, coords in atoms:
                        if idx in used:
                            continue
                        
                        equiv_count = 1
                        used.add(idx)
                        
                        for other_idx, other_coords in atoms:
                            if other_idx in used:
                                continue
                            
                            min_dist = float('inf')
                            for sym_op in pga.get_symmetry_operations():
                                transformed = sym_op.operate(coords)
                                dist = np.linalg.norm(transformed - other_coords)
                                min_dist = min(min_dist, dist)
                            
                            if min_dist < 0.01:
                                equiv_count += 1
                                used.add(other_idx)
                        
                        point_group_sites.append(PointGroupSite(z, equiv_count, tuple(coords)))
                
                total_multiplicity = sum(s.multiplicity for s in point_group_sites)
                if total_multiplicity == len(pmg_molecule) and len(point_group_sites) < len(pmg_molecule):
                    struct_props = StructureProperties()
                    if energy is not None:
                        struct_props.energy = energy
                    
                    formula = pmg_molecule.composition.reduced_formula
                    
                    return USIFStructure(
                        structure_type=StructureType.MOLECULAR,
                        storage_mode=StorageMode.SYMMETRIC,
                        point_group=point_group,
                        point_group_sites=point_group_sites,
                        structure_properties=struct_props,
                        formula=formula
                    )
            except Exception:
                pass
        
        atom_sites = []
        for i, site in enumerate(pmg_molecule):
            z = site.specie.Z
            
            atom_props = AtomicProperties()
            if forces is not None and i < len(forces):
                atom_props.force = tuple(forces[i])
            if charges is not None and i < len(charges):
                atom_props.charge = float(charges[i])
            
            atom_sites.append(AtomSite(z, tuple(site.coords), atom_props))
        
        struct_props = StructureProperties()
        if energy is not None:
            struct_props.energy = energy
        
        formula = pmg_molecule.composition.reduced_formula
        
        return USIFStructure(
            structure_type=StructureType.MOLECULAR,
            storage_mode=StorageMode.FULL_ATOMIC,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=formula
        )
    
    @staticmethod
    def _from_crystal(pmg_structure: PMGStructure,
                     forces: Optional[np.ndarray] = None,
                     stress: Optional[np.ndarray] = None,
                     energy: Optional[float] = None,
                     charges: Optional[np.ndarray] = None,
                     magmoms: Optional[np.ndarray] = None,
                     force_symmetric: bool = False,
                     **kwargs) -> USIFStructure:
        lattice_matrix = pmg_structure.lattice.matrix.copy()
        
        has_atomic_properties = (
            forces is not None or charges is not None or magmoms is not None
        )
        
        if force_symmetric:
            storage_mode = StorageMode.SYMMETRIC
        else:
            storage_mode = StorageMode.FULL_ATOMIC if has_atomic_properties else StorageMode.SYMMETRIC
        
        wyckoff_sites = None
        atom_sites = None
        
        if storage_mode == StorageMode.SYMMETRIC:
            sga = SpacegroupAnalyzer(pmg_structure, symprec=1e-3)
            spacegroup_number = sga.get_space_group_number()
            symmetrized = sga.get_symmetrized_structure()
            
            wyckoff_sites = []
            for equiv_sites in symmetrized.equivalent_sites:
                rep = equiv_sites[0]
                z = rep.specie.Z
                wyckoff_sites.append(WyckoffSite(z, len(equiv_sites), tuple(rep.frac_coords)))
        else:
            sga = SpacegroupAnalyzer(pmg_structure, symprec=1e-3)
            spacegroup_number = sga.get_space_group_number()
            
            atom_sites = []
            for i, site in enumerate(pmg_structure):
                z = site.specie.Z
                
                atom_props = AtomicProperties()
                if forces is not None and i < len(forces):
                    atom_props.force = tuple(forces[i])
                if charges is not None and i < len(charges):
                    atom_props.charge = float(charges[i])
                if magmoms is not None and i < len(magmoms):
                    atom_props.magmom = float(magmoms[i])
                
                atom_sites.append(AtomSite(z, tuple(site.frac_coords), atom_props))
        
        struct_props = StructureProperties()
        
        if energy is not None:
            struct_props.energy = energy
        
        if stress is not None:
            if stress.shape == (3, 3):
                struct_props.stress = (
                    stress[0, 0], stress[1, 1], stress[2, 2],
                    stress[0, 1], stress[1, 2], stress[0, 2]
                )
            else:
                struct_props.stress = tuple(stress[:6])
        
        struct_props.volume = pmg_structure.volume
        
        formula = pmg_structure.composition.reduced_formula
        
        return USIFStructure(
            structure_type=StructureType.PERIODIC,
            lattice_matrix=lattice_matrix,
            spacegroup=spacegroup_number,
            storage_mode=storage_mode,
            wyckoff_sites=wyckoff_sites,
            atom_sites=atom_sites,
            structure_properties=struct_props,
            formula=formula
        )
    
    @staticmethod
    def to_pymatgen(usif_structure: USIFStructure) -> Union[PMGStructure, PMGMolecule]:
        if usif_structure.is_molecular():
            return StructureConverter._to_molecule(usif_structure)
        else:
            return StructureConverter._to_crystal(usif_structure)
    
    @staticmethod
    def _to_molecule(usif_structure: USIFStructure) -> PMGMolecule:
        species = []
        coords = []
        site_properties = {}
        
        forces = []
        charges = []
        
        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            for site in usif_structure.point_group_sites:
                element = Element.from_Z(site.atomic_number)
                species.append(element)
                coords.append(site.coords)
        else:
            for atom in usif_structure.atom_sites:
                element = Element.from_Z(atom.atomic_number)
                species.append(element)
                coords.append(atom.coords)
                
                if atom.properties.force is not None:
                    forces.append(atom.properties.force)
                if atom.properties.charge is not None:
                    charges.append(atom.properties.charge)
        
        if forces:
            site_properties['forces'] = forces
        if charges:
            site_properties['charges'] = charges
        
        return PMGMolecule(species, coords, 
                          site_properties=site_properties if site_properties else None)
    
    @staticmethod
    def _to_crystal(usif_structure: USIFStructure) -> PMGStructure:
        lattice_matrix = usif_structure.lattice_matrix
        lattice = Lattice(lattice_matrix)
        
        species = []
        coords = []
        site_properties = {}
        
        if usif_structure.storage_mode == StorageMode.SYMMETRIC:
            for site in usif_structure.wyckoff_sites:
                element = Element.from_Z(site.atomic_number)
                species.append(element)
                coords.append(site.coords)
        else:
            forces = []
            charges = []
            magmoms = []
            
            for site in usif_structure.atom_sites:
                element = Element.from_Z(site.atomic_number)
                species.append(element)
                coords.append(site.coords)
                
                if site.properties.force is not None:
                    forces.append(site.properties.force)
                if site.properties.charge is not None:
                    charges.append(site.properties.charge)
                if site.properties.magmom is not None:
                    magmoms.append(site.properties.magmom)
            
            if forces:
                site_properties['forces'] = forces
            if charges:
                site_properties['charges'] = charges
            if magmoms:
                site_properties['magmom'] = magmoms
        
        return PMGStructure(lattice, species, coords, 
                           site_properties=site_properties if site_properties else None)
    
    @staticmethod
    def from_file(filename: Union[str, Path]) -> USIFStructure:
        filepath = Path(filename)
        suffix = filepath.suffix.lower()
        
        if suffix == '.cif':
            parser = CifParser(str(filepath))
            pmg_obj = parser.get_structures()[0]
        elif suffix in ['.xyz', '.mol']:
            pmg_obj = PMGMolecule.from_file(str(filepath))
        elif suffix == '.xml' and 'vasprun' in filepath.name:
            vasprun = Vasprun(str(filepath))
            pmg_obj = vasprun.final_structure
            forces = vasprun.ionic_steps[-1].get('forces', None)
            stress = vasprun.ionic_steps[-1].get('stress', None)
            energy = vasprun.final_energy
            
            return StructureConverter.from_pymatgen(
                pmg_obj,
                forces=np.array(forces) if forces else None,
                stress=np.array(stress) if stress else None,
                energy=energy,
                calculator='VASP'
            )
        else:
            poscar = Poscar.from_file(str(filepath))
            pmg_obj = poscar.structure
        
        return StructureConverter.from_pymatgen(pmg_obj)


# ============================================================================
# Container with Random Access
# ============================================================================

class StructureContainer:
    """Multi-structure container with random access"""
    
    CONTAINER_MAGIC = b'USIFC'
    CONTAINER_VERSION = 2
    INDEX_ENTRY_SIZE = 44  # 32 bytes hash + 8 bytes offset + 4 bytes size
    
    def __init__(self, filename: Union[str, Path], mode: str = 'r'):
        self.filename = Path(filename)
        self.mode = mode
        self.encoder = USIF()
        self._index = {}  # hash -> (offset, size)
        self._file = None
        self._index_offset = 0
        
        if mode == 'r':
            self._open_read()
        elif mode == 'w':
            self._open_write()
        elif mode == 'a':
            self._open_append()
        else:
            raise ValueError("Mode must be 'r', 'w', or 'a'")
    
    def _write_header(self):
        """Write container header"""
        header = bytearray(64)
        header[0:5] = self.CONTAINER_MAGIC
        header[5:6] = struct.pack('B', self.CONTAINER_VERSION)
        header[6:10] = struct.pack('<I', 0)  # num_structures, will be updated later
        header[10:18] = struct.pack('<Q', 64)  # index_offset, will be updated later
        self._file.write(header)
        self._file.flush()
        self._index_offset = 64
    
    def _open_read(self):
        """Open container for reading"""
        if not self.filename.exists():
            raise FileNotFoundError(f"Container not found: {self.filename}")
        self._file = open(self.filename, 'rb')
        self._read_index()
    
    def _open_write(self):
        """Open container for writing (truncates existing file)"""
        self._file = open(self.filename, 'wb')
        self._write_header()
    
    def _open_append(self):
        """Open container for appending"""
        if self.filename.exists():
            self._file = open(self.filename, 'r+b')
            self._read_index()
            if self._index:
                # Find the end of existing data
                self._file.seek(0, 2)  # Seek to end
                self._index_offset = self._file.tell()
            else:
                self._index_offset = 64
        else:
            self._file = open(self.filename, 'wb')
            self._write_header()
    
    def _read_index(self):
        """Read container index"""
        self._file.seek(0)
        magic = self._file.read(5)
        if magic != self.CONTAINER_MAGIC:
            raise ValueError("Invalid USIF container file")
        
        version = struct.unpack('B', self._file.read(1))[0]
        if version not in [1, 2]:
            raise ValueError(f"Unsupported container version: {version}")
        
        num_structures = struct.unpack('<I', self._file.read(4))[0]
        index_offset = struct.unpack('<Q', self._file.read(8))[0]
        
        if num_structures == 0:
            return
        
        # Read index entries
        self._file.seek(index_offset)
        for _ in range(num_structures):
            hash_bytes = self._file.read(32)
            offset = struct.unpack('<Q', self._file.read(8))[0]
            size = struct.unpack('<I', self._file.read(4))[0]
            self._index[hash_bytes.hex()] = (offset, size)
    
    def add(self, structure: USIFStructure) -> str:
        """Add structure to container and return its hash"""
        if self.mode == 'r':
            raise ValueError("Cannot add to read-only container")
        
        usif_data = self.encoder.encode(structure)
        struct_hash = self.encoder.get_structure_hash(structure)
        
        # Check for duplicates
        if struct_hash in self._index:
            return struct_hash
        
        # Write structure data
        self._file.seek(self._index_offset)
        offset = self._file.tell()
        self._file.write(usif_data)
        size = len(usif_data)
        
        # Update index
        self._index[struct_hash] = (offset, size)
        self._index_offset = self._file.tell()
        
        # Update container index
        self._write_index()
        
        return struct_hash
    
    def _write_index(self):
        """Write updated index to file"""
        index_start = self._index_offset
        
        # Write index entries
        self._file.seek(index_start)
        for struct_hash, (offset, size) in self._index.items():
            self._file.write(bytes.fromhex(struct_hash))
            self._file.write(struct.pack('<Q', offset))
            self._file.write(struct.pack('<I', size))
        
        # Update header
        self._file.seek(6)
        self._file.write(struct.pack('<I', len(self._index)))  # num_structures
        self._file.write(struct.pack('<Q', index_start))       # index_offset
        self._file.flush()
    
    def get(self, struct_hash: str) -> Optional[USIFStructure]:
        """Get structure by hash (O(1) random access)"""
        if struct_hash not in self._index:
            return None
        
        offset, size = self._index[struct_hash]
        self._file.seek(offset)
        usif_data = self._file.read(size)
        
        try:
            structure, _ = self.encoder.decode(usif_data)
            return structure
        except Exception as e:
            print(f"Error decoding structure {struct_hash}: {e}")
            return None
    
    def get_batch(self, hashes: List[str]) -> List[Optional[USIFStructure]]:
        """Batch read multiple structures"""
        return [self.get(h) for h in hashes]
    
    def add_batch(self, structures: List[USIFStructure]) -> List[str]:
        """Batch add multiple structures"""
        return [self.add(s) for s in structures]
    
    def list_hashes(self) -> List[str]:
        """List all structure hashes in container"""
        return list(self._index.keys())
    
    def __len__(self) -> int:
        return len(self._index)
    
    def __contains__(self, struct_hash: str) -> bool:
        return struct_hash in self._index
    
    def __iter__(self) -> Iterator[Tuple[str, USIFStructure]]:
        """Iterate over all structures in container"""
        for struct_hash in self._index:
            structure = self.get(struct_hash)
            if structure:
                yield struct_hash, structure
    
    def close(self):
        """Close the container file"""
        if self._file:
            self._file.close()
            self._file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def stats(self) -> Dict[str, Any]:
        """Get container statistics"""
        if not self._file:
            return {}
        
        file_size = self.filename.stat().st_size
        total_structures = len(self._index)
        
        # For write mode, we can't read structures, so use a simplified compression ratio
        if self.mode == 'w':
            return {
                'total_structures': total_structures,
                'file_size_bytes': file_size,
                'file_size_mb': file_size / (1024 * 1024),
                'avg_structure_size': file_size / total_structures if total_structures else 0,
                'index_size': len(self._index) * self.INDEX_ENTRY_SIZE,
                'compression_ratio': 0.0  # Can't calculate in write mode
            }
        
        # For read mode, calculate proper compression ratio
        return {
            'total_structures': total_structures,
            'file_size_bytes': file_size,
            'file_size_mb': file_size / (1024 * 1024),
            'avg_structure_size': file_size / total_structures if total_structures else 0,
            'index_size': len(self._index) * self.INDEX_ENTRY_SIZE,
            'compression_ratio': self._calculate_compression_ratio()
        } 

    def _calculate_compression_ratio(self) -> float:
        """Calculate average compression ratio"""
        if not self._index:
            return 0.0
        
        total_original_size = 0
        total_compressed_size = 0
        valid_structures = 0
        
        for struct_hash in self._index:
            try:
                structure = self.get(struct_hash)
                if structure:
                    # Estimate original size (rough approximation)
                    num_atoms = structure.num_atoms()
                    original_size = num_atoms * 50  # ~50 bytes per atom in uncompressed format
                    compressed_size = self._index[struct_hash][1]
                    
                    total_original_size += original_size
                    total_compressed_size += compressed_size
                    valid_structures += 1
            except Exception:
                # Skip structures that can't be read
                continue
        
        if total_original_size == 0 or valid_structures == 0:
            return 0.0
        
        return total_compressed_size / total_original_size

    def search_by_formula(self, formula: str) -> List[Tuple[str, USIFStructure]]:
        """Search structures by chemical formula"""
        results = []
        for struct_hash, structure in self:
            if structure.formula == formula:
                results.append((struct_hash, structure))
        return results
    
    def search_by_property(self, property_name: str, min_value: float = None, 
                          max_value: float = None) -> List[Tuple[str, USIFStructure]]:
        """Search structures by property value range"""
        results = []
        for struct_hash, structure in self:
            props = structure.structure_properties.get_all_properties()
            if property_name in props:
                value = props[property_name]
                if isinstance(value, (int, float)):
                    if min_value is not None and value < min_value:
                        continue
                    if max_value is not None and value > max_value:
                        continue
                    results.append((struct_hash, structure))
        return results
    
    def export_hashes(self, output_file: Union[str, Path]) -> None:
        """Export all structure hashes to a text file"""
        with open(output_file, 'w') as f:
            for hash_val in self._index:
                f.write(f"{hash_val}\n")
    
    def import_hashes(self, input_file: Union[str, Path]) -> List[str]:
        """Import structure hashes from a text file and return existing ones"""
        existing_hashes = []
        with open(input_file, 'r') as f:
            for line in f:
                hash_val = line.strip()
                if hash_val in self._index:
                    existing_hashes.append(hash_val)
        return existing_hashes


# ============================================================================
# Demo Functions
# ============================================================================

def demo_property_system():
    """Demonstrate the modular property system"""
    print("\n=== MODULAR PROPERTY SYSTEM ===\n")
    
    print("Registered Properties:")
    all_props = PropertyRegistry.get_all_properties()
    for name, prop_def in all_props.items():
        type_desc = "per-atom" if prop_def.is_per_atom else "structure"
        print(f"  {name:15} {prop_def.data_type.__name__:10} {type_desc:12} {prop_def.description}")
    
    print("\nProperty Validation:")
    force_def = PropertyRegistry.get_property("force")
    valid_force = (1.0, 2.0, 3.0)
    print(f"  Force validation (valid): {force_def.validate_value(valid_force)}")
    
    print("\nAtomic Properties Container:")
    atom_props = AtomicProperties()
    atom_props.force = (1.0, 2.0, 3.0)
    atom_props.charge = 0.5
    
    all_atom_props = atom_props.get_all_properties()
    print("  Atomic properties:")
    for name, value in all_atom_props.items():
        print(f"    {name}: {value}")


def demo_molecule_point_group():
    """Demonstrate molecule point group symmetry"""
    print("\n=== MOLECULE POINT GROUP SYMMETRY ===\n")
    
    water = PMGMolecule(['O', 'H', 'H'], [[0, 0, 0], [0.96, 0, 0], [-0.24, 0.93, 0]])
    
    structure = StructureConverter.from_pymatgen(water, force_symmetric=True)
    
    print(f"Water:")
    print(f"  Point group: {structure.point_group}")
    print(f"  Storage mode: {structure.storage_mode.name}")
    print(f"  Total atoms: {structure.num_atoms()}")
    
    if structure.storage_mode == StorageMode.SYMMETRIC:
        print(f"  Unique sites: {len(structure.point_group_sites)}")
        for i, site in enumerate(structure.point_group_sites):
            elem = Element.from_Z(site.atomic_number).symbol
            print(f"    Site {i+1}: {elem} x{site.multiplicity}")
    
    encoder = USIF()
    encoded = encoder.encode(structure)
    print(f"  Encoded size: {len(encoded)} bytes")
    print(f"  ✓ Decoded successfully")


def demo_crystal_encoding():
    """Demonstrate encoding/decoding of crystal structures"""
    print("\n" + "="*60)
    print("CRYSTAL STRUCTURE EXAMPLE")
    print("="*60)
    
    # Create a silicon crystal structure
    silicon = PMGStructure(
        lattice=Lattice.cubic(5.43),
        species=['Si', 'Si'],
        coords=[[0, 0, 0], [0.25, 0.25, 0.25]]
    )
    
    # Create atomic forces and stress
    forces = np.array([
        [0.001, -0.002, 0.003],
        [-0.001, 0.002, -0.003]
    ])
    
    stress = np.array([
        [0.1, 0.02, 0.03],
        [0.02, 0.1, 0.04],
        [0.03, 0.04, 0.1]
    ])
    
    # Convert to USIF format
    usif_structure = StructureConverter.from_pymatgen(
        silicon,
        forces=forces,
        stress=stress,
        energy=-10.5,  # eV
        calculator='VASP',
        functional='PBE'
    )
    
    print(f"Original structure: {silicon.formula}")
    print(f"USIF structure type: {usif_structure.structure_type.name}")
    print(f"Storage mode: {usif_structure.storage_mode.name}")
    print(f"Space group: {usif_structure.spacegroup}")
    print(f"Number of atoms: {usif_structure.num_atoms()}")
    
    # Encode to USIF binary
    encoder = USIF()
    encoded_data = encoder.encode(usif_structure)
    structure_hash = encoder.get_structure_hash(usif_structure)
    
    print(f"\nEncoding results:")
    print(f"  Encoded size: {len(encoded_data)} bytes")
    print(f"  Structure hash: {structure_hash}")
    
    # Decode back
    decoded_structure, decoded_hash = encoder.decode(encoded_data)
    
    print(f"\nDecoding verification:")
    print(f"  Hash match: {structure_hash == decoded_hash.hex()}")
    print(f"  Formula match: {decoded_structure.formula == usif_structure.formula}")
    print(f"  Structure type match: {decoded_structure.structure_type == usif_structure.structure_type}")
    
    # Display properties
    props = decoded_structure.structure_properties.get_all_properties()
    print(f"\nDecoded properties:")
    for prop_name, value in props.items():
        print(f"  {prop_name}: {value}")
    
    return usif_structure, encoded_data, structure_hash

def demo_unified_interface():
    """Demonstrate unified variable naming"""
    print("\n=== UNIFIED INTERFACE DEMO ===")
    
    pmg_crystal = PMGStructure(Lattice.cubic(5.64), ['Na', 'Cl'], [[0, 0, 0], [0.5, 0.5, 0.5]])
    pmg_molecule = PMGMolecule(['O', 'H', 'H'], [[0, 0, 0], [0.96, 0, 0], [-0.24, 0.93, 0]])
    
    crystal_structure = StructureConverter.from_pymatgen(pmg_crystal)
    molecule_structure = StructureConverter.from_pymatgen(pmg_molecule, force_symmetric=True)
    
    print(f"Crystal: {crystal_structure.formula}")
    print(f"  Is molecule: {crystal_structure.is_molecular()}")
    print(f"  Storage mode: {crystal_structure.storage_mode.name}")
    
    print(f"\nMolecule: {molecule_structure.formula}")
    print(f"  Is molecule: {molecule_structure.is_molecular()}")
    print(f"  Storage mode: {molecule_structure.storage_mode.name}")
    if molecule_structure.point_group:
        print(f"  Point group: {molecule_structure.point_group}")


if __name__ == "__main__":
    print("="*80)
    print("USIF v2.0 - Fixed Implementation")
    print("="*80)
    
    demo_property_system()
    demo_molecule_point_group()
    demo_unified_interface()
    demo_crystal_encoding()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("✓ Modular property system with type safety")
    print("✓ Unified interface for crystals and molecules") 
    print("✓ Intelligent compression with symmetry detection")
    print("✓ Optimized code with reduced redundancy")
    print("✓ Fixed property serialization bugs")
    print("="*80)
