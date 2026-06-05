"""Materials Project API client wrapper."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Sequence

from .dependencies import require_mp_rester


class MaterialsProjectClient:
    """Small context-manager wrapper around ``mp_api.client.MPRester``."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._context = None
        self._client = None

    def __enter__(self) -> "MaterialsProjectClient":
        MPRester = require_mp_rester()
        self._context = MPRester(self.api_key)
        self._client = self._context.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            self._context.__exit__(exc_type, exc, tb)
        self._context = None
        self._client = None

    def search_summary(self, search_kwargs: Dict[str, Any], fields: Sequence[str]) -> Iterable[Any]:
        """Yield summary documents for a prepared MP query."""
        if self._client is None:
            raise RuntimeError("MaterialsProjectClient must be used as a context manager")
        return self._client.materials.summary.search(
            **search_kwargs,
            fields=list(fields),
            num_chunks=None,
            chunk_size=1000,
        )
