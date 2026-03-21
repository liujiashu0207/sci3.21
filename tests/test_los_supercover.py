"""
Unit tests for supercover line-of-sight and smoothing legality.

Run: python -m pytest tests/test_los_supercover.py -v
"""
import sys
import math
import random
from pathlib import Path

import numpy as np
import pytest

# Project imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from planners.core import (
    line_of_sight,
    supercover_cells,
    neighbors8,
    simplify_path,
    smooth_corners,
    octile_distance,
    reconstruct_path,
    path_length,
    turn_count,
)


# =========================================================================
# A. Corner-touch / boundary cases
# =========================================================================

class TestLosCornerTouchCases:
    """Test that boundary-slope lines (e2 == -dy or e2 == dx) are caught."""

    def _grid_with_obstacle(self, size, obstacles):
        grid = np.zeros((size, size), dtype=int)
        for r, c in obstacles:
            grid[r, c] = 1
        return grid

    def test_exact_diagonal_corner_touch(self):
        """Line from (0,0) to (2,2) passes through cell corner at (1,1).
        If (1,0) or (0,1) is obstacle, must return False."""
        grid = self._grid_with_obstacle(5, [(1, 0)])
        assert line_of_sight(grid, (0, 0), (2, 2)) is False

    def test_exact_diagonal_corner_touch_other_side(self):
        grid = self._grid_with_obstacle(5, [(0, 1)])
        assert line_of_sight(grid, (0, 0), (2, 2)) is False

    def test_exact_diagonal_free(self):
        """If both orthogonal neighbors are free, diagonal should pass."""
        grid = np.zeros((5, 5), dtype=int)
        assert line_of_sight(grid, (0, 0), (4, 4)) is True

    def test_slope_2_1_corner_hit(self):
        """Line (0,0)->(2,1): slope triggers e2 boundary at some step.
        Obstacle at (1,0) should block because line grazes it."""
        grid = self._grid_with_obstacle(5, [(1, 0)])
        # The supercover of (0,0)->(2,1) must include (1,0)
        cells = supercover_cells((0, 0), (2, 1))
        assert (1, 0) in cells
        assert line_of_sight(grid, (0, 0), (2, 1)) is False

    def test_slope_1_2_corner_hit(self):
        """Line (0,0)->(1,2): obstacle at (0,1) should block."""
        grid = self._grid_with_obstacle(5, [(0, 1)])
        cells = supercover_cells((0, 0), (1, 2))
        assert (0, 1) in cells
        assert line_of_sight(grid, (0, 0), (1, 2)) is False

    def test_horizontal_line(self):
        grid = np.zeros((5, 10), dtype=int)
        grid[2, 5] = 1
        assert line_of_sight(grid, (2, 0), (2, 9)) is False
        grid[2, 5] = 0
        assert line_of_sight(grid, (2, 0), (2, 9)) is True

    def test_vertical_line(self):
        grid = np.zeros((10, 5), dtype=int)
        grid[4, 2] = 1
        assert line_of_sight(grid, (0, 2), (9, 2)) is False
        grid[4, 2] = 0
        assert line_of_sight(grid, (0, 2), (9, 2)) is True

    def test_same_point(self):
        grid = np.zeros((5, 5), dtype=int)
        assert line_of_sight(grid, (2, 2), (2, 2)) is True
        grid[2, 2] = 1
        assert line_of_sight(grid, (2, 2), (2, 2)) is False

    def test_adjacent_diagonal_with_wall(self):
        """Single diagonal step (0,0)->(1,1) with wall at (0,1) must fail."""
        grid = self._grid_with_obstacle(3, [(0, 1)])
        assert line_of_sight(grid, (0, 0), (1, 1)) is False

    def test_adjacent_diagonal_with_wall_other(self):
        grid = self._grid_with_obstacle(3, [(1, 0)])
        assert line_of_sight(grid, (0, 0), (1, 1)) is False

    def test_adjacent_diagonal_free(self):
        grid = np.zeros((3, 3), dtype=int)
        assert line_of_sight(grid, (0, 0), (1, 1)) is True

    def test_long_diagonal_wall_at_midpoint(self):
        """(0,0)->(6,6): obstacle at (3,3) directly on path."""
        grid = self._grid_with_obstacle(8, [(3, 3)])
        assert line_of_sight(grid, (0, 0), (6, 6)) is False

    def test_reverse_direction_same_result(self):
        """LOS must be symmetric: p1->p2 == p2->p1."""
        grid = self._grid_with_obstacle(10, [(3, 5)])
        fwd = line_of_sight(grid, (0, 0), (6, 9))
        rev = line_of_sight(grid, (6, 9), (0, 0))
        assert fwd == rev


# =========================================================================
# B. supercover_cells consistency
# =========================================================================

