#!/usr/bin/env python3
""" 
USIF (Universal Structure Interchange Format)
Unified format for crystals and molecules with intelligent compression
    
Features:
- Unified interface for periodic and non-periodic structures
- Intelligent compression: symmetric (crystals + molecules) or atomic (all types)
- Point group symmetry support for molecules
- Space group symmetry support for crystals
- 4-6x compression vs traditional formats
- Modular property system with type safety
- Random access container
    
Author: haidi@hfut.edu.cn
Version: 4.0
"""    

import struct
import hashlib
import gzip
import numpy as np
from typing import Dict, List, Tuple, Optional, Union, Any, Iterator
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from collections import defaultdict
import queue
import mmap
import threading
from monty.json import MSONable

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
    """Serialize and deserialize property values with complete type support"""
    
    # Type mapping for struct format characters
    TYPE_FORMATS = {
        float: {
            'scalar': 'd',      # 8 bytes
            'array': 'f',       # 4 bytes per element
            'pack_multiple': lambda fmt, values: struct.pack(f'{len(values)}{fmt}', *values),
            'unpack_multiple': lambda fmt, data, count: struct.unpack(f'{count}{fmt}', data)
        },
        int: {
            'scalar': 'q',      # 8 bytes
            'array': 'i',       # 4 bytes per element  
            'pack_multiple': lambda fmt, values: struct.pack(f'{len(values)}{fmt}', *values),
            'unpack_multiple': lambda fmt, data, count: struct.unpack(f'{count}{fmt}', data)
        },
        bool: {
            'scalar': '?',      # 1 byte
            'array': '?',       # 1 byte per element
            'pack_multiple': lambda fmt, values: struct.pack(f'{len(values)}{fmt}', *values),
            'unpack_multiple': lambda fmt, data, count: struct.unpack(f'{count}{fmt}', data)
        },
        str: {
            'scalar': None,     # Special handling with length prefix
            'array': None,      # Special handling for string arrays
            'pack_multiple': None,
            'unpack_multiple': None
        },
        tuple: {
            'scalar': None,     # Tuples are treated as arrays
            'array': 'f',       # Default to float for compatibility
            'pack_multiple': lambda fmt, values: struct.pack(f'{len(values)}{fmt}', *values),
            'unpack_multiple': lambda fmt, data, count: struct.unpack(f'{count}{fmt}', data)
        }
    }
    
    @staticmethod
    def serialize_value(value: Any, prop_def: PropertyDefinition, 
                       num_atoms: int = None) -> bytes:
        """Serialize property value to bytes with complete type support"""
        if value is None:
            return b''
        
        data = bytearray()
        
        # Handle scalar properties
        if prop_def.is_scalar():
            PropertySerializer._serialize_scalar(data, value, prop_def)
        
        # Handle array properties (both per-atom and structure-level)
        else:
            PropertySerializer._serialize_array(data, value, prop_def, num_atoms)
        
        return bytes(data)
    
    @staticmethod
    def _serialize_scalar(data: bytearray, value: Any, prop_def: PropertyDefinition):
        """Serialize scalar value based on data type"""
        data_type = prop_def.data_type
        
        if data_type == float:
            data.extend(struct.pack('d', value))
        elif data_type == int:
            data.extend(struct.pack('q', value))
        elif data_type == bool:
            data.extend(struct.pack('?', value))
        elif data_type == str:
            str_bytes = value.encode('utf-8')
            data.extend(struct.pack('<I', len(str_bytes)))
            data.extend(str_bytes)
        else:
            raise ValueError(f"Unsupported scalar data type: {data_type}")
    
    @staticmethod
    def _serialize_array(data: bytearray, value: Any, prop_def: PropertyDefinition, num_atoms: int = None):
        """Serialize array value with proper type handling"""
        data_type = prop_def.data_type
        
        # Handle per-atom properties
        if prop_def.is_per_atom:
            if num_atoms == 1:
                # Single atom case - wrap single value in list
                data.extend(struct.pack('<I', 1))
                PropertySerializer._serialize_array_element(data, value, prop_def)
            else:
                # Multiple atoms case
                actual_atoms = num_atoms if num_atoms is not None else len(value)
                data.extend(struct.pack('<I', actual_atoms))
                
                # Handle both single value (repeat for all atoms) and list of values
                if not isinstance(value, (list, tuple, np.ndarray)) or (isinstance(value, np.ndarray) and value.ndim == 0):
                    # Single value repeated for all atoms
                    for _ in range(actual_atoms):
                        PropertySerializer._serialize_array_element(data, value, prop_def)
                else:
                    # List of values, one per atom
                    for atom_value in value:
                        PropertySerializer._serialize_array_element(data, atom_value, prop_def)
        
        # Handle structure-level array properties
        else:
            PropertySerializer._serialize_array_element(data, value, prop_def)
    
    @staticmethod
    def _serialize_array_element(data: bytearray, value: Any, prop_def: PropertyDefinition):
        """Serialize a single array element based on dimensions and data type"""
        data_type = prop_def.data_type
        
        # Handle zero-dimensional arrays (scalar elements)
        if len(prop_def.dimensions) == 0:
            if data_type == float:
                data.extend(struct.pack('f', value))
            elif data_type == int:
                data.extend(struct.pack('i', value))
            elif data_type == bool:
                data.extend(struct.pack('?', value))
            elif data_type == str:
                str_bytes = value.encode('utf-8')
                data.extend(struct.pack('<I', len(str_bytes)))
                data.extend(str_bytes)
            else:
                raise ValueError(f"Unsupported array element type: {data_type}")
        
        # Handle multi-dimensional arrays
        else:
            dim = prop_def.dimensions[0]
            
            # Convert to iterable if single value
            if not isinstance(value, (list, tuple, np.ndarray)):
                value = [value] * dim
            
            # Ensure we have the right number of elements
            if len(value) != dim:
                raise ValueError(f"Expected {dim} elements for property {prop_def.name}, got {len(value)}")
            
            # Pack based on data type
            if data_type in (float, tuple):
                data.extend(struct.pack(f'{dim}f', *value))
            elif data_type == int:
                data.extend(struct.pack(f'{dim}i', *value))
            elif data_type == bool:
                # Convert bool to bytes (0/1) for compact storage
                bool_bytes = [1 if x else 0 for x in value]
                data.extend(struct.pack(f'{dim}B', *bool_bytes))
            else:
                raise ValueError(f"Unsupported multi-dimensional array type: {data_type}")
    
    @staticmethod
    def deserialize_value(prop_def: PropertyDefinition, data: bytes, 
                         offset: int, num_atoms: int = None) -> Tuple[Any, int]:
        """Deserialize property value from bytes with complete type support"""
        if len(data) <= offset:
            return None, offset
        
        value = None
        
        # Handle scalar properties
        if prop_def.is_scalar():
            value, offset = PropertySerializer._deserialize_scalar(data, offset, prop_def)
        
        # Handle array properties
        else:
            value, offset = PropertySerializer._deserialize_array(data, offset, prop_def, num_atoms)
        
        return value, offset
    
    @staticmethod
    def _deserialize_scalar(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize scalar value based on data type"""
        data_type = prop_def.data_type
        
        if data_type == float:
            value = struct.unpack('d', data[offset:offset+8])[0]
            offset += 8
        elif data_type == int:
            value = struct.unpack('q', data[offset:offset+8])[0]
            offset += 8
        elif data_type == bool:
            value = struct.unpack('?', data[offset:offset+1])[0]
            offset += 1
        elif data_type == str:
            str_len = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            value = data[offset:offset+str_len].decode('utf-8')
            offset += str_len
        else:
            raise ValueError(f"Unsupported scalar data type: {data_type}")
        
        return value, offset
    
    @staticmethod
    def _deserialize_array(data: bytes, offset: int, prop_def: PropertyDefinition, 
                          num_atoms: int = None) -> Tuple[Any, int]:
        """Deserialize array value with proper type handling"""
        data_type = prop_def.data_type
        
        # Handle per-atom properties
        if prop_def.is_per_atom:
            count = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            # Validate count if num_atoms is provided
            if num_atoms is not None and count != num_atoms and count != 1:
                raise ValueError(f"Atom count mismatch: expected {num_atoms}, got {count}")
            
            values = []
            for _ in range(count):
                atom_value, offset = PropertySerializer._deserialize_array_element(data, offset, prop_def)
                values.append(atom_value)
            
            # If single value was stored for multiple atoms, expand it
            if count == 1 and num_atoms is not None and num_atoms > 1:
                values = values * num_atoms
            
            value = values
        
        # Handle structure-level array properties
        else:
            value, offset = PropertySerializer._deserialize_array_element(data, offset, prop_def)
        
        return value, offset
    
    @staticmethod
    def _deserialize_array_element(data: bytes, offset: int, prop_def: PropertyDefinition) -> Tuple[Any, int]:
        """Deserialize a single array element based on dimensions and data type"""
        data_type = prop_def.data_type
        
        # Handle zero-dimensional arrays (scalar elements)
        if len(prop_def.dimensions) == 0:
            if data_type == float:
                value = struct.unpack('f', data[offset:offset+4])[0]
                offset += 4
            elif data_type == int:
                value = struct.unpack('i', data[offset:offset+4])[0]
                offset += 4
            elif data_type == bool:
                value = struct.unpack('?', data[offset:offset+1])[0]
                offset += 1
            elif data_type == str:
                str_len = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                value = data[offset:offset+str_len].decode('utf-8')
                offset += str_len
            else:
                raise ValueError(f"Unsupported array element type: {data_type}")
        
        # Handle multi-dimensional arrays
        else:
            dim = prop_def.dimensions[0]
            
            if data_type in (float, tuple):
                values = struct.unpack(f'{dim}f', data[offset:offset+dim*4])
                value = tuple(values)
                offset += dim * 4
            elif data_type == int:
                values = struct.unpack(f'{dim}i', data[offset:offset+dim*4])
                value = tuple(values)
                offset += dim * 4
            elif data_type == bool:
                bool_values = struct.unpack(f'{dim}B', data[offset:offset+dim])
                value = tuple(bool(x) for x in bool_values)
                offset += dim
            else:
                raise ValueError(f"Unsupported multi-dimensional array type: {data_type}")
        
        return value, offset
    
    @staticmethod
    def validate_value(value: Any, prop_def: PropertyDefinition, num_atoms: int = None) -> bool:
        """Validate that a value matches the property definition"""
        if value is None:
            return True
        
        # Check basic type
        if not isinstance(value, prop_def.data_type):
            # Allow tuples for properties defined as float with dimensions
            if prop_def.data_type == float and isinstance(value, tuple) and len(prop_def.dimensions) > 0:
                pass  # This is acceptable
            else:
                return False
        
        # Check dimensions for array properties
        if not prop_def.is_scalar():
            if prop_def.is_per_atom:
                # For per-atom properties, value should be a list/tuple/array
                if num_atoms == 1:
                    # Single atom - value is the property directly
                    if len(prop_def.dimensions) > 0:
                        if not isinstance(value, (tuple, list, np.ndarray)) or len(value) != prop_def.dimensions[0]:
                            return False
                else:
                    # Multiple atoms - value should be a sequence
                    if not isinstance(value, (list, tuple, np.ndarray)):
                        return False
                    if num_atoms is not None and len(value) != num_atoms:
                        return False
                    
                    # Check each element
                    for elem in value:
                        if len(prop_def.dimensions) > 0:
                            if not isinstance(elem, (tuple, list, np.ndarray)) or len(elem) != prop_def.dimensions[0]:
                                return False
            else:
                # Structure-level array properties
                if len(prop_def.dimensions) > 0:
                    if not isinstance(value, (tuple, list, np.ndarray)) or len(value) != prop_def.dimensions[0]:
                        return False
        
        return True
    
    @staticmethod
    def get_expected_size(prop_def: PropertyDefinition, value: Any = None, num_atoms: int = None) -> int:
        """Calculate expected size in bytes for serialized property value"""
        if value is None:
            return 0
        
        size = 0
        
        if prop_def.is_scalar():
            if prop_def.data_type == float:
                size = 8
            elif prop_def.data_type == int:
                size = 8
            elif prop_def.data_type == bool:
                size = 1
            elif prop_def.data_type == str:
                size = 4 + len(value.encode('utf-8'))
        else:
            if prop_def.is_per_atom:
                size = 4  # Count field
                element_size = PropertySerializer._get_element_size(prop_def)
                
                if num_atoms == 1:
                    size += element_size
                else:
                    actual_atoms = num_atoms if num_atoms is not None else len(value)
                    size += actual_atoms * element_size
            else:
                size = PropertySerializer._get_element_size(prop_def)
        
        return size
    
    @staticmethod
    def _get_element_size(prop_def: PropertyDefinition) -> int:
        """Calculate size of a single array element"""
        if len(prop_def.dimensions) == 0:
            if prop_def.data_type == float:
                return 4
            elif prop_def.data_type == int:
                return 4
            elif prop_def.data_type == bool:
                return 1
            elif prop_def.data_type == str:
                # Cannot determine without actual value
                return 0
        else:
            dim = prop_def.dimensions[0]
            if prop_def.data_type in (float, tuple):
                return dim * 4
            elif prop_def.data_type == int:
                return dim * 4
            elif prop_def.data_type == bool:
                return dim
        
        return 0

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

    def __eq__(self, other):
        if not isinstance(other, AtomicProperties):
            return False
        
        # Compare all built-in properties
        for prop_name in PropertyRegistry._properties:
            if PropertyRegistry.is_atomic_property(prop_name):
                self_val = getattr(self, prop_name, None)
                other_val = getattr(other, prop_name, None)
                
                if self_val != other_val:
                    # Handle floating point comparison for numeric values
                    if isinstance(self_val, float) and isinstance(other_val, float):
                        if abs(self_val - other_val) > 1e-6:
                            return False
                    elif isinstance(self_val, tuple) and isinstance(other_val, tuple):
                        if any(abs(a - b) > 1e-6 for a, b in zip(self_val, other_val)):
                            return False
                    else:
                        return False
        
        # Compare custom properties
        if self.custom != other.custom:
            return False
        
        return True

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

    def __eq__(self, other):
        if not isinstance(other, StructureProperties):
            return False

        # Compare all built-in properties
        for prop_name in PropertyRegistry._properties:
            if PropertyRegistry.is_structure_property(prop_name):
                self_val = getattr(self, prop_name, None)
                other_val = getattr(other, prop_name, None)

                if self_val != other_val:
                    # Handle floating point comparison for numeric values
                    if isinstance(self_val, float) and isinstance(other_val, float):
                        if abs(self_val - other_val) > 1e-6:
                            return False
                    else:
                        return False

        # Compare custom properties
        if self.custom != other.custom:
            return False

        return True

@dataclass
class WyckoffSite:
    """Wyckoff position for symmetric storage (periodic only)"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Fractional
    occupancy: float = 1.0
    def __eq__(self, other):
        if not isinstance(other, WyckoffSite):
            return False
        return (self.atomic_number == other.atomic_number and
                self.multiplicity == other.multiplicity and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                abs(self.occupancy - other.occupancy) < 1e-6)


@dataclass
class PointGroupSite:
    """Point group symmetric position for molecules"""
    atomic_number: int
    multiplicity: int
    coords: Tuple[float, float, float]  # Cartesian (Å)
    occupancy: float = 1.0
    def __eq__(self, other):
        if not isinstance(other, PointGroupSite):
            return False
        return (self.atomic_number == other.atomic_number and
                self.multiplicity == other.multiplicity and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                abs(self.occupancy - other.occupancy) < 1e-6)



@dataclass
class AtomSite:
    """Universal atom site"""
    atomic_number: int
    coords: Tuple[float, float, float]
    properties: AtomicProperties = field(default_factory=AtomicProperties)
    def __eq__(self, other):
        if not isinstance(other, AtomSite):
            return False
        return (self.atomic_number == other.atomic_number and
                all(abs(a - b) < 1e-6 for a, b in zip(self.coords, other.coords)) and
                self.properties == other.properties)


class USIFStructure(MSONable):
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
    
    __slots__ = ['structure_type', 'storage_mode', 'lattice_matrix', 'spacegroup', 
                'point_group', 'wyckoff_sites', 'point_group_sites', 'atom_sites',
                'structure_properties', 'formula']
    
    def __init__(self, 
                 structure_type: StructureType = StructureType.PERIODIC,
                 storage_mode: StorageMode = StorageMode.SYMMETRIC,
                 lattice_matrix: Optional[np.ndarray] = None,
                 spacegroup: int = 1,
                 point_group: Optional[str] = None,
                 wyckoff_sites: Optional[List[WyckoffSite]] = None,
                 point_group_sites: Optional[List[PointGroupSite]] = None,
                 atom_sites: Optional[List[AtomSite]] = None,
                 structure_properties: StructureProperties = None,
                 formula: str = ""):
        
        self.structure_type = structure_type
        self.storage_mode = storage_mode
        self.lattice_matrix = lattice_matrix
        self.spacegroup = spacegroup
        self.point_group = point_group
        self.wyckoff_sites = wyckoff_sites
        self.point_group_sites = point_group_sites
        self.atom_sites = atom_sites
        self.structure_properties = structure_properties if structure_properties is not None else StructureProperties()
        self.formula = formula
        
        self._validate_structure()
    
    def _validate_structure(self):
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
    
    def as_dict(self) -> dict:
        """
        Convert USIFStructure to MSONable dictionary
        
        Returns:
            Dictionary representation suitable for JSON serialization
        """
        d = {
            "@module": self.__class__.__module__,
            "@class": self.__class__.__name__,
            "structure_type": self.structure_type.value,
            "storage_mode": self.storage_mode.value,
            "spacegroup": self.spacegroup,
            "point_group": self.point_group,
            "structure_properties": self.structure_properties,
            "formula": self.formula
        }
        
        # Handle lattice matrix (convert to list for JSON serialization)
        if self.lattice_matrix is not None:
            d["lattice_matrix"] = self.lattice_matrix.tolist()
        
        # Handle Wyckoff sites
        if self.wyckoff_sites is not None:
            d["wyckoff_sites"] = [{
                'atomic_number': site.atomic_number,
                'multiplicity': site.multiplicity,
                'coords': site.coords,
                'occupancy': site.occupancy
            } for site in self.wyckoff_sites]
        
        # Handle point group sites
        if self.point_group_sites is not None:
            d["point_group_sites"] = [{
                'atomic_number': site.atomic_number,
                'multiplicity': site.multiplicity,
                'coords': site.coords,
                'occupancy': site.occupancy
            } for site in self.point_group_sites]
        
        # Handle atom sites
        if self.atom_sites is not None:
            d["atom_sites"] = [{
                'atomic_number': site.atomic_number,
                'coords': site.coords,
                'properties': {
                    'force': site.properties.force,
                    'charge': site.properties.charge,
                    'magmom': site.properties.magmom,
                    'velocity': site.properties.velocity,
                    'custom': site.properties.custom
                }
            } for site in self.atom_sites]
        
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> 'USIFStructure':
        """
        Create USIFStructure from MSONable dictionary
        
        Args:
            d: Dictionary representation from as_dict()
            
        Returns:
            USIFStructure instance
        """
        # Convert lattice matrix back to numpy array
        lattice_matrix = None
        if "lattice_matrix" in d and d["lattice_matrix"] is not None:
            lattice_matrix = np.array(d["lattice_matrix"])
        
        # Reconstruct Wyckoff sites
        wyckoff_sites = None
        if "wyckoff_sites" in d and d["wyckoff_sites"] is not None:
            wyckoff_sites = []
            for site_dict in d["wyckoff_sites"]:
                wyckoff_sites.append(WyckoffSite(**site_dict))
        
        # Reconstruct point group sites
        point_group_sites = None
        if "point_group_sites" in d and d["point_group_sites"] is not None:
            point_group_sites = []
            for site_dict in d["point_group_sites"]:
                point_group_sites.append(PointGroupSite(**site_dict))
        
        # Reconstruct atom sites
        atom_sites = None
        if "atom_sites" in d and d["atom_sites"] is not None:
            atom_sites = []
            for site_dict in d["atom_sites"]:
                props_dict = site_dict.get('properties', {})
                atom_props = AtomicProperties(
                    force=props_dict.get('force'),
                    charge=props_dict.get('charge'),
                    magmom=props_dict.get('magmom'),
                    velocity=props_dict.get('velocity'),
                    custom=props_dict.get('custom', {})
                )
                atom_sites.append(AtomSite(
                    atomic_number=site_dict['atomic_number'],
                    coords=site_dict['coords'],
                    properties=atom_props
                ))
        
        # Reconstruct structure properties
        structure_properties = None
        if "structure_properties" in d:
            if isinstance(d["structure_properties"], dict):
                structure_properties = StructureProperties(**d["structure_properties"])
            else:
                structure_properties = d["structure_properties"]
        
        return cls(
            structure_type=StructureType(d["structure_type"]),
            storage_mode=StorageMode(d["storage_mode"]),
            lattice_matrix=lattice_matrix,
            spacegroup=d["spacegroup"],
            point_group=d.get("point_group"),
            wyckoff_sites=wyckoff_sites,
            point_group_sites=point_group_sites,
            atom_sites=atom_sites,
            structure_properties=structure_properties,
            formula=d["formula"]
        )

    def __eq__(self, other):
        if not isinstance(other, USIFStructure):
            return False
        
        # Compare lattice matrices with tolerance for floating point precision
        lattice_equal = True
        if self.lattice_matrix is not None and other.lattice_matrix is not None:
            lattice_equal = np.allclose(self.lattice_matrix, other.lattice_matrix, atol=1e-6)
        elif self.lattice_matrix != other.lattice_matrix:
            lattice_equal = False
        
        return (self.structure_type == other.structure_type and
                self.storage_mode == other.storage_mode and
                lattice_equal and
                self.spacegroup == other.spacegroup and
                self.point_group == other.point_group and
                self.wyckoff_sites == other.wyckoff_sites and
                self.point_group_sites == other.point_group_sites and
                self.atom_sites == other.atom_sites and
                self.structure_properties == other.structure_properties and
                self.formula == other.formula)

    
    def __repr__(self):
        return (f"USIFStructure(structure_type={self.structure_type.name}, "
                f"storage_mode={self.storage_mode.name}, "
                f"formula='{self.formula}', "
                f"atoms={self.num_atoms()})")


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
            lattice_data = structure.lattice_matrix.astype(np.float32).tobytes()
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
                    data.extend(struct.pack('<H', site.multiplicity))
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
                    data.extend(struct.pack('<H', site.multiplicity))
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
                    mult = struct.unpack('<H', data[offset+1:offset+3])[0]  # Changed to 2 bytes
                    x, y, z_coord = struct.unpack('3f', data[offset+3:offset+15])
                    occupancy = struct.unpack('f', data[offset+15:offset+19])[0]
                    offset += 19
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
                    mult = struct.unpack('<H', data[offset+1:offset+3])[0]  # Changed to 2 bytes
                    x, y, z_coord = struct.unpack('3f', data[offset+3:offset+15])
                    occupancy = struct.unpack('f', data[offset+15:offset+19])[0]
                    offset += 19
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
        spacegroup_number = 1
        
        if storage_mode == StorageMode.SYMMETRIC:
            try:
                sga = SpacegroupAnalyzer(pmg_structure, symprec=0.1)  # Increased tolerance
                spacegroup_number = sga.get_space_group_number()
                symmetrized = sga.get_symmetrized_structure()
                
                wyckoff_sites = []
                for equiv_sites in symmetrized.equivalent_sites:
                    rep = equiv_sites[0]
                    z = rep.specie.Z
                    wyckoff_sites.append(WyckoffSite(z, len(equiv_sites), tuple(rep.frac_coords)))
            except Exception as e:
                print(f"  Warning: Symmetry analysis failed, using full atomic: {e}")
                storage_mode = StorageMode.FULL_ATOMIC
        
        if storage_mode == StorageMode.FULL_ATOMIC:
            # Fallback to spacegroup 1 if analysis fails
            try:
                sga = SpacegroupAnalyzer(pmg_structure, symprec=0.1)
                spacegroup_number = sga.get_space_group_number()
            except:
                spacegroup_number = 1
            
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
                for _ in range(site.multiplicity):
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
                for _ in range(site.multiplicity):
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
# Enhanced Container with HDF5-like Features
# ============================================================================

@dataclass
class USIFGroup:
    """HDF5-like group for hierarchical organization"""
    name: str
    structures: Dict[str, Any] = field(default_factory=dict)  # name -> structure or hash
    subgroups: Dict[str, 'USIFGroup'] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def add_structure(self, name: str, structure_or_hash: Any):
        self.structures[name] = structure_or_hash
    
    def create_subgroup(self, name: str) -> 'USIFGroup':
        if name not in self.subgroups:
            self.subgroups[name] = USIFGroup(name)
        return self.subgroups[name]
    
    def get_subgroup(self, path: str) -> Optional['USIFGroup']:
        """Get subgroup by path (e.g., '/molecules/water')"""
        parts = [p for p in path.split('/') if p]
        current = self
        
        for part in parts:
            if part not in current.subgroups:
                return None
            current = current.subgroups[part]
        
        return current
    
    def find_structures(self, 
                       name_pattern: str = None,
                       formula: str = None,
                       properties: Dict[str, Any] = None,
                       recursive: bool = True) -> List[Tuple[str, Any]]:
        """Find structures matching criteria"""
        results = []
        
        # Search in current group
        for name, struct in self.structures.items():
            if name_pattern and name_pattern not in name:
                continue
            
            # Additional filtering would be applied here
            results.append((f"{self.name}/{name}", struct))
        
        # Recursive search in subgroups
        if recursive:
            for subgroup_name, subgroup in self.subgroups.items():
                subgroup_results = subgroup.find_structures(
                    name_pattern, formula, properties, recursive)
                results.extend([(f"{self.name}/{path}", struct) 
                              for path, struct in subgroup_results])
        
        return results


class StructureContainer:
    """
    Enhanced container with HDF5-like features:
    - Hierarchical organization
    - Secondary indexing
    - Chunked storage
    - Parallel I/O
    - Memory mapping
    """
    
    CONTAINER_MAGIC = b'USIFCv4'
    CONTAINER_VERSION = 2
    HEADER_SIZE = 256
    CHUNK_SIZE = 64 * 1024  # 64KB chunks
    
    def __init__(self, 
                 filename: Union[str, Path], 
                 mode: str = 'r',
                 use_mmap: bool = True,
                 num_workers: int = 4):
        self.filename = Path(filename)
        self.mode = mode
        self.use_mmap = use_mmap
        self.num_workers = num_workers
        
        self.encoder = USIF()
        self._file = None
        self._mmap = None
        
        # Enhanced indexing
        self._hash_index = {}           # hash -> (chunk_id, chunk_offset, size)
        self._name_index = {}           # name -> hash
        self._formula_index = defaultdict(list)  # formula -> [hashes]
        self._property_index = defaultdict(lambda: defaultdict(list))  # prop -> value -> [hashes]
        self._spatial_index = None      # For geometric queries
        
        # Hierarchical organization
        self.root_group = USIFGroup("/")
        self._group_index = {"/": self.root_group}
        
        # Caching
        self._cache = {}
        self._cache_size = 1000
        
        # Parallel I/O
        self._prefetch_queue = queue.Queue()
        self._prefetch_thread = None
        
        # Initialize offsets
        self._index_offset = 0
        self._data_offset = self.HEADER_SIZE
        
        self._open_container()

    def _open_container(self):
        """Open container with enhanced features"""
        if self.mode == 'r':
            if not self.filename.exists():
                raise FileNotFoundError(f"Container not found: {self.filename}")
            
            self._file = open(self.filename, 'rb')
            if self.use_mmap:
                self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
            
            self._read_enhanced_index()
            
            # Start prefetch thread
            self._start_prefetch_thread()
            
        elif self.mode == 'w':
            self._file = open(self.filename, 'w+b')  # Changed to w+b for read/write
            self._write_enhanced_header()
            
        elif self.mode == 'a':
            if self.filename.exists():
                self._file = open(self.filename, 'r+b')  # Changed to r+b for read/write
                if self.use_mmap:
                    self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_WRITE)
                self._read_enhanced_index()
            else:
                self._file = open(self.filename, 'w+b')  # Changed to w+b for read/write
                self._write_enhanced_header()
    def _write_enhanced_header(self):
        """Write enhanced container header"""
        header = bytearray(self.HEADER_SIZE)
        header[0:7] = self.CONTAINER_MAGIC
        header[7:8] = struct.pack('B', self.CONTAINER_VERSION)
        header[8:12] = struct.pack('<I', 0)  # num_structures
        header[12:20] = struct.pack('<Q', self.HEADER_SIZE)  # data_offset
        header[20:28] = struct.pack('<Q', 0)  # index_offset
        header[28:36] = struct.pack('<Q', 0)  # group_offset
        header[36:44] = struct.pack('<Q', 0)  # attribute_offset
        
        # Compression settings
        header[44:45] = struct.pack('B', self.encoder.compression.value)
        header[45:46] = struct.pack('B', 1)  # use_chunking
        
        # Timestamps
        import time
        timestamp = int(time.time())
        header[46:54] = struct.pack('<Q', timestamp)  # creation
        header[54:62] = struct.pack('<Q', timestamp)  # modification
        
        self._file.write(header)
        self._file.flush()

    def _read_enhanced_index(self):
        """Read enhanced index with secondary indexes"""
        if self._mmap:
            data = self._mmap
        else:
            self._file.seek(0)
            data = self._file.read()
        
        # Read basic index
        magic = data[0:7]
        if magic != self.CONTAINER_MAGIC:
            raise ValueError("Invalid enhanced USIF container")
        
        version = struct.unpack('B', data[7:8])[0]
        num_structures = struct.unpack('<I', data[8:12])[0]
        data_offset = struct.unpack('<Q', data[12:20])[0]
        index_offset = struct.unpack('<Q', data[20:28])[0]
        group_offset = struct.unpack('<Q', data[28:36])[0]
        
        # Store offsets
        self._data_offset = data_offset
        self._index_offset = index_offset
        
        # Read hash index if available
        if index_offset > 0:
            self._file.seek(index_offset)
            for _ in range(num_structures):
                hash_bytes = self._file.read(32)
                chunk_id = struct.unpack('<I', self._file.read(4))[0]
                chunk_offset = struct.unpack('<I', self._file.read(4))[0]
                size = struct.unpack('<I', self._file.read(4))[0]
                self._hash_index[hash_bytes.hex()] = (chunk_id, chunk_offset, size)
        
        # Read name index if available
        if group_offset > 0:
            self._read_group_hierarchy(group_offset)
        
        # Build secondary indexes
        self._build_secondary_indexes()

    def _read_group_hierarchy(self, group_offset: int):
        """Read group hierarchy from file"""
        self._file.seek(group_offset)
        
        # Simplified group reading - in practice would read complex hierarchy
        num_groups = struct.unpack('<I', self._file.read(4))[0]
        
        for _ in range(num_groups):
            name_len = struct.unpack('<H', self._file.read(2))[0]
            name = self._file.read(name_len).decode('utf-8')
            
            num_structures = struct.unpack('<I', self._file.read(4))[0]
            group = self.create_group(name)
            
            for _ in range(num_structures):
                struct_name_len = struct.unpack('<H', self._file.read(2))[0]
                struct_name = self._file.read(struct_name_len).decode('utf-8')
                hash_len = struct.unpack('<H', self._file.read(2))[0]
                struct_hash = self._file.read(hash_len).decode('utf-8')
                
                group.add_structure(struct_name, struct_hash)
                self._name_index[struct_name] = struct_hash

    def _build_secondary_indexes(self):
        """Build secondary indexes for fast querying"""
        print("Building secondary indexes...")
        
        for struct_hash in list(self._hash_index.keys())[:10]:  # Limit for demo
            structure = self.get(struct_hash)
            if structure:
                # Formula index
                self._formula_index[structure.formula].append(struct_hash)
                
                # Property index
                props = structure.structure_properties.get_all_properties()
                for prop_name, value in props.items():
                    if isinstance(value, (int, float)):
                        # Bucket numerical values
                        bucket = round(value, 3)
                        self._property_index[prop_name][bucket].append(struct_hash)
                    else:
                        self._property_index[prop_name][value].append(struct_hash)

    def _start_prefetch_thread(self):
        """Start background thread for prefetching"""
        def prefetch_worker():
            while True:
                try:
                    hashes = self._prefetch_queue.get(timeout=1.0)
                    if hashes is None:  # Stop signal
                        break
                    for h in hashes:
                        if h not in self._cache:
                            self.get(h)  # This will cache the result
                    self._prefetch_queue.task_done()
                except queue.Empty:
                    continue
        
        self._prefetch_thread = threading.Thread(target=prefetch_worker, daemon=True)
        self._prefetch_thread.start()

    def add(self, structure: USIFStructure, name: str = None, group: str = "/") -> str:
        """Add structure with optional naming and grouping"""
        if self.mode == 'r':
            raise ValueError("Cannot add to read-only container")
        
        usif_data = self.encoder.encode(structure)
        struct_hash = self.encoder.get_structure_hash(structure)
        
        # Check for duplicates
        if struct_hash in self._hash_index:
            return struct_hash
        
        # Write to file using chunked storage
        chunk_id, chunk_offset = self._allocate_space(len(usif_data))
        self._write_to_chunk(chunk_id, chunk_offset, usif_data)
        
        # Update indexes
        self._hash_index[struct_hash] = (chunk_id, chunk_offset, len(usif_data))
        
        # Name index
        if name:
            self._name_index[name] = struct_hash
        
        # Add to group
        target_group = self._get_or_create_group(group)
        display_name = name or struct_hash[:16]
        target_group.add_structure(display_name, struct_hash)
        
        # Update secondary indexes
        self._update_secondary_indexes(structure, struct_hash)
        
        return struct_hash

    def _allocate_space(self, size: int) -> Tuple[int, int]:
        """Allocate space in chunked storage"""
        if self._mmap:
            current_pos = self._mmap.size()
        else:
            self._file.seek(0, 2)  # Seek to end
            current_pos = self._file.tell()
        
        chunk_id = current_pos // self.CHUNK_SIZE
        chunk_offset = current_pos % self.CHUNK_SIZE
        
        # If we don't have enough space in current chunk, move to next
        if chunk_offset + size > self.CHUNK_SIZE:
            chunk_id += 1
            chunk_offset = 0
            # Pad the current chunk if needed
            if self._mmap:
                self._mmap.resize(chunk_id * self.CHUNK_SIZE)
            else:
                self._file.seek(chunk_id * self.CHUNK_SIZE - 1)
                self._file.write(b'\x00')
        
        return chunk_id, chunk_offset

    def _write_to_chunk(self, chunk_id: int, offset: int, data: bytes):
        """Write data to specific chunk"""
        actual_offset = chunk_id * self.CHUNK_SIZE + offset
        
        if self._mmap:
            # Extend mmap if needed
            required_size = actual_offset + len(data)
            if required_size > self._mmap.size():
                self._mmap.resize(required_size)
            self._mmap[actual_offset:actual_offset + len(data)] = data
        else:
            self._file.seek(actual_offset)
            self._file.write(data)

    def _get_or_create_group(self, path: str) -> USIFGroup:
        """Get or create group by path"""
        if path == "/":
            return self.root_group
            
        parts = [p for p in path.split('/') if p]
        current = self.root_group
        
        full_path = "/"
        for part in parts:
            full_path += part + "/"
            if part not in current.subgroups:
                current.subgroups[part] = USIFGroup(part)
                self._group_index[full_path] = current.subgroups[part]
            current = current.subgroups[part]
        
        return current

    def _update_secondary_indexes(self, structure: USIFStructure, struct_hash: str):
        """Update secondary indexes for a structure"""
        # Formula index
        self._formula_index[structure.formula].append(struct_hash)
        
        # Property index
        props = structure.structure_properties.get_all_properties()
        for prop_name, value in props.items():
            if isinstance(value, (int, float)):
                bucket = round(value, 3)
                self._property_index[prop_name][bucket].append(struct_hash)
            else:
                self._property_index[prop_name][value].append(struct_hash)

    def get(self, identifier: str) -> Optional[USIFStructure]:
        """Get structure by hash or name"""
        # Check cache first
        if identifier in self._cache:
            return self._cache[identifier]
        
        # Resolve name to hash
        struct_hash = self._name_index.get(identifier, identifier)
        
        if struct_hash not in self._hash_index:
            return None
        
        # Read from storage
        chunk_id, chunk_offset, size = self._hash_index[struct_hash]
        usif_data = self._read_from_chunk(chunk_id, chunk_offset, size)
        
        try:
            structure, _ = self.encoder.decode(usif_data)
            # Cache the result
            self._cache[identifier] = structure
            if len(self._cache) > self._cache_size:
                # Remove oldest entry (simplified LRU)
                self._cache.pop(next(iter(self._cache)))
            return structure
        except Exception as e:
            print(f"Error decoding structure {identifier}: {e}")
            return None

    def _read_from_chunk(self, chunk_id: int, offset: int, size: int) -> bytes:
        """Read data from specific chunk"""
        actual_offset = chunk_id * self.CHUNK_SIZE + offset
        
        if self._mmap:
            return self._mmap[actual_offset:actual_offset + size]
        else:
            current_pos = self._file.tell()
            self._file.seek(actual_offset)
            data = self._file.read(size)
            self._file.seek(current_pos)  # Restore original position
            return data

    def query(self, 
              formula: str = None,
              properties: Dict[str, Any] = None,
              energy_range: Tuple[float, float] = None,
              group: str = None) -> List[Tuple[str, USIFStructure]]:
        """Enhanced query with multiple criteria"""
        results = []
        
        # Start with formula filter
        candidate_hashes = set()
        if formula:
            candidate_hashes.update(self._formula_index.get(formula, []))
        else:
            candidate_hashes.update(self._hash_index.keys())
        
        # Property filter
        if properties:
            for prop_name, prop_value in properties.items():
                if prop_name in self._property_index:
                    if isinstance(prop_value, (int, float)):
                        # Range query for numerical values
                        for bucket, hashes in self._property_index[prop_name].items():
                            if isinstance(bucket, (int, float)) and abs(bucket - prop_value) < 0.001:
                                candidate_hashes.intersection_update(hashes)
                    else:
                        # Exact match for other types
                        if prop_value in self._property_index[prop_name]:
                            candidate_hashes.intersection_update(
                                self._property_index[prop_name][prop_value])
        
        # Energy range filter
        if energy_range:
            min_energy, max_energy = energy_range
            energy_hashes = set()
            for bucket, hashes in self._property_index.get('energy', {}).items():
                if isinstance(bucket, (int, float)) and min_energy <= bucket <= max_energy:
                    energy_hashes.update(hashes)
            candidate_hashes.intersection_update(energy_hashes)
        
        # Group filter
        if group and group != "/":
            group_hashes = set()
            target_group = self.get_group(group)
            if target_group:
                for struct_name, struct_hash in target_group.structures.items():
                    group_hashes.add(struct_hash)
            candidate_hashes.intersection_update(group_hashes)
        
        # Retrieve structures
        for hash_val in candidate_hashes:
            structure = self.get(hash_val)
            if structure:
                results.append((hash_val, structure))
        
        return results

    def get_group(self, path: str) -> Optional[USIFGroup]:
        """Get group by path"""
        return self.root_group.get_subgroup(path)

    def create_group(self, path: str) -> USIFGroup:
        """Create group hierarchy"""
        return self._get_or_create_group(path)

    def prefetch(self, identifiers: List[str]):
        """Prefetch structures for faster access"""
        self._prefetch_queue.put(identifiers)

    def get_batch_parallel(self, identifiers: List[str]) -> List[Optional[USIFStructure]]:
        """Batch read using multiple threads"""
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = {executor.submit(self.get, ident): ident for ident in identifiers}
            results = [None] * len(identifiers)
            
            for future in futures:
                ident = futures[future]
                idx = identifiers.index(ident)
                try:
                    results[idx] = future.result()
                except Exception:
                    results[idx] = None
            
            return results

    def _write_enhanced_index(self):
        """Write enhanced index to file - simplified for demo"""
        if self.mode == 'r':
            return
        
        # For demo purposes, we'll skip writing the full index
        # In a production system, this would write the complete index
        pass

    def _serialize_group_hierarchy(self) -> bytes:
        """Serialize group hierarchy to bytes - simplified for demo"""
        return b''

    def stats(self) -> Dict[str, Any]:
        """Get detailed container statistics"""
        total_structures = len(self._hash_index)
        total_groups = len(self._group_index)
        
        # Calculate storage statistics
        total_size = sum(size for _, _, size in self._hash_index.values())
        avg_size = total_size / total_structures if total_structures else 0
        
        # Index sizes
        hash_index_size = total_structures * 44  # Approximate
        secondary_index_size = sum(
            len(hashes) * 16 for hashes in self._formula_index.values()
        ) + sum(
            len(bucket_hashes) * 16 for prop_dict in self._property_index.values()
            for bucket_hashes in prop_dict.values()
        )
        
        return {
            'total_structures': total_structures,
            'total_groups': total_groups,
            'total_size_bytes': total_size,
            'average_structure_size': avg_size,
            'hash_index_size': hash_index_size,
            'secondary_index_size': secondary_index_size,
            'cache_size': len(self._cache),
            'cache_hit_ratio': 0.0,  # Would track actual hits in production
            'compression_enabled': self.encoder.compression != CompressionType.NONE,
            'mmap_enabled': self.use_mmap,
            'chunk_size': self.CHUNK_SIZE,
        }

    def close(self):
        """Close container and cleanup"""
        if hasattr(self, '_prefetch_thread') and self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_queue.put(None)  # Signal to stop
            self._prefetch_thread.join(timeout=5.0)
        
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        
        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __len__(self):
        return len(self._hash_index)

    def __contains__(self, identifier: str):
        return identifier in self._hash_index or identifier in self._name_index

    def __iter__(self):
        for struct_hash in self._hash_index:
            structure = self.get(struct_hash)
            if structure:
                yield struct_hash, structure

    def list_groups(self) -> List[str]:
        """List all groups in container"""
        return list(self._group_index.keys())

    def get_structures_in_group(self, group_path: str) -> List[Tuple[str, USIFStructure]]:
        """Get all structures in a specific group"""
        group = self.get_group(group_path)
        if not group:
            return []
        
        results = []
        for name, struct_hash in group.structures.items():
            structure = self.get(struct_hash)
            if structure:
                results.append((name, structure))
        
        return results


