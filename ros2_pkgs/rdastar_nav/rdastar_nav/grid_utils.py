"""
Conversions between nav_msgs/OccupancyGrid and the planner's numpy grid.

Planner grid convention (must match code/planners/core.py):
  - np.int8 array of shape (H, W), value 1 = obstacle, 0 = free
  - a cell is addressed as Point = (row, col)

ROS convention used here:
  - OccupancyGrid data is row-major starting at the map origin (lower-left),
    so we keep row = y cell index, col = x cell index. No vertical flip is
    needed as long as world<->grid conversions below are used consistently.
  - Map origin yaw is assumed to be 0 (true for maps saved by map_saver_cli).
"""

import math
from collections import deque
from typing import List, Optional, Tuple

import numpy as np

Point = Tuple[int, int]


def occupancy_grid_to_planner_grid(
    msg,
    occupied_thresh: int = 65,
    unknown_as_obstacle: bool = True,
) -> np.ndarray:
    """Convert nav_msgs/OccupancyGrid to a binary planner grid (1=obstacle)."""
    h, w = msg.info.height, msg.info.width
    data = np.asarray(msg.data, dtype=np.int16).reshape(h, w)
    grid = np.zeros((h, w), dtype=np.int8)
    grid[data >= occupied_thresh] = 1
    if unknown_as_obstacle:
        grid[data < 0] = 1
    return grid


def inflate_obstacles(grid: np.ndarray, radius_cells: int) -> np.ndarray:
    """
    Binary dilation of obstacles with a disk of the given cell radius.

    Implemented as shift-and-OR over disk offsets (numpy only, no scipy).
    A cell within radius_cells of any obstacle becomes an obstacle, so a
    point-robot plan on the inflated grid keeps the real robot collision-free.
    """
    if radius_cells <= 0:
        return grid.copy()
    obs = grid == 1
    out = obs.copy()
    h, w = obs.shape
    r = radius_cells
    for dr in range(-r, r + 1):
        for dc in range(-r, r + 1):
            if dr == 0 and dc == 0:
                continue
            if dr * dr + dc * dc > r * r:
                continue
            src_r0, src_r1 = max(0, -dr), min(h, h - dr)
            src_c0, src_c1 = max(0, -dc), min(w, w - dc)
            dst_r0, dst_r1 = max(0, dr), min(h, h + dr)
            dst_c0, dst_c1 = max(0, dc), min(w, w + dc)
            out[dst_r0:dst_r1, dst_c0:dst_c1] |= obs[src_r0:src_r1, src_c0:src_c1]
    return out.astype(np.int8)


def world_to_cell(wx: float, wy: float, map_info) -> Point:
    """World coordinates (map frame) -> (row, col) cell."""
    res = map_info.resolution
    col = int(math.floor((wx - map_info.origin.position.x) / res))
    row = int(math.floor((wy - map_info.origin.position.y) / res))
    return (row, col)


def cell_to_world(cell: Point, map_info) -> Tuple[float, float]:
    """(row, col) cell -> world coordinates of the cell center (map frame)."""
    res = map_info.resolution
    row, col = cell
    wx = map_info.origin.position.x + (col + 0.5) * res
    wy = map_info.origin.position.y + (row + 0.5) * res
    return (wx, wy)


def in_bounds(grid: np.ndarray, cell: Point) -> bool:
    return 0 <= cell[0] < grid.shape[0] and 0 <= cell[1] < grid.shape[1]


def nearest_free_cell(
    grid: np.ndarray,
    cell: Point,
    max_radius_cells: int,
    passable: Optional[np.ndarray] = None,
) -> Optional[Point]:
    """
    BFS for the free cell nearest to `cell` (Euclidean-nearest among the
    first BFS depth that contains free cells).

    Needed because after inflation the robot's own cell can fall inside the
    inflated band when it stands close to a wall.

    `passable` (bool array, optional): cells the BFS may expand *through*.
    Pass the raw (un-inflated) free-space mask so the search can cross the
    inflation band but never a real wall — otherwise a goal clicked against
    a thin wall could snap to the far side and the plan would enter the
    wrong room. Returns None if no free cell is reachable within
    max_radius_cells.
    """
    if not in_bounds(grid, cell):
        return None
    if grid[cell[0], cell[1]] == 0:
        return cell
    h, w = grid.shape
    visited = {cell}
    q = deque([(cell, 0)])
    best: Optional[Point] = None
    best_d2 = float("inf")
    found_depth = None
    while q:
        (r, c), d = q.popleft()
        if found_depth is not None and d > found_depth:
            break  # every free cell at the minimal depth has been collected
        if d >= max_radius_cells:
            continue
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            nb = (r + dr, c + dc)
            if nb in visited or not (0 <= nb[0] < h and 0 <= nb[1] < w):
                continue
            visited.add(nb)
            if grid[nb[0], nb[1]] == 0:
                found_depth = d
                d2 = (nb[0] - cell[0]) ** 2 + (nb[1] - cell[1]) ** 2
                if d2 < best_d2:
                    best, best_d2 = nb, d2
            elif passable is None or passable[nb[0], nb[1]]:
                q.append((nb, d + 1))
    return best


def densify_polyline(
    points: List[Tuple[float, float]], step: float
) -> List[Tuple[float, float]]:
    """
    Insert intermediate points so consecutive waypoints are at most `step`
    apart. Nav2 controllers prune the plan by distance, so a plan whose
    vertices are meters apart (typical after line-of-sight simplification)
    must be densified before being sent as FollowPath.
    """
    if len(points) < 2:
        return list(points)
    out = [points[0]]
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        seg = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil(seg / step)))
        for k in range(1, n + 1):
            t = k / n
            out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out
