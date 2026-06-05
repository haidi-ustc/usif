"""Container validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Iterable, List, Literal

from usif.encoder import USIF
from usif.exceptions import CorruptedDataError, StorageError
from usif.format.binary import USIFHeader
from usif.storage.groups import USIFGroup

ValidationLevel = Literal["index", "records", "full"]


@dataclass(frozen=True)
class ContainerValidationResult:
    """Result returned by ``StructureContainer.validate()``."""

    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    structure_count: int = 0
    group_count: int = 0
    level: str = "index"
    checked_records: int = 0
    elapsed_seconds: float = 0.0


class ContainerValidator:
    """Validate consistency between container indexes, groups, and records."""

    VALID_LEVELS = {"index", "records", "full"}

    def __init__(self, container: Any) -> None:
        self.container = container

    def validate(self, *, level: ValidationLevel = "index") -> ContainerValidationResult:
        """Validate a container at the requested cost/assurance level.

        ``index`` checks manifest consistency only. ``records`` also reads each
        record byte range and validates its USIF header/length. ``full`` decodes
        every record and verifies its persisted record hash.
        """
        if level not in self.VALID_LEVELS:
            raise ValueError(f"Invalid validation level {level!r}; expected one of {sorted(self.VALID_LEVELS)}")

        start = time.perf_counter()
        errors: List[str] = []
        warnings: List[str] = []
        checked_records = 0
        record_hashes = set(self.container._record_index)

        for record_hash, location in self.container._record_index.items():
            if not isinstance(record_hash, str) or not record_hash:
                errors.append("record index contains an empty or non-string hash")
            if len(location) != 3:
                errors.append(f"record {record_hash!r} has invalid location tuple {location!r}")
                continue
            chunk_id, offset, size = location
            if chunk_id < 0 or offset < 0 or size <= 0:
                errors.append(f"record {record_hash!r} has invalid chunk location {location!r}")
                continue
            if level in {"records", "full"}:
                self._validate_record_bytes(record_hash, location, errors)
                checked_records += 1
            if level == "full":
                self._validate_record_decode(record_hash, errors)

        self._validate_hash_references("name_index", self.container._name_index.values(), record_hashes, errors)
        self._validate_hash_references(
            "geometry_index",
            (item for bucket in self.container._geometry_index.values() for item in bucket),
            record_hashes,
            errors,
        )
        self._validate_hash_references(
            "formula_index",
            (item for bucket in self.container._formula_index.values() for item in bucket),
            record_hashes,
            errors,
        )
        self._validate_hash_references(
            "property_index",
            (
                item
                for prop_buckets in self.container._property_index.values()
                for bucket in prop_buckets.values()
                for item in bucket
            ),
            record_hashes,
            errors,
        )

        group_count = self._validate_group(self.container.root_group, record_hashes, errors, path="/")

        for name in self.container._structure_attributes:
            if name not in self.container._name_index:
                warnings.append(f"attributes exist for unknown structure alias {name!r}")

        return ContainerValidationResult(
            ok=not errors,
            errors=errors,
            warnings=warnings,
            structure_count=len(record_hashes),
            group_count=group_count,
            level=level,
            checked_records=checked_records,
            elapsed_seconds=time.perf_counter() - start,
        )

    def _validate_record_bytes(self, record_hash: str, location: tuple[int, int, int], errors: List[str]) -> None:
        chunk_id, offset, size = location
        try:
            data = self.container._read_from_chunk(chunk_id, offset, size)
            if len(data) != size:
                errors.append(f"record {record_hash!r} read {len(data)} bytes, expected {size}")
                return
            if size < USIF.HEADER_SIZE:
                errors.append(f"record {record_hash!r} is shorter than the USIF header")
                return
            header = USIFHeader.parse(data)
            expected_size = USIF.HEADER_SIZE + header.compressed_size
            if expected_size != size:
                errors.append(
                    f"record {record_hash!r} size mismatch: index {size}, header {expected_size}"
                )
        except (StorageError, CorruptedDataError, ValueError) as exc:
            errors.append(f"record {record_hash!r} byte validation failed: {exc}")
        except Exception as exc:  # pragma: no cover - defensive reliability path
            errors.append(f"record {record_hash!r} byte validation failed: {exc}")

    def _validate_record_decode(self, record_hash: str, errors: List[str]) -> None:
        try:
            structure = self.container.get(record_hash)
            if structure is None:
                errors.append(f"record {record_hash!r} cannot be decoded")
                return
            actual_hash = self.container.encoder.get_record_hash(structure)
            if actual_hash != record_hash:
                errors.append(
                    f"record {record_hash!r} hash mismatch after decode: decoded {actual_hash!r}"
                )
        except Exception as exc:  # pragma: no cover - exercised through reliability tests
            errors.append(f"record {record_hash!r} decode failed: {exc}")

    @staticmethod
    def _validate_hash_references(
        index_name: str,
        references: Iterable[str],
        record_hashes: set[str],
        errors: List[str],
    ) -> None:
        for reference in references:
            if reference not in record_hashes:
                errors.append(f"{index_name} references unknown record {reference!r}")

    def _validate_group(
        self,
        group: USIFGroup,
        record_hashes: set[str],
        errors: List[str],
        *,
        path: str,
    ) -> int:
        group_count = 1
        for name, record_hash in group.structures.items():
            if record_hash not in record_hashes:
                errors.append(f"group {path!r} structure {name!r} references unknown record {record_hash!r}")
        for subgroup_name, subgroup in group.subgroups.items():
            subgroup_path = f"{path.rstrip('/')}/{subgroup_name}/"
            group_count += self._validate_group(subgroup, record_hashes, errors, path=subgroup_path)
        return group_count
