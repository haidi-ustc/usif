#!/usr/bin/env python3
"""
Materials Project Data Downloader and Loader

This module provides utilities for downloading Materials Project data
and converting it to USIF format. Designed for testing and benchmarking.

Main Functions:
    download_mp_data: Download MP structures with filtering
    load_mp_group: Load a group of MP documents from JSON
    convert_mp_to_usif: Convert MP document to USIF structure
    create_mp_data_archive: Create zip archive of downloaded data

Requirements:
    - pymatgen
    - mp-api (Materials Project API client)
    - monty (for serialization)

Usage:
    >>> from usif.utils.mp_downloader import download_mp_data, load_mp_group, convert_mp_to_usif
    >>>
    >>> # Download data
    >>> stats = download_mp_data(api_key="YOUR_KEY", total_entries=100)
    >>>
    >>> # Load and convert
    >>> docs = load_mp_group("data/mp_structures/group_01/materials.json")
    >>> usif_struct = convert_mp_to_usif(docs[0])
"""

import logging
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from monty.serialization import dumpfn, loadfn
    from mp_api.client import MPRester
    from pymatgen.core import Structure
except ImportError as e:
    raise ImportError(
        "Required packages not installed. Install with: pip install pymatgen mp-api monty"
    ) from e

from usif import USIFStructure

logger = logging.getLogger(__name__)


