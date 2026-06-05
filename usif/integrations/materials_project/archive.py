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


def safe_extract(zip_file: zipfile.ZipFile, target_dir: Union[str, Path]) -> None:
    """Safely extract a zip archive without allowing Zip Slip traversal."""
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    for member in zip_file.infolist():
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

        destination.parent.mkdir(parents=True, exist_ok=True)
        with zip_file.open(member, "r") as src, open(destination, "wb") as dst:
            dst.write(src.read())


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
