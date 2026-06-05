"""Tests for isolated property registries used by codecs."""

import numpy as np

from usif import (
    USIF,
    CompressionType,
    PropertyDefinition,
    DEFAULT_REGISTRY,
    create_default_registry,
    StorageMode,
    StructureProperties,
    StructureType,
    USIFStructure,
    WyckoffSite,
)


def test_create_isolated_registry_does_not_pollute_global_registry():
    registry = create_default_registry()
    registry.register(PropertyDefinition("isolated_scalar", float))

    assert registry.exists("isolated_scalar")
    assert not DEFAULT_REGISTRY.exists("isolated_scalar")


def test_encoder_uses_injected_registry_for_builtin_style_property():
    registry = create_default_registry()
    registry.register(PropertyDefinition("isolated_energy", float))

    props = StructureProperties()
    props.custom["isolated_energy"] = -1.25
    structure = USIFStructure(
        structure_type=StructureType.CRYSTAL,
        storage_mode=StorageMode.SYMMETRIC,
        lattice_matrix=np.eye(3),
        spacegroup=1,
        wyckoff_sites=[WyckoffSite(1, 1, (0.0, 0.0, 0.0))],
        structure_properties=props,
        formula="H",
    )

    encoder = USIF(compression=CompressionType.NONE, property_registry=registry)
    decoded, _ = encoder.decode(encoder.encode(structure))

    assert decoded.structure_properties.custom["isolated_energy"] == -1.25