def download_mp_data(
    api_key: str,
    output_dir: str = "tests/data/mp_structures",
    total_entries: int = 1000,
    entries_per_group: int = 100,
    e_above_hull_max: float = 0.1,
    min_band_gap: Optional[float] = None,
    max_band_gap: Optional[float] = None,
    rate_limit: float = 2.0,
    create_zip: bool = True,
) -> Dict[str, Any]:
    """
    Download Materials Project data for USIF testing

    Uses materials.summary.search to query and download structures.
    Saves in monty JSON format for easy loading. Optionally creates zip archive.

    Args:
        api_key: Materials Project API key
        output_dir: Directory to save structures
        total_entries: Total number of entries to download
        entries_per_group: Number of entries per group
        e_above_hull_max: Maximum energy above hull (eV) for high quality
        min_band_gap: Minimum band gap (eV), None for no filter
        max_band_gap: Maximum band gap (eV), None for no filter
        rate_limit: Delay between API requests (seconds)
        create_zip: Whether to create zip archive after download

    Returns:
        Dictionary with download statistics including zip_file path if created
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for groups
    for i in range(10):
        (output_path / f"group_{i + 1:02d}").mkdir(exist_ok=True)

    # Define 10 diverse chemistry groups with distinct properties
    query_groups = [
        {"chemsys": "Si-Ge", "band_gap": (0.0, 1.0)},
        {"chemsys": "Ga-As", "band_gap": (0.0, 2.0)},
        {"chemsys": "In-P", "band_gap": (0.0, 2.5)},
        {"chemsys": "C-N", "band_gap": (0.0, 6.0)},
        {"chemsys": "Li-Fe-P", "band_gap": (0.0, 1.5)},
        {"chemsys": "Na-Cl", "band_gap": (4.0, 6.0)},
        {"chemsys": "Mg-Si", "band_gap": (0.0, 3.0)},
        {"chemsys": "B-N", "band_gap": (0.0, 6.5)},
        {"chemsys": "Cu-S", "band_gap": (0.0, 2.5)},
        {"elements": ["Al", "Si", "N"], "band_gap": (2.0, 5.0)},
    ]

    # Properties to retrieve (structure is included for USIF conversion)
    fields = [
        "material_id",
        "formula_pretty",
        "nelements",
        "nsites",
        "elements",
        "band_gap",
        "energy_above_hull",
        "formation_energy_per_atom",
        "energy_per_atom",
        "density",
        "volume",
        "total_magnetization",
        "symmetry",  # Contains spacegroup and crystal_system
        "is_magnetic",
        "is_metal",
        "is_gap_direct",
        "is_stable",
        "composition",
        "structure",  # Pymatgen Structure object for USIF conversion
    ]

    stats = {
        "total_downloaded": 0,
        "total_skipped": 0,
        "total_filtered": 0,
        "groups": {},
    }

    with MPRester(api_key) as mpr:
        for group_idx, query in enumerate(query_groups, start=1):
            if stats["total_downloaded"] >= total_entries:
                break

            logger.info(f"Group {group_idx}/10: {query}")

            # Build search parameters
            search_kwargs = {
                k: v
                for k, v in query.items()
                if k in ["chemsys", "elements", "band_gap"]
            }

            # Apply band gap filters if specified
            if min_band_gap is not None or max_band_gap is not None:
                bg_min = min_band_gap if min_band_gap is not None else 0.0
                bg_max = max_band_gap if max_band_gap is not None else 10.0
                search_kwargs["band_gap"] = (bg_min, bg_max)
            elif "band_gap" in search_kwargs:
                # Use query's band_gap if no override
                pass

            # Add num_sites limit for reasonable structure sizes
            search_kwargs["num_sites"] = (1, 200)

            try:
                # Query materials.summary.search
                docs = list(
                    mpr.materials.summary.search(
                        **search_kwargs,
                        fields=fields,
                        num_chunks=None,  # Get all chunks
                        chunk_size=1000,
                    )
                )

                logger.info(f"  Found {len(docs)} materials")

                # Filter by energy_above_hull and save
                group_docs = []
                group_dir = output_path / f"group_{group_idx:02d}"

                for doc in docs:
                    if stats["total_downloaded"] >= total_entries:
                        break

                    # Filter by energy_above_hull
                    if (
                        hasattr(doc, "energy_above_hull")
                        and doc.energy_above_hull is not None
                    ):
                        if doc.energy_above_hull > e_above_hull_max:
                            stats["total_filtered"] += 1
                            continue

                    # Check if structure exists
                    if not hasattr(doc, "structure") or doc.structure is None:
                        stats["total_skipped"] += 1
                        continue

                    group_docs.append(doc)
                    stats["total_downloaded"] += 1

                    # Stop when we have enough for this group
                    if len(group_docs) >= entries_per_group:
                        break

                # Save group
                if group_docs:
                    output_file = group_dir / "materials.json"
                    dumpfn(group_docs, str(output_file))
                    group_key = f"group_{group_idx:02d}"
                    stats["groups"][group_key] = len(group_docs)
                    logger.info(f"  Saved {len(group_docs)} materials to {output_file}")
                else:
                    logger.info("  No materials passed filters, skipped")

            except Exception as e:
                logger.error(f"  Error querying group {group_idx}: {e}")
                continue

            # Rate limiting between groups
            if group_idx < len(query_groups):
                time.sleep(rate_limit)

    # Save metadata
    metadata = {
        "download_stats": stats,
        "output_directory": str(output_path),
        "total_groups": len(stats["groups"]),
        "fields_included": fields,
    }
    dumpfn(metadata, str(output_path / "metadata.json"))

    # Create zip archive if requested
    zip_file = None
    if create_zip and stats["total_downloaded"] > 0:
        zip_file = create_mp_data_archive(output_path)
        stats["zip_file"] = str(zip_file)
        logger.info(f"Created zip archive: {zip_file}")

    return stats


def create_mp_data_archive(data_dir: Union[str, Path]) -> Path:
    """
    Create a zip archive of downloaded MP data

    Args:
        data_dir: Directory containing MP data (with group_XX subdirectories)

    Returns:
        Path to created zip file
    """
    data_path = Path(data_dir)
    zip_path = data_path.parent / f"{data_path.name}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add all group directories
        for group_dir in sorted(data_path.glob("group_*")):
            if group_dir.is_dir():
                materials_file = group_dir / "materials.json"
                if materials_file.exists():
                    arcname = f"{group_dir.name}/materials.json"
                    zipf.write(materials_file, arcname=arcname)

        # Add metadata
        metadata_file = data_path / "metadata.json"
        if metadata_file.exists():
            zipf.write(metadata_file, arcname="metadata.json")

    return zip_path


def load_mp_data_from_archive(
    zip_path: Union[str, Path], extract_to: Optional[Union[str, Path]] = None
) -> Path:
    """
    Load MP data from zip archive

    Args:
        zip_path: Path to zip archive
        extract_to: Directory to extract to (default: same directory as zip)

    Returns:
        Path to extracted directory
    """
    zip_path = Path(zip_path)
    if extract_to is None:
        extract_to = zip_path.parent / zip_path.stem
    else:
        extract_to = Path(extract_to)

    extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zipf:
        zipf.extractall(extract_to)

    return extract_to


def load_mp_group(group_file: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Load a group of Materials Project documents

    Args:
        group_file: Path to group JSON file (e.g., "group_01/materials.json")

    Returns:
        List of MP documents (as dictionaries) with structure and properties
    """
    group_path = Path(group_file)
    if not group_path.exists():
        raise FileNotFoundError(f"Group file not found: {group_file}")

    return loadfn(str(group_path))


