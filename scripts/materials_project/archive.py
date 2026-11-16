"""Archive creation and safe extraction for Materials Project datasets."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Optional, Union


def create_mp_data_archive(data_dir: Union[str, Path]) -> Path:
    """Create a zip archive from a downloaded Materials Project dataset directory."""
    data_path = Path(data_dir)
    zip_path = data_path.parent / f"{data_path.name}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for group_dir in sorted(data_path.glob("group_*")):
            if group_dir.is_dir():
                materials_file = group_dir / "materials.json"
                if materials_file.exists():
                    zipf.write(materials_file, arcname=f"{group_dir.name}/materials.json")

        metadata_file = data_path / "metadata.json"
        if metadata_file.exists():
            zipf.write(metadata_file, arcname="metadata.json")

    return zip_path


DEFAULT_MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_MEMBER_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_MEMBERS = 10_000


def safe_extract(
    zip_file: zipfile.ZipFile,
    target_dir: Union[str, Path],
    *,
    max_total_bytes: int = DEFAULT_MAX_EXTRACTED_BYTES,
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
    max_members: int = DEFAULT_MAX_MEMBERS,
) -> None:
    """Safely extract a zip archive without Zip Slip or zip-bomb expansion.

    Size limits are checked against each member's declared uncompressed size
    before extraction and streamed while copying.
    """
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    members = zip_file.infolist()
    if len(members) > max_members:
        raise ValueError(f"Zip archive has too many members: {len(members)} > {max_members}")

    total_uncompressed = 0
    for member in members:
        member_name = member.filename
        if Path(member_name).is_absolute():
            raise ValueError(f"Unsafe absolute zip member path: {member_name}")

        destination = (target_path / member_name).resolve()
        try:
            destination.relative_to(target_path)
        except ValueError as e:
            raise ValueError(f"Unsafe zip member path outside target: {member_name}") from e

        if member.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue

        if member.file_size > max_member_bytes:
            raise ValueError(
                f"Zip member is too large: {member_name} "
                f"({member.file_size} > {max_member_bytes} bytes)"
            )
        total_uncompressed += member.file_size
        if total_uncompressed > max_total_bytes:
            raise ValueError(
                f"Zip archive expands beyond configured limit: "
                f"{total_uncompressed} > {max_total_bytes} bytes"
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        copied = 0
        with zip_file.open(member, "r") as src, open(destination, "wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > max_member_bytes:
                    raise ValueError(f"Zip member exceeded limit while extracting: {member_name}")
                dst.write(chunk)


def load_mp_data_from_archive(
    zip_path: Union[str, Path], extract_to: Optional[Union[str, Path]] = None
) -> Path:
    """Extract a Materials Project dataset archive and return the target directory."""
    archive_path = Path(zip_path)
    target = archive_path.parent / archive_path.stem if extract_to is None else Path(extract_to)
    target.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zipf:
        safe_extract(zipf, target)

    return target
