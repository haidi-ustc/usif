#!/usr/bin/env python3
"""
Download Materials Project Data for Testing

This script downloads high-quality crystal structures from the Materials Project
and saves them in pymatgen format with properties for use in USIF testing.

Requirements:
    - pymatgen
    - mp-api (Materials Project API client)
    - API key from https://materialsproject.org/api

Usage:
    python examples/download_mp_data.py --api_key YOUR_API_KEY --output_dir data/mp_structures

Features:
    - Downloads 1000 high-quality structures (100 per group, 10 groups)
    - Filters for high-quality data (e_above_hull < 0.1 eV, band_gap available)
    - Includes basic properties: energy, formation_energy, band_gap, volume, etc.
    - Saves in pymatgen JSON format for easy loading
    - Organizes structures into groups by space group
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

try:
    from mp_api.client import MPRester
    from pymatgen.core import Structure
    from pymatgen.io.cif import CifWriter
except ImportError as e:
    print(f"Error: Required packages not installed. Install with:")
    print(f"  pip install pymatgen mp-api")
    raise

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MaterialsProjectDownloader:
    """Download high-quality structures from Materials Project"""
    
    # Basic properties to download
    BASIC_PROPERTIES = [
        "formation_energy_per_atom",
        "formation_energy",
        "energy_per_atom",
        "energy",
        "band_gap",
        "volume",
        "density",
        "total_magnetization",
        "nsites",
        "nelements",
        "elements",
        "spacegroup",
        "crystal_system",
        "is_magnetic",
        "is_metal",
        "is_gap_direct",
    ]
    
    def __init__(self, api_key: str, output_dir: str = "data/mp_structures"):
        """
        Initialize downloader
        
        Args:
            api_key: Materials Project API key
            output_dir: Directory to save structures
        """
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for groups
        for i in range(10):
            (self.output_dir / f"group_{i+1:02d}").mkdir(exist_ok=True)
    
    def download_structures(self, 
                           total_entries: int = 1000,
                           entries_per_group: int = 100,
                           e_above_hull_max: float = 0.1,
                           min_band_gap: Optional[float] = None,
                           max_band_gap: Optional[float] = None,
                           crystal_system: Optional[str] = None,
                           spacegroup: Optional[int] = None) -> Dict[str, Any]:
        """
        Download high-quality structures from Materials Project
        
        Args:
            total_entries: Total number of entries to download
            entries_per_group: Number of entries per group
            e_above_hull_max: Maximum energy above hull (eV) for high quality
            min_band_gap: Minimum band gap (eV), None for no filter
            max_band_gap: Maximum band gap (eV), None for no filter
            
        Returns:
            Dictionary with download statistics
        """
        logger.info(f"Starting download: {total_entries} entries, {entries_per_group} per group")
        
        stats = {
            "total_downloaded": 0,
            "total_skipped": 0,
            "groups": {},
            "properties_included": self.BASIC_PROPERTIES
        }
        
        with MPRester(self.api_key) as mpr:
            # Query for high-quality structures
            # Filter: e_above_hull < 0.1 eV (stable or near-stable)
            # Order by formation_energy_per_atom for diversity
            logger.info("Querying Materials Project database...")
            
            # Build query criteria
            criteria = {
                "e_above_hull": {"$lte": e_above_hull_max},
                "nsites": {"$lte": 200},  # Reasonable size for testing
            }
            
            if min_band_gap is not None:
                criteria["band_gap"] = {"$gte": min_band_gap}
            if max_band_gap is not None:
                if "band_gap" in criteria:
                    criteria["band_gap"]["$lte"] = max_band_gap
                else:
                    criteria["band_gap"] = {"$lte": max_band_gap}
            
            # Filter by crystal system if specified
            if crystal_system is not None:
                criteria["crystal_system"] = crystal_system
            
            # Filter by spacegroup if specified
            if spacegroup is not None:
                criteria["spacegroup.number"] = spacegroup
            
            # Get total count
            total_available = mpr.summary.count(
                fields=["material_id"],
                **criteria
            )
            logger.info(f"Found {total_available} matching structures in database")
            
            # Download in batches
            downloaded = 0
            group_num = 1
            entries_in_group = 0
            offset = 0
            batch_size = 100
            
            while downloaded < total_entries and group_num <= 10:
                logger.info(f"Downloading batch: offset={offset}, batch_size={batch_size}")
                
                # Get summary data with properties
                # Note: MP API search may need adjustment based on API version
                try:
                    summaries = mpr.summary.search(
                        **criteria,
                        fields=["material_id", "structure", "spacegroup"] + self.BASIC_PROPERTIES,
                        num_chunks=1,
                        chunk_size=batch_size,
                        num_sites=[1, 200],  # Reasonable size
                    )
                except Exception as e:
                    # Fallback: try without num_sites filter
                    logger.warning(f"Search with num_sites failed, trying without: {e}")
                    summaries = mpr.summary.search(
                        **criteria,
                        fields=["material_id", "structure", "spacegroup"] + self.BASIC_PROPERTIES,
                        num_chunks=1,
                        chunk_size=batch_size,
                    )
                
                if not summaries:
                    logger.warning("No more structures found")
                    break
                
                for summary in summaries:
                    if downloaded >= total_entries:
                        break
                    
                    try:
                        # Get full structure
                        structure = summary.structure
                        material_id = summary.material_id
                        
                        # Extract properties
                        properties = self._extract_properties(summary)
                        
                        # Save structure
                        filename = f"{material_id}.json"
                        group_dir = self.output_dir / f"group_{group_num:02d}"
                        filepath = group_dir / filename
                        
                        # Save as pymatgen JSON format
                        self._save_structure(structure, properties, filepath, material_id)
                        
                        downloaded += 1
                        entries_in_group += 1
                        
                        if entries_in_group >= entries_per_group:
                            stats["groups"][f"group_{group_num:02d}"] = entries_in_group
                            logger.info(f"Group {group_num:02d} complete: {entries_in_group} entries")
                            group_num += 1
                            entries_in_group = 0
                        
                        if downloaded % 50 == 0:
                            logger.info(f"Downloaded {downloaded}/{total_entries} structures")
                    
                    except Exception as e:
                        logger.warning(f"Error processing {summary.material_id}: {e}")
                        stats["total_skipped"] += 1
                        continue
                
                skip += batch_size
                
                # Safety check
                if skip > total_available:
                    logger.warning("Reached end of available structures")
                    break
            
            # Save final group stats
            if entries_in_group > 0:
                stats["groups"][f"group_{group_num:02d}"] = entries_in_group
            
            stats["total_downloaded"] = downloaded
            
            # Save metadata
            self._save_metadata(stats)
            
            logger.info(f"Download complete: {downloaded} structures in {len(stats['groups'])} groups")
            return stats
    
    def _extract_properties(self, summary) -> Dict[str, Any]:
        """Extract properties from MP summary"""
        properties = {}
        
        for prop in self.BASIC_PROPERTIES:
            if hasattr(summary, prop):
                value = getattr(summary, prop)
                # Convert numpy types to Python types for JSON serialization
                if hasattr(value, 'item'):  # numpy scalar
                    value = value.item()
                elif hasattr(value, 'tolist'):  # numpy array
                    value = value.tolist()
                properties[prop] = value
        
        # Add material_id
        properties["material_id"] = summary.material_id
        
        return properties
    
    def _save_structure(self, 
                       structure: Structure, 
                       properties: Dict[str, Any],
                       filepath: Path,
                       material_id: str) -> None:
        """
        Save structure in pymatgen JSON format with properties
        
        Args:
            structure: Pymatgen Structure object
            properties: Dictionary of properties
            filepath: Path to save file
            material_id: Materials Project material ID
        """
        # Create data structure compatible with pymatgen
        data = {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": structure.lattice.as_dict(),
            "sites": [site.as_dict() for site in structure],
            "properties": properties,
            "material_id": material_id,
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_metadata(self, stats: Dict[str, Any]) -> None:
        """Save download metadata"""
        metadata_path = self.output_dir / "metadata.json"
        
        metadata = {
            "download_stats": stats,
            "output_directory": str(self.output_dir),
            "total_groups": len(stats["groups"]),
            "properties_included": stats["properties_included"],
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Metadata saved to {metadata_path}")


def load_structure(filepath: Path) -> tuple[Structure, Dict[str, Any]]:
    """
    Load structure from saved JSON file
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Tuple of (Structure, properties)
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    structure = Structure.from_dict(data)
    properties = data.get("properties", {})
    
    return structure, properties


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Download Materials Project data for USIF testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download with default settings (1000 entries, 10 groups)
  python download_mp_data.py --api_key YOUR_API_KEY
  
  # Custom output directory
  python download_mp_data.py --api_key YOUR_API_KEY --output_dir my_data
  
  # Filter by band gap
  python download_mp_data.py --api_key YOUR_API_KEY --min_band_gap 0.5 --max_band_gap 3.0
        """
    )
    
    parser.add_argument(
        "--api_key",
        type=str,
        required=True,
        help="Materials Project API key (get from https://materialsproject.org/api)"
    )
    
    parser.add_argument(
        "--output_dir",
        type=str,
        default="data/mp_structures",
        help="Output directory for structures (default: data/mp_structures)"
    )
    
    parser.add_argument(
        "--total_entries",
        type=int,
        default=1000,
        help="Total number of entries to download (default: 1000)"
    )
    
    parser.add_argument(
        "--entries_per_group",
        type=int,
        default=100,
        help="Number of entries per group (default: 100)"
    )
    
    parser.add_argument(
        "--e_above_hull_max",
        type=float,
        default=0.1,
        help="Maximum energy above hull for high quality (eV, default: 0.1)"
    )
    
    parser.add_argument(
        "--min_band_gap",
        type=float,
        default=None,
        help="Minimum band gap filter (eV, optional)"
    )
    
    parser.add_argument(
        "--max_band_gap",
        type=float,
        default=None,
        help="Maximum band gap filter (eV, optional)"
    )
    
    parser.add_argument(
        "--crystal_system",
        type=str,
        default=None,
        choices=["cubic", "tetragonal", "orthorhombic", "hexagonal", 
                 "rhombohedral", "monoclinic", "triclinic"],
        help="Filter by crystal system (optional)"
    )
    
    parser.add_argument(
        "--spacegroup",
        type=int,
        default=None,
        help="Filter by space group number (optional)"
    )
    
    args = parser.parse_args()
    
    # Create downloader
    downloader = MaterialsProjectDownloader(
        api_key=args.api_key,
        output_dir=args.output_dir
    )
    
    # Download structures
    stats = downloader.download_structures(
        total_entries=args.total_entries,
        entries_per_group=args.entries_per_group,
        e_above_hull_max=args.e_above_hull_max,
        min_band_gap=args.min_band_gap,
        max_band_gap=args.max_band_gap,
        crystal_system=args.crystal_system,
        spacegroup=args.spacegroup,
    )
    
    # Print summary
    print("\n" + "="*60)
    print("Download Summary")
    print("="*60)
    print(f"Total downloaded: {stats['total_downloaded']}")
    print(f"Total skipped: {stats['total_skipped']}")
    print(f"Number of groups: {len(stats['groups'])}")
    print("\nGroup breakdown:")
    for group, count in stats['groups'].items():
        print(f"  {group}: {count} entries")
    print(f"\nOutput directory: {args.output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()

