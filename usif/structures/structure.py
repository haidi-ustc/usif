#!/usr/bin/env python3
"""Pure USIF structure domain model."""

from typing import Any, Iterable, List, Optional

import numpy as np
from usif.constants import StorageMode, StructureType, SymmetryConstants
from usif.exceptions import ValidationError
from usif.properties.atomic import AtomicProperties
from usif.properties.structure import StructureProperties
from usif.structures.metadata import SYMMETRY_METADATA_KEY, SymmetryMetadata
from usif.structures.sites import AtomSite, PointGroupSite, WyckoffSite


class USIFStructure:
    """Structure data, validation, metadata, and dictionary serialization only."""

    __slots__ = [
        "structure_type",
        "storage_mode",
        "lattice_matrix",
        "spacegroup",
        "point_group",
        "wyckoff_sites",
        "point_group_sites",
        "atom_sites",
        "structure_properties",
        "formula",
    ]

    def __init__(
        self,
        structure_type: StructureType = StructureType.CRYSTAL,
        storage_mode: StorageMode = StorageMode.SYMMETRIC,
        lattice_matrix: Optional[np.ndarray] = None,
        spacegroup: int = 1,
        point_group: Optional[str] = None,
        wyckoff_sites: Optional[List[WyckoffSite]] = None,
        point_group_sites: Optional[List[PointGroupSite]] = None,
        atom_sites: Optional[List[AtomSite]] = None,
        structure_properties: Optional[StructureProperties] = None,
        formula: str = "",
    ):
        self.structure_type = structure_type
        self.storage_mode = storage_mode
        self.lattice_matrix = lattice_matrix
        self.spacegroup = spacegroup
        self.point_group = point_group
        self.wyckoff_sites = wyckoff_sites
        self.point_group_sites = point_group_sites
        self.atom_sites = atom_sites
        self.structure_properties = structure_properties or StructureProperties()
        self.formula = formula
        self._validate_structure()

    def _validate_structure(self) -> None:
        """Validate structure type/storage mode consistency."""
        if self.structure_type == StructureType.MOLECULE:
            if self.lattice_matrix is not None:
                raise ValidationError("Molecular structures should not have lattice")
            if self.storage_mode == StorageMode.SYMMETRIC and not self.point_group_sites:
                raise ValidationError(
                    "Molecular SYMMETRIC mode requires non-empty point_group_sites"
                )
            if self.storage_mode == StorageMode.FULL_ATOMIC and not self.atom_sites:
                raise ValidationError(
                    "Molecular FULL_ATOMIC mode requires non-empty atom_sites"
                )
            return

        if self.lattice_matrix is None:
            raise ValidationError("Crystal structures require lattice")
        if self.storage_mode == StorageMode.SYMMETRIC and not self.wyckoff_sites:
            raise ValidationError("Crystal SYMMETRIC mode requires non-empty wyckoff_sites")
        if self.storage_mode == StorageMode.FULL_ATOMIC and not self.atom_sites:
            raise ValidationError("Crystal FULL_ATOMIC mode requires non-empty atom_sites")

    def is_crystal(self) -> bool:
        return self.structure_type == StructureType.CRYSTAL

    def is_molecular(self) -> bool:
        return self.structure_type == StructureType.MOLECULE

    def is_symmetric(self) -> bool:
        return self.storage_mode == StorageMode.SYMMETRIC


    def get_structure_property(self, name: str, default: Any = None) -> Any:
        """Return a structure-level property by name."""
        return self.structure_properties.get(name, default)

    def set_structure_property(self, name: str, value: Any, *, units: str | None = None) -> "USIFStructure":
        """Set a structure-level property and return ``self`` for chaining."""
        self.structure_properties.set(name, value, units=units)
        return self

    def remove_structure_property(self, name: str) -> Any:
        """Remove a structure-level property and return its previous value."""
        return self.structure_properties.remove(name)

    def get_atom_property(self, index: int, name: str, default: Any = None) -> Any:
        """Return one atom-level property by atom index. Requires full-atomic storage."""
        sites = self._require_atom_sites()
        return sites[index].properties.get(name, default)

    def set_atom_property(self, index: int, name: str, value: Any, *, units: str | None = None) -> "USIFStructure":
        """Set one atom-level property by atom index. Requires full-atomic storage."""
        sites = self._require_atom_sites()
        sites[index].properties.set(name, value, units=units)
        return self

    def get_atomic_property(self, name: str, default: Any = None) -> list[Any]:
        """Return an atom-aligned list for one property across all atom sites."""
        return [site.properties.get(name, default) for site in self._require_atom_sites()]

    def set_atomic_property(self, name: str, values: Iterable[Any], *, units: str | None = None) -> "USIFStructure":
        """Set one property across all atom sites from an atom-aligned iterable."""
        sites = self._require_atom_sites()
        values_list = list(values)
        if len(values_list) != len(sites):
            raise ValueError(
                f"Atomic property '{name}' expects {len(sites)} values, got {len(values_list)}"
            )
        for site, value in zip(sites, values_list):
            site.properties.set(name, value, units=units)
        return self

    def _require_atom_sites(self) -> list[AtomSite]:
        if self.storage_mode != StorageMode.FULL_ATOMIC or self.atom_sites is None:
            raise ValidationError("Atomic property management requires FULL_ATOMIC storage")
        return self.atom_sites

    def set_symmetry_metadata(self, metadata: SymmetryMetadata) -> None:
        self.structure_properties.custom[SYMMETRY_METADATA_KEY] = metadata.as_dict()

    def get_symmetry_metadata(self) -> Optional[SymmetryMetadata]:
        data = self.structure_properties.custom.get(SYMMETRY_METADATA_KEY)
        if isinstance(data, SymmetryMetadata):
            return data
        if isinstance(data, dict):
            return SymmetryMetadata.from_dict(data)
        return None

    def num_atoms(self) -> int:
        if self.storage_mode == StorageMode.FULL_ATOMIC:
            return len(self.atom_sites or [])
        if self.is_crystal():
            return sum(site.multiplicity for site in self.wyckoff_sites or [])
        return sum(site.multiplicity for site in self.point_group_sites or [])

    def as_dict(self) -> dict:
        data = {
            "@module": self.__class__.__module__,
            "@class": self.__class__.__name__,
            "structure_type": self.structure_type.value,
            "storage_mode": self.storage_mode.value,
            "structure_properties": _structure_properties_to_dict(self.structure_properties),
            "formula": self.formula,
        }
        if self.is_crystal():
            if self.lattice_matrix is not None:
                data["lattice_matrix"] = self.lattice_matrix.tolist()
            data["spacegroup"] = self.spacegroup
            if self.wyckoff_sites is not None:
                data["wyckoff_sites"] = [
                    _symmetric_site_to_dict(site) for site in self.wyckoff_sites
                ]
        else:
            if self.point_group is not None:
                data["point_group"] = self.point_group
            if self.point_group_sites is not None:
                data["point_group_sites"] = [
                    _symmetric_site_to_dict(site) for site in self.point_group_sites
                ]
        if self.atom_sites is not None:
            data["atom_sites"] = [_atom_site_to_dict(site) for site in self.atom_sites]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "USIFStructure":
        structure_type = StructureType(data["structure_type"])
        is_crystal = structure_type == StructureType.CRYSTAL
        lattice_matrix = (
            np.array(data["lattice_matrix"]) if data.get("lattice_matrix") else None
        )
        wyckoff_sites = (
            [
                WyckoffSite(**_site_coords_as_tuple(site))
                for site in data.get("wyckoff_sites", [])
            ]
            if is_crystal and data.get("wyckoff_sites") is not None
            else None
        )
        point_group_sites = (
            [
                PointGroupSite(**_site_coords_as_tuple(site))
                for site in data.get("point_group_sites", [])
            ]
            if not is_crystal and data.get("point_group_sites") is not None
            else None
        )
        atom_sites = (
            [_atom_site_from_dict(site) for site in data.get("atom_sites", [])]
            if data.get("atom_sites") is not None
            else None
        )
        structure_properties = data.get("structure_properties")
        if isinstance(structure_properties, dict):
            structure_properties = StructureProperties.from_dict(structure_properties)
        return cls(
            structure_type=structure_type,
            storage_mode=StorageMode(data["storage_mode"]),
            lattice_matrix=lattice_matrix,
            spacegroup=data.get("spacegroup", 1),
            point_group=data.get("point_group"),
            wyckoff_sites=wyckoff_sites,
            point_group_sites=point_group_sites,
            atom_sites=atom_sites,
            structure_properties=structure_properties,
            formula=data["formula"],
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, USIFStructure):
            return False
        if self.lattice_matrix is None or other.lattice_matrix is None:
            lattice_equal = self.lattice_matrix is other.lattice_matrix
        else:
            lattice_equal = np.allclose(
                self.lattice_matrix,
                other.lattice_matrix,
                atol=SymmetryConstants.COORDINATE_TOLERANCE,
            )
        return (
            self.structure_type == other.structure_type
            and self.storage_mode == other.storage_mode
            and lattice_equal
            and self.spacegroup == other.spacegroup
            and self.point_group == other.point_group
            and self.wyckoff_sites == other.wyckoff_sites
            and self.point_group_sites == other.point_group_sites
            and self.atom_sites == other.atom_sites
            and self.structure_properties == other.structure_properties
            and self.formula == other.formula
        )

    def __repr__(self) -> str:
        parts = [
            f"structure_type={self.structure_type.name}",
            f"storage_mode={self.storage_mode.name}",
            f"formula='{self.formula}'",
            f"atoms={self.num_atoms()}",
        ]
        if self.is_crystal():
            parts.append(f"spacegroup={self.spacegroup}")
            if self.lattice_matrix is not None:
                lengths = np.linalg.norm(self.lattice_matrix, axis=1)
                parts.append(
                    f"lattice=({lengths[0]:.3f}, {lengths[1]:.3f}, {lengths[2]:.3f})"
                )
        elif self.point_group:
            parts.append(f"point_group='{self.point_group}'")
        if self.structure_properties.energy is not None:
            parts.append(f"energy={self.structure_properties.energy:.6f}")
        return f"USIFStructure({', '.join(parts)})"

    def __str__(self) -> str:
        lines = [
            f"{'Crystal' if self.is_crystal() else 'Molecule'}: {self.formula or 'Unknown'}",
            f"  Atoms: {self.num_atoms()}",
            f"  Storage: {self.storage_mode.name}",
        ]
        if self.is_crystal():
            if self.lattice_matrix is not None:
                lengths = np.linalg.norm(self.lattice_matrix, axis=1)
                angles = _lattice_angles(self.lattice_matrix, lengths)
                lines.append(
                    f"  Lattice: a={lengths[0]:.3f} Å, b={lengths[1]:.3f} Å, c={lengths[2]:.3f} Å"
                )
                lines.append(
                    f"  Angles: α={angles[0]:.1f}°, β={angles[1]:.1f}°, γ={angles[2]:.1f}°"
                )
            lines.append(f"  Spacegroup: {self.spacegroup}")
            if self.is_symmetric() and self.wyckoff_sites:
                lines.append(f"  Wyckoff sites: {len(self.wyckoff_sites)}")
        else:
            if self.point_group:
                lines.append(f"  Point group: {self.point_group}")
            if self.is_symmetric() and self.point_group_sites:
                lines.append(f"  Symmetry sites: {len(self.point_group_sites)}")
        props = _format_properties(self.structure_properties)
        if props:
            lines.append(f"  Properties: {props}")
        return "\n".join(lines)


