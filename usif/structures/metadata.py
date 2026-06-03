"""Metadata models for USIF structures."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

SYMMETRY_METADATA_KEY = "__usif_symmetry_metadata__"


@dataclass(frozen=True)
class SymmetryMetadata:
    """Describe whether a symmetric representation can reconstruct the source."""

    lossless: bool
    reconstruction_mode: str
    symmetry_origin: str
    source_coordinate_frame: str
    tolerance: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymmetryMetadata":
        return cls(
            lossless=bool(data["lossless"]),
            reconstruction_mode=str(data["reconstruction_mode"]),
            symmetry_origin=str(data["symmetry_origin"]),
            source_coordinate_frame=str(data["source_coordinate_frame"]),
            tolerance=data.get("tolerance"),
        )
