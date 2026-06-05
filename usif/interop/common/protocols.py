"""Structural protocols used at the interop boundary.

The adapters still validate concrete optional dependency types at runtime, but
these protocols document the small surface USIF actually consumes.  Keeping the
contract here prevents pymatgen/ASE details from leaking into services and tests.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Protocol, Sequence, TypeAlias, runtime_checkable

import numpy as np

NumericArray: TypeAlias = np.ndarray | Sequence[float] | Sequence[Sequence[float]]


@runtime_checkable
class PymatgenSiteLike(Protocol):
    """Minimum site surface consumed by pymatgen importers."""

    specie: Any
    coords: Any
    frac_coords: Any


@runtime_checkable
class PymatgenStructureLike(Protocol):
    """Minimum pymatgen ``Structure`` surface consumed by USIF."""

    lattice: Any
    sites: Sequence[PymatgenSiteLike]
    composition: Any
    volume: float
    site_properties: Mapping[str, Sequence[Any]]

    def __iter__(self) -> Iterable[PymatgenSiteLike]: ...

    def __len__(self) -> int: ...


@runtime_checkable
class PymatgenMoleculeLike(Protocol):
    """Minimum pymatgen ``Molecule`` surface consumed by USIF."""

    sites: Sequence[PymatgenSiteLike]
    composition: Any
    site_properties: Mapping[str, Sequence[Any]]

    def __iter__(self) -> Iterable[PymatgenSiteLike]: ...

    def __len__(self) -> int: ...


@runtime_checkable
class ASEAtomsLike(Protocol):
    """Minimum ASE ``Atoms`` surface consumed by USIF."""

    cell: Any
    info: dict[str, Any]
    calc: Any

    def __len__(self) -> int: ...

    def get_forces(self) -> Any: ...

    def get_stress(self, voigt: bool = ...) -> Any: ...

    def get_potential_energy(self) -> float: ...

    def get_charges(self) -> Any: ...

    def get_magnetic_moments(self) -> Any: ...


PymatgenObject: TypeAlias = PymatgenStructureLike | PymatgenMoleculeLike


__all__ = [
    "ASEAtomsLike",
    "NumericArray",
    "PymatgenMoleculeLike",
    "PymatgenObject",
    "PymatgenSiteLike",
    "PymatgenStructureLike",
]
