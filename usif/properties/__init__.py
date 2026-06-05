"""USIF property system."""

from .atomic import AtomicProperties
from .definitions import PropertyDefinition
from .registry import DEFAULT_REGISTRY, PropertyRegistry, create_default_registry
from .serializer import PropertySerializer
from .structure import StructureProperties
from .values import PropertyValueKind, normalize_json_value

__all__ = [
    "PropertyDefinition",
    "PropertySerializer",
    "PropertyRegistry",
    "DEFAULT_REGISTRY",
    "create_default_registry",
    "AtomicProperties",
    "StructureProperties",
    "PropertyValueKind",
    "normalize_json_value",
]