class TestSupercoverCellsConsistency:

    def test_endpoints_included(self):
        cells = supercover_cells((2, 3), (7, 9))
        assert cells[0] == (2, 3)
        assert cells[-1] == (7, 9)

    def test_same_point(self):
        cells = supercover_cells((4, 4), (4, 4))
        assert cells == [(4, 4)]

    def test_horizontal(self):
        cells = supercover_cells((3, 1), (3, 6))
        # Must visit every column: (3,1),(3,2),(3,3),(3,4),(3,5),(3,6)
        for c in range(1, 7):
            assert (3, c) in cells

    def test_vertical(self):
        cells = supercover_cells((1, 5), (6, 5))
        for r in range(1, 7):
            assert (r, 5) in cells

    def test_diagonal_covers_orthogonals(self):
        """Diagonal (0,0)->(3,3) must include orthogonal neighbors at each step."""
        cells = supercover_cells((0, 0), (3, 3))
        # At step from (0,0) to (1,1), cells (1,0) and (0,1) must be present
        assert (1, 0) in cells
        assert (0, 1) in cells

    def test_no_duplicates_in_unique_cells(self):
        """There may be duplicates in raw output but unique set should be valid."""
        cells = supercover_cells((0, 0), (5, 8))
        unique = set(cells)
        # No negative coordinates
        for r, c in unique:
            assert r >= 0 and c >= 0

    def test_connectivity(self):
        """Each consecutive pair in the primary path should be ≤√2 apart."""
        cells = supercover_cells((0, 0), (7, 11))
        # Remove duplicate orthogonal expansions — check main path connectivity
        # The unique cells form a connected region (every cell touches at least one other)
        unique = set(cells)
        for (r, c) in unique:
            if (r, c) == cells[0]:
                continue
            # Must have at least one 8-neighbor in the set
            has_neighbor = any(
                (r + dr, c + dc) in unique
                for dr in [-1, 0, 1] for dc in [-1, 0, 1]
                if (dr, dc) != (0, 0)
            )
            assert has_neighbor, f"Cell ({r},{c}) isolated in supercover"

    def test_supercover_is_superset_of_bresenham(self):
        """Supercover must contain at least all cells basic Bresenham visits."""
        # Simple Bresenham
        def bresenham(p1, p2):
            x0, y0 = p1; x1, y1 = p2
            dx = abs(x1-x0); dy = abs(y1-y0)
            sx = 1 if x0<x1 else -1; sy = 1 if y0<y1 else -1
            err = dx - dy; cells = []
            while True:
                cells.append((x0, y0))
                if (x0, y0) == (x1, y1): break
                e2 = 2*err
                if e2 > -dy: err -= dy; x0 += sx
                if e2 < dx: err += dx; y0 += sy
            return cells

        for _ in range(100):
            p1 = (random.randint(0, 20), random.randint(0, 20))
            p2 = (random.randint(0, 20), random.randint(0, 20))
            bres = set(bresenham(p1, p2))
            sc = set(supercover_cells(p1, p2))
            assert bres.issubset(sc), f"Bresenham cell not in supercover: {bres - sc}"


# =========================================================================
# C. LOS vs reference implementation
# =========================================================================

class TestLosVsReference:
    """Compare our LOS against a conservative reference that checks every cell
    in the bounding box intersected by the line's geometric corridor."""

    @staticmethod
    def _reference_los(grid, p1, p2):
        """
        Conservative reference: for every cell in the bounding box,
        check if the cell rectangle intersects the line segment.
        Uses geometric segment-AABB intersection.
        """
        r0, c0 = p1; r1, c1 = p2
        rmin, rmax = min(r0, r1), max(r0, r1)
        cmin, cmax = min(c0, c1), max(c0, c1)
        h, w = grid.shape

        # Direction vector
        dr, dc = r1 - r0, c1 - c0

        for r in range(max(0, rmin), min(h, rmax + 1)):
            for c in range(max(0, cmin), min(w, cmax + 1)):
                if grid[r, c] == 0:
                    continue
                # Check if line segment from (r0+0.5, c0+0.5) to (r1+0.5, c1+0.5)
                # intersects cell rectangle [c, c+1] x [r, r+1]
                # (using center-of-cell coordinates)
                if TestLosVsReference._segment_intersects_rect(
                    c0 + 0.5, r0 + 0.5, c1 + 0.5, r1 + 0.5,
                    c, r, c + 1, r + 1
                ):
                    return False
        return True

    @staticmethod
    def _segment_intersects_rect(x1, y1, x2, y2, rx, ry, rx2, ry2):
        """Check if line segment (x1,y1)-(x2,y2) intersects rectangle [rx,ry,rx2,ry2]."""
        # Liang-Barsky clipping
        dx = x2 - x1
        dy = y2 - y1
        p = [-dx, dx, -dy, dy]
        q = [x1 - rx, rx2 - x1, y1 - ry, ry2 - y1]
        t0, t1 = 0.0, 1.0

        for pi, qi in zip(p, q):
            if abs(pi) < 1e-12:
                if qi < -1e-12:
                    return False
            else:
                t = qi / pi
                if pi < 0:
                    t0 = max(t0, t)
                else:
                    t1 = min(t1, t)
                if t0 > t1 + 1e-12:
                    return False
        return t0 <= t1 + 1e-12

    def test_random_grids(self):
        """Test 200 random (grid, p1, p2) pairs: our LOS must be at least as
        conservative as the geometric reference."""
        rng = random.Random(42)
        mismatches = []
        for _ in range(200):
            size = rng.randint(5, 15)
            grid = np.zeros((size, size), dtype=int)
            # Random obstacles
            for r in range(size):
                for c in range(size):
                    if rng.random() < 0.25:
                        grid[r, c] = 1
            p1 = (rng.randint(0, size-1), rng.randint(0, size-1))
            p2 = (rng.randint(0, size-1), rng.randint(0, size-1))

            # Skip if start/end on obstacle
            if grid[p1[0], p1[1]] == 1 or grid[p2[0], p2[1]] == 1:
                continue

            ours = line_of_sight(grid, p1, p2)
            ref = self._reference_los(grid, p1, p2)

            # Our result must be AT LEAST as conservative as reference.
            # If reference says blocked, ours must also say blocked.
            if ref is False and ours is True:
                mismatches.append((p1, p2, "ours=True but ref=False"))

        assert len(mismatches) == 0, f"{len(mismatches)} cases where ours is less conservative than reference: {mismatches[:5]}"


