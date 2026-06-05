"""Symmetry conversion policy objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from usif.constants import SymmetryConstants
from usif.exceptions import ValidationError

SymmetryMode = Literal["none", "analyze", "reduce", "preserve"]


@dataclass(frozen=True)
class SymmetryPolicy:
    """Policy controlling whether imports attempt symmetric representations.

    Modes:
        none: Always keep full atomic coordinates.
        analyze: Use a symmetric representation only when it is lossless and no
            per-atom properties would be lost.
        reduce: Prefer a symmetric representation. Per-atom properties must be
            explicitly dropped or preserved by falling back to full atomic.
        preserve: Keep the source object's natural representation. For pymatgen
            imports this currently behaves like analyze.
    """

    mode: SymmetryMode = "analyze"
    tolerance: float = SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE
    molecular_tolerance: float = SymmetryConstants.MOLECULAR_EQUIVALENCE_TOLERANCE
    drop_atomic_properties: bool = False
    fallback_full_atomic: bool = False

    @classmethod
    def from_import_flags(
        cls,
        *,
        force_symmetric: bool = False,
        drop_atomic_properties: bool = False,
        fallback_full_atomic: bool = False,
        tolerance: float = SymmetryConstants.DEFAULT_SPACEGROUP_TOLERANCE,
        molecular_tolerance: float = SymmetryConstants.MOLECULAR_EQUIVALENCE_TOLERANCE,
    ) -> "SymmetryPolicy":
        """Build a policy from the public importer flags."""
        return cls(
            mode="reduce" if force_symmetric else "analyze",
            tolerance=tolerance,
            molecular_tolerance=molecular_tolerance,
            drop_atomic_properties=drop_atomic_properties,
            fallback_full_atomic=fallback_full_atomic,
        )

    def resolve_atomic_properties(self, has_atomic_properties: bool, names: str) -> tuple[bool, bool]:
        """Return ``(try_symmetric, drop_properties)`` for an import.

        Raises:
            ValidationError: if the policy requests reduction while preserving
                per-atom properties without an explicit fallback mode.
        """
        if self.drop_atomic_properties and self.fallback_full_atomic:
            raise ValidationError(
                "drop_atomic_properties and fallback_full_atomic are mutually exclusive"
            )

        if self.mode == "none":
            return False, False

        if self.mode == "reduce" and has_atomic_properties:
            if self.fallback_full_atomic:
                return False, False
            if self.drop_atomic_properties:
                return True, True
            raise ValidationError(
                "Symmetry reduction cannot preserve per-atom properties "
                f"({names}). Set fallback_full_atomic=True to preserve them or "
                "drop_atomic_properties=True to explicitly discard them."
            )

        if has_atomic_properties:
            return False, False

        return True, False
