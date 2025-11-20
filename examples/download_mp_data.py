#!/usr/bin/env python3
"""
Download Materials Project Data for Testing

This script downloads high-quality crystal structures from the Materials Project
and saves them in a format that's easy to load and convert to USIF format.

Requirements:
    - pymatgen
    - mp-api (Materials Project API client)
    - monty (for serialization)
    - API key from https://materialsproject.org/api

Usage:
    # Using environment variable
    export MP_API_KEY=your_key_here
    python examples/download_mp_data.py
    
    # Or pass API key directly
    python examples/download_mp_data.py --api_key YOUR_API_KEY

Features:
    - Downloads 1000 high-quality structures (100 per group, 10 groups)
    - Uses materials.summary.search for efficient querying
    - Saves in monty JSON format (easy to load with monty.serialization.loadfn)
    - Creates zip archive of downloaded data
    - Rate-limited downloads (no multi-threading)
"""

import argparse
import os
from pathlib import Path

from usif.utils.mp_downloader import (
    convert_mp_to_usif,
    download_mp_data,
    load_mp_group,
)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Download Materials Project data for USIF testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variable
  export MP_API_KEY=your_key_here
  python download_mp_data.py
  
  # Custom settings
  python download_mp_data.py --api_key YOUR_KEY --total_entries 500 --entries_per_group 50
  
  # Filter by band gap
  python download_mp_data.py --min_band_gap 0.5 --max_band_gap 3.0
  
  # Disable zip creation
  python download_mp_data.py --no_zip
        """
    )
    
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="Materials Project API key. If not provided, uses MP_API_KEY environment variable."
    )
    
    parser.add_argument(
        "--output_dir",
        type=str,
        default="tests/data/mp_structures",
        help="Output directory for structures (default: tests/data/mp_structures)"
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
        help="Minimum band gap filter (eV, optional, overrides group defaults)"
    )
    
    parser.add_argument(
        "--max_band_gap",
        type=float,
        default=None,
        help="Maximum band gap filter (eV, optional, overrides group defaults)"
    )
    
    parser.add_argument(
        "--rate_limit",
        type=float,
        default=2.0,
        help="Rate limit delay between groups in seconds (default: 2.0)"
    )
    
    parser.add_argument(
        "--no_zip",
        action="store_true",
        help="Disable zip archive creation"
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.getenv("MP_API_KEY")
    if not api_key:
        parser.error("API key required. Provide --api_key or set MP_API_KEY environment variable.")
    
    # Download
    stats = download_mp_data(
        api_key=api_key,
        output_dir=args.output_dir,
        total_entries=args.total_entries,
        entries_per_group=args.entries_per_group,
        e_above_hull_max=args.e_above_hull_max,
        min_band_gap=args.min_band_gap,
        max_band_gap=args.max_band_gap,
        rate_limit=args.rate_limit,
        create_zip=not args.no_zip,
    )
    
    # Print summary
    print("\n" + "="*60)
    print("Download Summary")
    print("="*60)
    print(f"Total downloaded: {stats['total_downloaded']}")
    print(f"Total skipped: {stats['total_skipped']}")
    print(f"Total filtered: {stats.get('total_filtered', 0)}")
    print(f"Number of groups: {len(stats['groups'])}")
    print("\nGroup breakdown:")
    for group, count in stats['groups'].items():
        print(f"  {group}: {count} entries")
    print(f"\nOutput directory: {args.output_dir}")
    if 'zip_file' in stats:
        print(f"Zip archive: {stats['zip_file']}")
    print("\nTo load and convert to USIF:")
    print("  from usif.utils.mp_downloader import load_mp_group, convert_mp_to_usif")
    print("  docs = load_mp_group('tests/data/mp_structures/group_01/materials.json')")
    print("  usif_struct = convert_mp_to_usif(docs[0])")
    print("="*60)


if __name__ == "__main__":
    main()
