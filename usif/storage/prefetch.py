"""Cache prefetch and parallel batch-read helpers for USIF containers."""

from __future__ import annotations

import logging
import queue
import threading
from typing import List, Optional

from usif.structures.structure import USIFStructure

logger = logging.getLogger(__name__)


class PrefetchMixin:
    """Background prefetch and parallel read helpers."""

    def _start_prefetch_thread(self) -> None:
        """Start background thread for prefetching"""

        def prefetch_worker():
            while True:
                try:
                    hashes = self._prefetch_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                try:
                    if hashes is None:
                        break
                    for h in hashes:
                        if not self._cache.contains(h):
                            self.get(h)
                except Exception as e:
                    logger.error(f"Prefetch error: {e}")
                finally:
                    self._prefetch_queue.task_done()

        self._prefetch_thread = threading.Thread(target=prefetch_worker, daemon=True)
        self._prefetch_thread.start()

    def prefetch(self, identifiers: List[str]) -> None:
        """
        Prefetch structures for faster access

        Queues structures for background loading to improve subsequent access
        performance. Useful when you know which structures will be accessed next.

        Args:
            identifiers: List of structure identifiers (hashes or names) to prefetch

        Example:
            >>> container.prefetch(["NaCl_001", "NaCl_002", "NaCl_003"])
            >>> # Structures will be loaded in background
        """
        if self._prefetch_queue:
            self._prefetch_queue.put(identifiers)

    def get_batch_parallel(
        self, identifiers: List[str]
    ) -> List[Optional[USIFStructure]]:
        """
        Batch read using multiple threads (optimized)

        Retrieves multiple structures in parallel using thread pool execution.
        Much faster than sequential get() calls for large batches.

        Args:
            identifiers: List of structure identifiers (hashes or names)

        Returns:
            List[Optional[USIFStructure]]: List of structures in same order as identifiers
            (None for structures that couldn't be loaded)

        Example:
            >>> identifiers = ["NaCl_001", "NaCl_002", "NaCl_003"]
            >>> structures = container.get_batch_parallel(identifiers)
            >>> for ident, struct in zip(identifiers, structures):
            ...     if struct:
            ...         print(f"{ident}: {struct.formula}")
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not identifiers:
            return []

        results = [None] * len(identifiers)

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_request = {
                executor.submit(self.get, ident): (idx, ident)
                for idx, ident in enumerate(identifiers)
            }

            for future in as_completed(future_to_request):
                idx, ident = future_to_request[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Failed to get structure {ident}: {e}")
                    results[idx] = None

        return results
