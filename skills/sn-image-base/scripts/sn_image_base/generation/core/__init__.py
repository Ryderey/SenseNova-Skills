from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path


def ensure_output_path(path: Path) -> Path:
    """Ensure the parent directory of the given path exists.

    Args:
        path (Path):
            The file path whose parent directory should be created.

    Returns:
        Path:
            The original path unchanged.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def unique_output_path(directory: Path, prefix: str, suffix: str) -> Path:
    """Return a collision-resistant default output path."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{suffix}"
