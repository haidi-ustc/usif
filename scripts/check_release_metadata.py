#!/usr/bin/env python3
"""Validate USIF release metadata before packaging.

The editable release source is ``pyproject.toml``.  This script checks that the
package version, date-based release record, baked wheel fallback constants,
changelog entry, and CI wheel smoke test all refer to the same release.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
RELEASE_RECORD_RE = re.compile(r"^(?P<yyyymmdd>\d{8})\.(?P<sequence>\d{3})$")


@dataclass(frozen=True)
class ReleaseMetadata:
    version: str
    date: str
    sequence: int
    record: str
    release_id: str

    @property
    def compact_date(self) -> str:
        return self.date.replace("-", "")

    @property
    def sequence_suffix(self) -> str:
        return f"{self.sequence:03d}"

    @property
    def expected_record(self) -> str:
        return f"{self.compact_date}.{self.sequence_suffix}"

    @property
    def expected_id(self) -> str:
        return f"usif-{self.compact_date}-{self.sequence_suffix}"


def _read_pyproject(root: Path) -> dict[str, Any]:
    path = root / "pyproject.toml"
    if not path.exists():
        raise AssertionError("pyproject.toml is missing")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def read_release_metadata(root: Path) -> ReleaseMetadata:
    data = _read_pyproject(root)
    project = data.get("project", {})
    release = data.get("tool", {}).get("usif", {}).get("release", {})
    try:
        return ReleaseMetadata(
            version=str(project["version"]),
            date=str(release["date"]),
            sequence=int(release["sequence"]),
            record=str(release["record"]),
            release_id=str(release["id"]),
        )
    except KeyError as exc:  # pragma: no cover - defensive error path
        raise AssertionError(f"missing release metadata key: {exc}") from exc


def _assert_contains(path: Path, needle: str) -> None:
    if not path.exists():
        raise AssertionError(f"required file is missing: {path}")
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise AssertionError(f"{path} does not contain {needle!r}")


def _extract_constant(text: str, name: str) -> str:
    pattern = re.compile(rf"^{re.escape(name)}\s*=\s*(?P<value>.+)$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        raise AssertionError(f"missing constant {name}")
    value = match.group("value").strip()
    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        return value[1:-1]
    return value


def validate_release_metadata(root: Path) -> ReleaseMetadata:
    root = root.resolve()
    meta = read_release_metadata(root)

    if not SEMVER_RE.match(meta.version):
        raise AssertionError(f"project.version must be X.Y.Z, got {meta.version!r}")

    record_match = RELEASE_RECORD_RE.match(meta.record)
    if not record_match:
        raise AssertionError(f"release record must be YYYYMMDD.NNN, got {meta.record!r}")
    if record_match.group("yyyymmdd") != meta.compact_date:
        raise AssertionError("release record date does not match release date")
    if record_match.group("sequence") != meta.sequence_suffix:
        raise AssertionError("release record sequence does not match release sequence")
    if meta.record != meta.expected_record:
        raise AssertionError(f"expected record {meta.expected_record}, got {meta.record}")
    if meta.release_id != meta.expected_id:
        raise AssertionError(f"expected release id {meta.expected_id}, got {meta.release_id}")

    version_py = root / "usif" / "version.py"
    version_text = version_py.read_text(encoding="utf-8")
    constants = {
        "_FALLBACK_VERSION": meta.version,
        "_FALLBACK_RELEASE_DATE": meta.date,
        "_FALLBACK_RELEASE_SEQUENCE": str(meta.sequence),
        "_FALLBACK_RELEASE_RECORD": meta.record,
        "_FALLBACK_RELEASE_ID": meta.release_id,
    }
    for name, expected in constants.items():
        actual = _extract_constant(version_text, name)
        if actual != expected:
            raise AssertionError(f"{name} is {actual!r}, expected {expected!r}")

    changelog = root / "docs" / "CHANGELOG.md"
    changelog_text = changelog.read_text(encoding="utf-8")
    first_heading = next(
        (line.strip() for line in changelog_text.splitlines() if line.startswith("## ")), ""
    )
    if first_heading != f"## {meta.version}":
        raise AssertionError(
            f"CHANGELOG latest heading is {first_heading!r}, expected ## {meta.version}"
        )
    if meta.record not in changelog_text.split("## ", 2)[1]:
        raise AssertionError("CHANGELOG latest entry does not include the release record")
    if meta.release_id not in changelog_text.split("## ", 2)[1]:
        raise AssertionError("CHANGELOG latest entry does not include the release id")

    _assert_contains(
        root / ".github" / "workflows" / "ci.yml", f'usif.__version__ == "{meta.version}"'
    )
    _assert_contains(
        root / ".github" / "workflows" / "ci.yml", f'usif.RELEASE_RECORD == "{meta.record}"'
    )
    _assert_contains(root / "docs" / "RELEASE.md", "python scripts/check_release_metadata.py")
    _assert_contains(root / "docs" / "RELEASE.md", f'version = "{meta.version}"')
    _assert_contains(root / "docs" / "RELEASE.md", f'usif.RELEASE_RECORD == "{meta.record}"')
    return meta


def _write_report(path: Path, meta: ReleaseMetadata) -> None:
    path.write_text(
        "\n".join(
            [
                "USIF release metadata check: PASS",
                f"version={meta.version}",
                f"date={meta.date}",
                f"sequence={meta.sequence}",
                f"record={meta.record}",
                f"id={meta.release_id}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--write-report", type=Path, help="optional release-checks.txt path")
    args = parser.parse_args(argv)

    try:
        meta = validate_release_metadata(args.root)
    except Exception as exc:  # noqa: BLE001 - CLI should report any validation failure clearly
        print(f"release metadata check failed: {exc}", file=sys.stderr)
        return 1

    if args.write_report:
        _write_report(args.write_report, meta)
    print(f"release metadata OK: version={meta.version} record={meta.record} id={meta.release_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess/CI
    raise SystemExit(main())