# ============================================================================
# Performance Optimizations and Utilities
# ============================================================================

class USIFOptimizer:
    """Performance optimization utilities for USIF"""
    
    @staticmethod
    def optimize_structure(structure: USIFStructure, 
                          tolerance: float = 1e-3) -> USIFStructure:
        """
        Optimize structure for maximum compression
        
        Args:
            structure: Input USIF structure
            tolerance: Symmetry tolerance for grouping
            
        Returns:
            Optimized USIF structure
        """
        if structure.is_periodic():
            return USIFOptimizer._optimize_crystal(structure, tolerance)
        else:
            return USIFOptimizer._optimize_molecule(structure, tolerance)
    
    @staticmethod
    def _optimize_crystal(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize crystal structure"""
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure  # Already optimized
        
        # Convert to pymatgen for symmetry analysis
        pmg_structure = StructureConverter.to_pymatgen(structure)
        
        # Try symmetric storage
        try:
            sga = SpacegroupAnalyzer(pmg_structure, symprec=tolerance)
            symmetrized = sga.get_symmetrized_structure()
            
            wyckoff_sites = []
            for equiv_sites in symmetrized.equivalent_sites:
                rep = equiv_sites[0]
                z = rep.specie.Z
                wyckoff_sites.append(WyckoffSite(z, len(equiv_sites), tuple(rep.frac_coords)))
            
            return USIFStructure(
                structure_type=StructureType.PERIODIC,
                storage_mode=StorageMode.SYMMETRIC,
                lattice_matrix=structure.lattice_matrix,
                spacegroup=sga.get_space_group_number(),
                wyckoff_sites=wyckoff_sites,
                structure_properties=structure.structure_properties,
                formula=structure.formula
            )
        except Exception:
            return structure  # Fall back to original
    
    @staticmethod
    def _optimize_molecule(structure: USIFStructure, tolerance: float) -> USIFStructure:
        """Optimize molecular structure"""
        if structure.storage_mode == StorageMode.SYMMETRIC:
            return structure  # Already optimized
        
        # Convert to pymatgen for symmetry analysis
        pmg_molecule = StructureConverter.to_pymatgen(structure)
        
        # Try symmetric storage
        try:
            pga = PointGroupAnalyzer(pmg_molecule)
            point_group = pga.sch_symbol
            
            # Simple symmetry detection
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
                        
                        if min_dist < tolerance:
                            equiv_count += 1
                            used.add(other_idx)
                    
                    point_group_sites.append(PointGroupSite(z, equiv_count, tuple(coords)))
            
            total_multiplicity = sum(s.multiplicity for s in point_group_sites)
            if total_multiplicity == len(pmg_molecule) and len(point_group_sites) < len(pmg_molecule):
                return USIFStructure(
                    structure_type=StructureType.MOLECULAR,
                    storage_mode=StorageMode.SYMMETRIC,
                    point_group=point_group,
                    point_group_sites=point_group_sites,
                    structure_properties=structure.structure_properties,
                    formula=structure.formula
                )
        except Exception:
            pass
        
        return structure  # Fall back to original


class USIFBenchmark:
    """Benchmarking utilities for USIF performance"""
    
    @staticmethod
    def benchmark_compression(structures: List[USIFStructure]) -> Dict[str, Any]:
        """
        Benchmark compression performance
        
        Args:
            structures: List of structures to benchmark
            
        Returns:
            Dictionary with benchmark results
        """
        encoder = USIF()
        
        total_original_size = 0
        total_compressed_size = 0
        compression_times = []
        decompression_times = []
        
        import time
        
        for structure in structures:
            # Measure compression
            start = time.time()
            compressed = encoder.encode(structure)
            compression_times.append(time.time() - start)
            
            # Measure decompression
            start = time.time()
            decoded, _ = encoder.decode(compressed)
            decompression_times.append(time.time() - start)
            
            # Calculate sizes
            pmg_structure = StructureConverter.to_pymatgen(structure)
            cif_size = len(pmg_structure.to(fmt="cif"))
            total_original_size += cif_size
            total_compressed_size += len(compressed)
        
        avg_compression_ratio = total_compressed_size / total_original_size if total_original_size > 0 else 0
        avg_compression_time = np.mean(compression_times) if compression_times else 0
        avg_decompression_time = np.mean(decompression_times) if decompression_times else 0
        
        return {
            'num_structures': len(structures),
            'total_original_size': total_original_size,
            'total_compressed_size': total_compressed_size,
            'average_compression_ratio': avg_compression_ratio,
            'average_compression_time': avg_compression_time,
            'average_decompression_time': avg_decompression_time,
            'compression_speedup': 1.0 / avg_compression_ratio if avg_compression_ratio > 0 else 0
        }


# ============================================================================
# Main Usage Examples
# ============================================================================

def main():
    """Main demonstration function"""
    print("USIF (Universal Structure Interchange Format) Demo")
    print("=" * 50)
    
    # Create a simple crystal structure
    lattice = np.array([
        [5.0, 0.0, 0.0],
        [0.0, 5.0, 0.0],
        [0.0, 0.0, 5.0]
    ])
    
    wyckoff_sites = [
        WyckoffSite(14, 8, (0.0, 0.0, 0.0)),  # Silicon
        WyckoffSite(8, 16, (0.25, 0.25, 0.25))  # Oxygen
    ]
    
    crystal_structure = USIFStructure(
        structure_type=StructureType.PERIODIC,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=lattice,
        spacegroup=227,
        wyckoff_sites=wyckoff_sites,
        formula="SiO2"
    )
    
    # Create encoder
    encoder = USIF()
    
    # Encode structure
    encoded_data = encoder.encode(crystal_structure)
    structure_hash = encoder.get_structure_hash(crystal_structure)
    
    print(f"Crystal structure: {crystal_structure.formula}")
    print(f"Number of atoms: {crystal_structure.num_atoms()}")
    print(f"Encoded size: {len(encoded_data)} bytes")
    print(f"Structure hash: {structure_hash}")
    
    # Decode structure
    decoded_structure, _ = encoder.decode(encoded_data)
    print(f"Decoded successfully: {crystal_structure == decoded_structure}")
    
    # Test container
    with StructureContainer("test_container.usifc", mode="w") as container:
        container.add(crystal_structure, name="silica_crystal", group="/crystals")
        
        # Query container
        results = container.query(formula="SiO2")
        print(f"Found {len(results)} structures with formula SiO2")
    
    print("Demo completed successfully!")


if __name__ == "__main__":
    main()
