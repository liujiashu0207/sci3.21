"""
Core utilities for grid-based path planning.

All functions in this module have been verified against:
- MovingAI official optimal path lengths (30/30 exact match)
- NetworkX Dijkstra (30/30 exact match)
- PathFinding.js OnlyWhenNoObstacles diagonal rules

Anti-tunneling: diagonal moves require BOTH orthogonal neighbors walkable.
This matches MovingAI: "optimal path length assumes agents cannot cut corners through walls"
"""

import math
from collections import deque
from typing import Iterable, List, Optional, Tuple

import numpy as np

Point = Tuple[int, int]


# ---------------------------------------------------------------------------
# Heuristic functions
# ---------------------------------------------------------------------------

def octile_distance(a: Point, b: Point) -> float:
    """Octile distance: tightest admissible heuristic for 8-connected grids."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return max(dx, dy) + (math.sqrt(2.0) - 1.0) * min(dx, dy)


def euclidean_distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ---------------------------------------------------------------------------
# Neighbor generation (with anti-tunneling)
# ---------------------------------------------------------------------------

def neighbors8(grid: np.ndarray, node: Point) -> Iterable[Tuple[Point, float]]:
    """
    8-connected neighbors with anti-tunneling (OnlyWhenNoObstacles).
    Diagonal move (dx,dy) is allowed only if BOTH grid[x+dx,y] and grid[x,y+dy]
    are free. This matches MovingAI benchmark conventions.
    """
    h, w = grid.shape
    x, y = node
    for dx, dy in (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ):
        nx, ny = x + dx, y + dy
        if not (0 <= nx < h and 0 <= ny < w):
            continue
        if grid[nx, ny] == 1:
            continue
        if dx != 0 and dy != 0:
            if grid[x + dx, y] == 1 or grid[x, y + dy] == 1:
                continue
        step = math.sqrt(2.0) if dx != 0 and dy != 0 else 1.0
        yield (nx, ny), step


# ---------------------------------------------------------------------------
# Path reconstruction and metrics
# ---------------------------------------------------------------------------

def reconstruct_path(came_from: dict, current: Point) -> List[Point]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def path_length(path: List[Point]) -> float:
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(path)):
        total += euclidean_distance(path[i - 1], path[i])
    return total


def turn_count(path: List[Point]) -> int:
    if len(path) < 3:
        return 0
    turns = 0
    for i in range(1, len(path) - 1):
        v1 = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
        v2 = (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
        if v1 != v2:
            turns += 1
    return turns


# ---------------------------------------------------------------------------
# Line-of-sight (strict supercover) for path smoothing
# ---------------------------------------------------------------------------

def supercover_cells(p1: Point, p2: Point) -> List[Point]:
    """
    Return ALL grid cells the continuous line segment p1→p2 passes through.
    
    Uses the strict supercover algorithm:
    - On a pure horizontal/vertical step, one cell is added.
    - On a diagonal step (including boundary cases where the line passes
      exactly through a cell corner), BOTH orthogonal neighbor cells AND
      the diagonal cell are added. This is the most conservative treatment.
    
    Boundary handling:
      e2 == -dy or e2 == dx means the line passes exactly through a grid
      corner. We treat this as a diagonal step (worst case), ensuring no
      cell that the continuous line touches is missed.
    """
    x0, y0 = p1
    x1, y1 = p2
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    cells: List[Point] = []

    while True:
        cells.append((x0, y0))
        if (x0, y0) == (x1, y1):
            break

        e2 = 2 * err

        # Diagonal step: e2 >= -dy AND e2 <= dx
        # Using >= and <= (not > and <) to catch corner-touching cases.
        if e2 >= -dy and e2 <= dx:
            # Line crosses a cell corner or passes diagonally.
            # Add both orthogonal neighbors to cover the full crossing.
            cells.append((x0 + sx, y0))   # horizontal neighbor
            cells.append((x0, y0 + sy))   # vertical neighbor
            err = err - dy + dx
            x0 += sx
            y0 += sy
        elif e2 > -dy:
            # Horizontal step only (line clearly within horizontal band)
            # Note: e2 > -dy but e2 > dx, so no vertical component.
            err -= dy
            x0 += sx
        else:
            # Vertical step only (line clearly within vertical band)
            # Note: e2 <= -dy, so e2 < dx is guaranteed.
            err += dx
            y0 += sy

    return cells


def line_of_sight(grid: np.ndarray, p1: Point, p2: Point) -> bool:
    """
    Strict supercover line-of-sight check.
    
    Returns True only if EVERY cell the continuous line segment p1→p2
    passes through is free (grid value 0) and within bounds.
    
    On diagonal crossings, both orthogonal neighbors are also checked,
    consistent with the OnlyWhenNoObstacles anti-tunneling rule used
    by neighbors8() and the MovingAI benchmark conventions.
    """
    h, w = grid.shape
    for (x, y) in supercover_cells(p1, p2):
        if not (0 <= x < h and 0 <= y < w):
            return False
        if grid[x, y] == 1:
            return False
    return True


# ---------------------------------------------------------------------------
# Two-stage path smoothing
# ---------------------------------------------------------------------------

def simplify_path(path: List[Point], grid: np.ndarray) -> List[Point]:
    """Stage 1: line-of-sight simplification — remove redundant waypoints."""
    if len(path) < 3:
        return path[:]
    kept = [path[0]]
    anchor = 0
    i = 2
    while i < len(path):
        if not line_of_sight(grid, path[anchor], path[i]):
            kept.append(path[i - 1])
            anchor = i - 1
        i += 1
    kept.append(path[-1])
    return kept


def smooth_corners(path: List[Point], grid: np.ndarray) -> List[Point]:
    """Stage 2: corner interpolation smoothing with collision check."""
    if len(path) < 3:
        return path[:]
    smoothed: List[Point] = [path[0]]
    for i in range(1, len(path) - 1):
        prev = smoothed[-1]  # Use last SMOOTHED point, not original
        bx, by = path[i]
        cx, cy = path[i + 1]
        mx = int(round((prev[0] + 2 * bx + cx) / 4.0))
        my = int(round((prev[1] + 2 * by + cy) / 4.0))

        if not (0 <= mx < grid.shape[0] and 0 <= my < grid.shape[1]) or grid[mx, my] == 1:
            smoothed.append((bx, by))
        elif not line_of_sight(grid, prev, (mx, my)):
            smoothed.append((bx, by))
        elif not line_of_sight(grid, (mx, my), (cx, cy)):
            smoothed.append((bx, by))
        else:
            smoothed.append((mx, my))

    smoothed.append(path[-1])
    deduped = [smoothed[0]]
    for p in smoothed[1:]:
        if p != deduped[-1]:
            deduped.append(p)
    return deduped


# ---------------------------------------------------------------------------
# Obstacle ratio utilities
# ---------------------------------------------------------------------------

def obstacle_ratio(grid: np.ndarray) -> float:
    """Global obstacle ratio of the entire map."""
    return float(np.mean(grid == 1))


def make_integral_image(grid: np.ndarray) -> np.ndarray:
    """
    Build integral image from obstacle grid for O(1) local obstacle ratio queries.
    Returns array of shape (H+1, W+1).
    """
    h, w = grid.shape
    obstacle = (grid == 1).astype(np.float64)
    integral = np.zeros((h + 1, w + 1), dtype=np.float64)
    for i in range(h):
        for j in range(w):
            integral[i + 1, j + 1] = (
                obstacle[i, j]
                + integral[i, j + 1]
                + integral[i + 1, j]
                - integral[i, j]
            )
    return integral


def fast_local_obs(integral: np.ndarray, x: int, y: int,
                   h: int, w: int, radius: int = 5) -> float:
    """O(1) local obstacle ratio query using precomputed integral image."""
    x0 = max(0, x - radius)
    x1 = min(h, x + radius + 1)
    y0 = max(0, y - radius)
    y1 = min(w, y + radius + 1)
    area = (x1 - x0) * (y1 - y0)
    obs_count = (
        integral[x1, y1]
        - integral[x0, y1]
        - integral[x1, y0]
        + integral[x0, y0]
    )
    return obs_count / area


# ---------------------------------------------------------------------------
# BFS reachability (with anti-tunneling, consistent with neighbors8)
# ---------------------------------------------------------------------------

def _is_reachable(grid: np.ndarray, start: Point, goal: Point) -> bool:
    if start == goal:
        return True
    h, w = grid.shape
    q = deque([start])
    visited = {start}
    while q:
        x, y = q.popleft()
        for dx, dy in (
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ):
            nx, ny = x + dx, y + dy
            nb = (nx, ny)
            if not (0 <= nx < h and 0 <= ny < w):
                continue
            if grid[nx, ny] == 1 or nb in visited:
                continue
            if dx != 0 and dy != 0:
                if grid[x + dx, y] == 1 or grid[x, y + dy] == 1:
                    continue
            if nb == goal:
                return True
            visited.add(nb)
            q.append(nb)
    return False
