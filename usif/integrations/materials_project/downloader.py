"""High-level Materials Project dataset downloader."""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .archive import create_mp_data_archive
from .client import MaterialsProjectClient
from .dependencies import require_monty
from .query import QUERY_GROUPS, SUMMARY_FIELDS, build_search_kwargs

logger = logging.getLogger(__name__)


def _passes_quality_filters(doc: Any, e_above_hull_max: float) -> bool:
    energy_above_hull = getattr(doc, "energy_above_hull", None)
    if energy_above_hull is not None and energy_above_hull > e_above_hull_max:
        return False
    return getattr(doc, "structure", None) is not None


def download_mp_data(
    api_key: str,
    output_dir: Optional[str] = None,
    total_entries: int = 1000,
    entries_per_group: int = 100,
    e_above_hull_max: float = 0.1,
    min_band_gap: Optional[float] = None,
    max_band_gap: Optional[float] = None,
    rate_limit: float = 2.0,
    create_zip: bool = True,
) -> Dict[str, Any]:
    """Download Materials Project structures for USIF testing and benchmarking."""
    dumpfn, _ = require_monty()

    if output_dir is None:
        output_path = Path(tempfile.mkdtemp(prefix="usif_mp_structures_"))
    else:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

    stats: Dict[str, Any] = {
        "total_downloaded": 0,
        "total_skipped": 0,
        "total_filtered": 0,
        "groups": {},
        "output_dir": str(output_path),
    }

    with MaterialsProjectClient(api_key) as client:
        for group_idx, query in enumerate(QUERY_GROUPS, start=1):
            if stats["total_downloaded"] >= total_entries:
                break

            logger.info("Group %s/%s: %s", group_idx, len(QUERY_GROUPS), query)
            search_kwargs = build_search_kwargs(query, min_band_gap, max_band_gap)

            try:
                docs = list(client.search_summary(search_kwargs, SUMMARY_FIELDS))
                logger.info("  Found %s materials", len(docs))
            except Exception as e:
                logger.error("  Error querying group %s: %s", group_idx, e)
                continue

            group_docs = []
            for doc in docs:
                if stats["total_downloaded"] >= total_entries:
                    break
                if not _passes_quality_filters(doc, e_above_hull_max):
                    if getattr(doc, "structure", None) is None:
                        stats["total_skipped"] += 1
                    else:
                        stats["total_filtered"] += 1
                    continue

                group_docs.append(doc)
                stats["total_downloaded"] += 1
                if len(group_docs) >= entries_per_group:
                    break

            if group_docs:
                group_dir = output_path / f"group_{group_idx:02d}"
                group_dir.mkdir(parents=True, exist_ok=True)
                output_file = group_dir / "materials.json"
                dumpfn(group_docs, str(output_file))
                group_key = f"group_{group_idx:02d}"
                stats["groups"][group_key] = len(group_docs)
                logger.info("  Saved %s materials to %s", len(group_docs), output_file)
            else:
                logger.info("  No materials passed filters, skipped")

            if group_idx < len(QUERY_GROUPS):
                time.sleep(rate_limit)

    metadata = {
        "download_stats": stats,
        "output_directory": str(output_path),
        "total_groups": len(stats["groups"]),
        "fields_included": SUMMARY_FIELDS,
    }
    dumpfn(metadata, str(output_path / "metadata.json"))

    if create_zip and stats["total_downloaded"] > 0:
        zip_file = create_mp_data_archive(output_path)
        stats["zip_file"] = str(zip_file)
        logger.info("Created zip archive: %s", zip_file)

    return stats
