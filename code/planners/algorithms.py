"""
Path planning algorithms for the Residual-Driven Adaptive Weighted A* paper.

Algorithm lineup (7 configurations):
  1. Dijkstra                — h=0 baseline
  2. A*(Euclidean)           — euclidean heuristic, α=1.0, no smoothing
  3. A*(Octile)              — octile heuristic, α=1.0, no smoothing
  4. Weighted A*(α=1.2)      — octile, fixed α=1.2, no smoothing
  5. Improved A*(ours)       — octile, residual-driven α(n), two-stage smoothing
  6. Ablation: no adaptive   — octile, α=1.0, two-stage smoothing
  7. Ablation: no smoothing  — octile, residual-driven α(n), no smoothing

Core formula:
  f(n) = g(n) + α(n) × h_oct(n)
  α(n) = 1 + β × (1 − ρ_local(n))
"""

import heapq
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from .core import (
    Point,
    euclidean_distance,
    fast_local_obs,
    line_of_sight,
    make_integral_image,
    neighbors8,
    obstacle_ratio,
    octile_distance,
    path_length,
    reconstruct_path,
    simplify_path,
    smooth_corners,
    turn_count,
)


# ---------------------------------------------------------------------------
# Unified A* search engine
# ---------------------------------------------------------------------------

def astar_search(
    grid: np.ndarray,
    start: Point,
    goal: Point,
    heuristic_mode: str = "octile",
    weight: float = 1.0,
    use_residual_alpha: bool = False,
    beta: float = 0.3,
    integral: np.ndarray = None,
    radius: int = 5,
) -> Dict[str, object]:
    """
    Unified A* search supporting multiple heuristic and weight modes.

    heuristic_mode: "zero" (Dijkstra), "euclidean", "octile"
    weight: constant weight multiplier (used when use_residual_alpha=False)
    use_residual_alpha: if True, use α(n) = 1 + beta * (1 - ρ_local(n))
    """
    t0 = time.perf_counter()
    h_map, w_map = grid.shape

    # Heuristic function selection
    if heuristic_mode == "zero":
        h_func = lambda n: 0.0
    elif heuristic_mode == "euclidean":
        h_func = lambda n: euclidean_distance(n, goal)
    else:  # octile
        h_func = lambda n: octile_distance(n, goal)

    # Weight function
    if use_residual_alpha and integral is not None:
        def w_func(n):
            rho = fast_local_obs(integral, n[0], n[1], h_map, w_map, radius)
            return 1.0 + beta * (1.0 - rho)
    else:
        def w_func(n):
            return weight

    # A* main loop
    start_f = w_func(start) * h_func(start)
    open_heap: List[Tuple[float, Point]] = [(start_f, start)]
    came_from: Dict[Point, Point] = {}
    g_score: Dict[Point, float] = {start: 0.0}
    closed = set()
    expanded = 0

    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)
        expanded += 1

        if current == goal:
            path = reconstruct_path(came_from, current)
            return {
                "success": True,
                "path": path,
                "path_length": path_length(path),
                "turn_count": turn_count(path),
                "expanded_nodes": expanded,
                "runtime_ms": (time.perf_counter() - t0) * 1000.0,
            }

        for nb, move_cost in neighbors8(grid, current):
            if nb in closed:
                continue
            tentative_g = g_score[current] + move_cost
            if tentative_g < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative_g
                f = tentative_g + w_func(nb) * h_func(nb)
                heapq.heappush(open_heap, (f, nb))

    return {
        "success": False,
        "path": [],
        "path_length": float("inf"),
        "turn_count": 0,
        "expanded_nodes": expanded,
        "runtime_ms": (time.perf_counter() - t0) * 1000.0,
    }


# ---------------------------------------------------------------------------
# Public algorithm functions
# ---------------------------------------------------------------------------

def dijkstra_search(grid: np.ndarray, start: Point, goal: Point) -> Dict:
    """Dijkstra: h=0, no heuristic."""
    return astar_search(grid, start, goal, heuristic_mode="zero")


def euclidean_astar(grid: np.ndarray, start: Point, goal: Point) -> Dict:
    """Traditional A* with euclidean heuristic (baseline)."""
    return astar_search(grid, start, goal, heuristic_mode="euclidean")


def octile_astar(grid: np.ndarray, start: Point, goal: Point) -> Dict:
    """A* with octile heuristic, α=1.0."""
    return astar_search(grid, start, goal, heuristic_mode="octile")


def weighted_astar(grid: np.ndarray, start: Point, goal: Point,
                   weight: float = 1.2) -> Dict:
    """Weighted A* with fixed α, octile heuristic."""
    return astar_search(grid, start, goal, heuristic_mode="octile", weight=weight)


def residual_astar(
    grid: np.ndarray,
    start: Point,
    goal: Point,
    beta: float = 0.3,
    radius: int = 5,
    use_smoothing: bool = True,
    precomputed_integral: np.ndarray = None,
) -> Dict:
    """
    Residual-Driven Adaptive Weighted A* (our method).

    f(n) = g(n) + α(n) × h_oct(n)
    α(n) = 1 + β × (1 − ρ_local(n))

    With optional two-stage path smoothing.
    """
    integral = precomputed_integral if precomputed_integral is not None \
               else make_integral_image(grid)

    res = astar_search(
        grid, start, goal,
        heuristic_mode="octile",
        use_residual_alpha=True,
        beta=beta,
        integral=integral,
        radius=radius,
    )

    if not res["success"] or not use_smoothing:
        return res

    # Two-stage smoothing
    p0 = res["path"]
    p1 = simplify_path(p0, grid)
    p2 = smooth_corners(p1, grid)
    res["path"] = p2
    res["path_length"] = path_length(p2)
    res["turn_count"] = turn_count(p2)
    return res


def ablation_no_adaptive(
    grid: np.ndarray, start: Point, goal: Point
) -> Dict:
    """Ablation: α=1.0 (no adaptive weight), with smoothing."""
    res = astar_search(grid, start, goal, heuristic_mode="octile", weight=1.0)

    if not res["success"]:
        return res

    p0 = res["path"]
    p1 = simplify_path(p0, grid)
    p2 = smooth_corners(p1, grid)
    res["path"] = p2
    res["path_length"] = path_length(p2)
    res["turn_count"] = turn_count(p2)
    return res


def ablation_no_smoothing(
    grid: np.ndarray,
    start: Point,
    goal: Point,
    beta: float = 0.3,
    radius: int = 5,
    precomputed_integral: np.ndarray = None,
) -> Dict:
    """Ablation: residual-driven α(n) but NO smoothing."""
    return residual_astar(
        grid, start, goal,
        beta=beta, radius=radius,
        use_smoothing=False,
        precomputed_integral=precomputed_integral,
    )
