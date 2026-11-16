"""Load persisted Materials Project groups."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union

from .dependencies import require_monty


def load_mp_group(group_file: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load a group JSON file produced by ``download_mp_data``."""
    group_path = Path(group_file)
    if not group_path.exists():
        raise FileNotFoundError(f"Group file not found: {group_file}")

    _, loadfn = require_monty()
    return loadfn(str(group_path))
