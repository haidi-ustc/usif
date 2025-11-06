#!/usr/bin/env python3
"""
USIF Properties Module
Property system for atomic and structure properties
"""

from .definitions import PropertyDefinition
from .serializer import PropertySerializer
from .registry import PropertyRegistry
from .atomic import AtomicProperties
from .structure import StructureProperties

__all__ = [
    'PropertyDefinition',
    'PropertySerializer',
    'PropertyRegistry',
    'AtomicProperties',
    'StructureProperties',
]