def convert_mp_to_usif(doc: Union[Dict[str, Any], Any]) -> USIFStructure:
    """
    Convert a Materials Project document to USIF structure

    Handles both MPDataDoc objects and dictionaries (from loaded JSON).

    Args:
        doc: MPDataDoc from materials.summary.search, or dict from loadfn

    Returns:
        USIFStructure instance with properties extracted from MP document

    Raises:
        ValueError: If document doesn't contain structure information
    """
    # Handle both dict (from loaded JSON) and MPDataDoc object
    if isinstance(doc, dict):
        # Loaded from JSON - reconstruct structure
        structure_dict = doc.get("structure")
        if structure_dict is None:
            raise ValueError("Document does not contain 'structure' key")

        # Reconstruct pymatgen Structure from dict
        if isinstance(structure_dict, dict):
            structure = Structure.from_dict(structure_dict)
        else:
            # Already a Structure object
            structure = structure_dict

        # Extract properties from dict
        properties = {}
        # Energy (formation energy per atom * nsites)
        formation_energy_per_atom = doc.get("formation_energy_per_atom")
        nsites = doc.get("nsites")
        if formation_energy_per_atom is not None and nsites is not None:
            properties["energy"] = formation_energy_per_atom * nsites

        # Volume
        if doc.get("volume") is not None:
            properties["volume"] = doc["volume"]

        # Store additional MP properties in custom dict
        # Note: Don't duplicate built-in properties (energy, volume) in custom
        custom_props = {}
        if doc.get("band_gap") is not None:
            custom_props["band_gap"] = doc["band_gap"]
        if doc.get("density") is not None:
            custom_props["density"] = doc["density"]
        if doc.get("total_magnetization") is not None:
            custom_props["total_magnetization"] = doc["total_magnetization"]
        if doc.get("is_magnetic") is not None:
            custom_props["is_magnetic"] = doc["is_magnetic"]
        if doc.get("is_metal") is not None:
            custom_props["is_metal"] = doc["is_metal"]
        if doc.get("is_stable") is not None:
            custom_props["is_stable"] = doc["is_stable"]
        if doc.get("material_id") is not None:
            custom_props["material_id"] = doc["material_id"]
        if doc.get("formula_pretty") is not None:
            custom_props["formula_pretty"] = doc["formula_pretty"]

        if custom_props:
            properties["custom"] = custom_props
    else:
        # MPDataDoc object - use attributes
        if not hasattr(doc, "structure") or doc.structure is None:
            raise ValueError("Document does not have 'structure' attribute")
        structure = doc.structure

        # Extract properties from object
        properties = {}
        # Energy (formation energy per atom * nsites)
        if (
            hasattr(doc, "formation_energy_per_atom")
            and doc.formation_energy_per_atom is not None
        ):
            if hasattr(doc, "nsites") and doc.nsites is not None:
                properties["energy"] = doc.formation_energy_per_atom * doc.nsites

        # Volume
        if hasattr(doc, "volume") and doc.volume is not None:
            properties["volume"] = doc.volume

        # Store additional MP properties in custom dict
        # Note: Don't duplicate built-in properties (energy, volume) in custom
        custom_props = {}
        if hasattr(doc, "band_gap") and doc.band_gap is not None:
            custom_props["band_gap"] = doc.band_gap
        if hasattr(doc, "density") and doc.density is not None:
            custom_props["density"] = doc.density
        if hasattr(doc, "total_magnetization") and doc.total_magnetization is not None:
            custom_props["total_magnetization"] = doc.total_magnetization
        if hasattr(doc, "is_magnetic") and doc.is_magnetic is not None:
            custom_props["is_magnetic"] = doc.is_magnetic
        if hasattr(doc, "is_metal") and doc.is_metal is not None:
            custom_props["is_metal"] = doc.is_metal
        if hasattr(doc, "is_stable") and doc.is_stable is not None:
            custom_props["is_stable"] = doc.is_stable
        if hasattr(doc, "material_id") and doc.material_id is not None:
            custom_props["material_id"] = doc.material_id
        if hasattr(doc, "formula_pretty") and doc.formula_pretty is not None:
            custom_props["formula_pretty"] = doc.formula_pretty

        if custom_props:
            properties["custom"] = custom_props

    # Convert using USIFStructure.from_pymatgen
    # Extract custom properties separately
    custom_props = properties.pop("custom", {})

    # Built-in properties that should not be passed as kwargs
    # (they're handled directly by from_pymatgen or set from structure)
    built_in_props = {"energy", "volume", "stress", "pressure", "temperature"}

    # Separate built-in properties from kwargs
    built_in_kwargs = {}
    other_kwargs = {}
    for k, v in properties.items():
        if k in built_in_props:
            built_in_kwargs[k] = v
        else:
            other_kwargs[k] = v

    # Convert - pass built-in properties explicitly, others as kwargs
    usif_struct = USIFStructure.from_pymatgen(
        structure,
        energy=built_in_kwargs.get("energy"),
        volume=built_in_kwargs.get(
            "volume"
        ),  # Will override pymatgen volume if provided
        **other_kwargs,
    )

    # Add custom properties (MP-specific metadata)
    if custom_props:
        usif_struct.structure_properties.custom.update(custom_props)

    return usif_struct
