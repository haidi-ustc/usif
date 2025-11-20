#!/usr/bin/env python3
"""
USIF Properties Module

This module provides a type-safe property system for attaching properties to
atomic structures. Properties can be atomic (per-atom) or structure-level.

Main Classes:
    PropertyDefinition: Define property types with validation
    PropertySerializer: Serialize/deserialize property values
    PropertyRegistry: Registry of built-in property definitions
    AtomicProperties: Properties attached to individual atoms
    StructureProperties: Properties attached to entire structures

Property Types:
    - Atomic properties: force, charge, magmom, velocity (per-atom)
    - Structure properties: energy, stress, volume, pressure, temperature

Usage:
    >>> from usif import PropertyDefinition, PropertyRegistry, AtomicProperties
    >>>
    >>> # Use built-in properties
    >>> force_def = PropertyRegistry.get('force')
    >>>
    >>> # Create custom property
    >>> custom_prop = PropertyDefinition(
    ...     name='band_gap',
    ...     data_type=float,
    ...     description='Electronic band gap',
    ...     units='eV'
    ... )
    >>> PropertyRegistry.register(custom_prop)
    >>>
    >>> # Use atomic properties
    >>> atom_props = AtomicProperties(
    ...     force=(0.1, 0.2, 0.3),
    ...     charge=0.5
    ... )
    >>>
    >>> # Use structure properties
    >>> from usif import StructureProperties
    >>> struct_props = StructureProperties(
    ...     energy=-10.5,
    ...     volume=179.4
    ... )

See Also:
    - Units: Physical unit constants
    - PropertySerializer: Serialization details
"""

from .atomic import AtomicProperties
from .definitions import PropertyDefinition
from .registry import PropertyRegistry
from .serializer import PropertySerializer
from .structure import StructureProperties

__all__ = [
    'PropertyDefinition',
    'PropertySerializer',
    'PropertyRegistry',
    'AtomicProperties',
    'StructureProperties',
]
