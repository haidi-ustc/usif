"""Container validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List

from usif.storage.groups import USIFGroup


@dataclass(frozen=True)
class ContainerValidationResult:
    """Result returned by ``StructureContainer.validate()``."""

    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    structure_count: int = 0
    group_count: int = 0


class ContainerValidator:
    """Validate consistency between container indexes, groups, and records."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def validate(self, *, decode_records: bool = False) -> ContainerValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
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
            if decode_records:
                try:
                    if self.container.get(record_hash) is None:
                        errors.append(f"record {record_hash!r} cannot be decoded")
                except Exception as exc:  # pragma: no cover - exercised through reliability tests
                    errors.append(f"record {record_hash!r} decode failed: {exc}")

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
        )

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
