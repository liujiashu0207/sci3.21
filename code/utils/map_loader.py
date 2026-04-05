from pathlib import Path
from typing import List, Tuple

import numpy as np


def load_grid_map(path: Path) -> np.ndarray:
    """
    Load occupancy grid where:
    - 0 means free
    - 1 means obstacle

    Supported:
    - MovingAI .map
    - .txt/.csv with numeric 0/1
    """
    suffix = path.suffix.lower()
    if suffix == ".map":
        return _load_movingai_map(path)
    if suffix in {".txt", ".csv"}:
        return _load_numeric_grid(path)
    raise ValueError(f"Unsupported map format: {path}")


def list_supported_maps(map_dir: Path) -> List[Path]:
    files: List[Path] = []
    for ext in ("*.map", "*.txt", "*.csv"):
        files.extend(sorted(map_dir.rglob(ext)))
    return files


def _load_numeric_grid(path: Path) -> np.ndarray:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Empty map file: {path}")
    rows: List[List[int]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Support comma or whitespace separators.
        if "," in line:
            parts = [x.strip() for x in line.split(",")]
        else:
            parts = [x.strip() for x in line.split()]
        row = [int(x) for x in parts]
        rows.append(row)
    grid = np.array(rows, dtype=np.int8)
    if grid.ndim != 2:
        raise ValueError(f"Invalid grid shape in: {path}")
    return grid


def _load_movingai_map(path: Path) -> np.ndarray:
    """
    MovingAI chars:
    - '.' or 'G' or 'S' => free
    - '@' or 'T' or 'O' or 'W' => blocked
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        map_idx = next(i for i, x in enumerate(lines) if x.strip().lower() == "map")
    except StopIteration as e:
        raise ValueError(f"Invalid .map (missing 'map' header): {path}") from e

    grid_lines = [x.rstrip("\n") for x in lines[map_idx + 1 :] if x.strip()]
    if not grid_lines:
        raise ValueError(f"Invalid .map (no map body): {path}")

    h = len(grid_lines)
    w = len(grid_lines[0])
    grid = np.zeros((h, w), dtype=np.int8)
    blocked = {"@", "T", "O", "W"}
    for i, row in enumerate(grid_lines):
        if len(row) != w:
            raise ValueError(f"Inconsistent row width in {path}")
        for j, c in enumerate(row):
            grid[i, j] = 1 if c in blocked else 0
    return grid