# =========================================================================
# D. Smoothing preserves legality
# =========================================================================

class TestSmoothingPreservesLegality:

    @staticmethod
    def _make_grid_with_corridor():
        """10x10 grid with a horizontal wall and gap."""
        grid = np.zeros((10, 10), dtype=int)
        for c in range(10):
            grid[5, c] = 1
        grid[5, 3] = 0  # gap
        return grid

    @staticmethod
    def _run_astar(grid, start, goal):
        """Minimal A* for testing."""
        import heapq
        open_heap = [(octile_distance(start, goal), start)]
        came_from = {}
        g_score = {start: 0.0}
        closed = set()
        while open_heap:
            _, cur = heapq.heappop(open_heap)
            if cur in closed:
                continue
            closed.add(cur)
            if cur == goal:
                return reconstruct_path(came_from, cur)
            for nb, cost in neighbors8(grid, cur):
                if nb in closed:
                    continue
                tg = g_score[cur] + cost
                if tg < g_score.get(nb, float("inf")):
                    came_from[nb] = cur
                    g_score[nb] = tg
                    heapq.heappush(open_heap, (tg + octile_distance(nb, goal), nb))
        return []

    def test_simplify_preserves_los(self):
        grid = self._make_grid_with_corridor()
        path = self._run_astar(grid, (0, 0), (9, 9))
        assert len(path) > 0
        simplified = simplify_path(path, grid)
        for i in range(1, len(simplified)):
            assert line_of_sight(grid, simplified[i-1], simplified[i]), \
                f"simplify_path produced invalid segment {simplified[i-1]}->{simplified[i]}"

    def test_smooth_corners_preserves_los(self):
        grid = self._make_grid_with_corridor()
        path = self._run_astar(grid, (0, 0), (9, 9))
        simplified = simplify_path(path, grid)
        smoothed = smooth_corners(simplified, grid)
        for p in smoothed:
            assert grid[p[0], p[1]] == 0, f"Smoothed point {p} on obstacle!"
        for i in range(1, len(smoothed)):
            assert line_of_sight(grid, smoothed[i-1], smoothed[i]), \
                f"smooth_corners produced invalid segment {smoothed[i-1]}->{smoothed[i]}"

    def test_full_pipeline_random_grids(self):
        """Run simplify+smooth on 50 random grids and verify all segments legal."""
        rng = random.Random(123)
        failures = []
        for trial in range(50):
            size = rng.randint(8, 20)
            grid = np.zeros((size, size), dtype=int)
            for r in range(size):
                for c in range(size):
                    if rng.random() < 0.2:
                        grid[r, c] = 1
            # Random start/goal
            free = [(r, c) for r in range(size) for c in range(size) if grid[r, c] == 0]
            if len(free) < 2:
                continue
            start, goal = rng.sample(free, 2)
            path = self._run_astar(grid, start, goal)
            if len(path) < 2:
                continue
            p1 = simplify_path(path, grid)
            p2 = smooth_corners(p1, grid)
            for i in range(1, len(p2)):
                if not line_of_sight(grid, p2[i-1], p2[i]):
                    failures.append((trial, p2[i-1], p2[i]))
                    break
        assert len(failures) == 0, f"{len(failures)} trials with illegal smoothed segments: {failures[:5]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