def _structure_properties_to_dict(properties: StructureProperties) -> dict:
    return {
        "energy": properties.energy,
        "stress": properties.stress,
        "volume": properties.volume,
        "pressure": properties.pressure,
        "temperature": properties.temperature,
        "custom": properties.custom,
        "units": properties.units,
    }


def _site_coords_as_tuple(site: dict) -> dict:
    copied = dict(site)
    if "coords" in copied:
        copied["coords"] = tuple(copied["coords"])
    return copied


def _symmetric_site_to_dict(site: WyckoffSite | PointGroupSite) -> dict:
    return {
        "atomic_number": site.atomic_number,
        "multiplicity": site.multiplicity,
        "coords": site.coords,
        "occupancy": site.occupancy,
    }


def _atom_site_to_dict(site: AtomSite) -> dict:
    return {
        "atomic_number": site.atomic_number,
        "coords": site.coords,
        "properties": {
            "force": site.properties.force,
            "charge": site.properties.charge,
            "magmom": site.properties.magmom,
            "velocity": site.properties.velocity,
            "custom": site.properties.custom,
            "units": site.properties.units,
        },
    }


def _atom_site_from_dict(data: dict) -> AtomSite:
    props = data.get("properties", {})
    return AtomSite(
        atomic_number=data["atomic_number"],
        coords=tuple(data["coords"]),
        properties=AtomicProperties(
            force=tuple(props["force"]) if props.get("force") is not None else None,
            charge=props.get("charge"),
            magmom=props.get("magmom"),
            velocity=(
                tuple(props["velocity"]) if props.get("velocity") is not None else None
            ),
            custom=props.get("custom", {}),
            units=props.get("units", {}),
        ),
    )


def _lattice_angles(lattice_matrix: np.ndarray, lengths: np.ndarray) -> list[float]:
    angles = []
    for i in range(3):
        j, k = (i + 1) % 3, (i + 2) % 3
        v1 = lattice_matrix[j] / lengths[j]
        v2 = lattice_matrix[k] / lengths[k]
        angle = np.degrees(np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0)))
        angles.append(float(angle))
    return angles


def _format_properties(properties: StructureProperties) -> str:
    from usif.units import Units

    parts = []
    if properties.energy is not None:
        parts.append(f"E={properties.energy:.6f} {properties.get_units('energy', Units.EV)}")
    if properties.volume is not None:
        parts.append(f"V={properties.volume:.3f} {properties.get_units('volume', Units.ANGSTROM_CUBED)}")
    if properties.pressure is not None:
        parts.append(f"P={properties.pressure:.3f} {properties.get_units('pressure', Units.GPA)}")
    return ", ".join(parts)
