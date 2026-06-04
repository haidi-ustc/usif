"""
USIF Property System

This package provides property definitions, registries, serialization, and
containers for atomic and structure-level properties.
"""

from .atomic import AtomicProperties
from .definitions import PropertyDefinition
from .registry import (
    PropertyRegistry,
    PropertyRegistryInstance,
    default_registry,
    isolated_registry,
)
from .serializer import PropertySerializer
from .structure import StructureProperties

__all__ = [
    "PropertyDefinition",
    "PropertySerializer",
    "PropertyRegistry",
    "PropertyRegistryInstance",
    "default_registry",
    "isolated_registry",
    "AtomicProperties",
    "StructureProperties",
]
