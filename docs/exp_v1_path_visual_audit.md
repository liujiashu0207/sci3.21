# Path Comparison Visual Audit — exp_v1 (supercover_strict)

## LOS Implementation

- **los_mode**: supercover_strict
- **Implementation**: `supercover_cells(p1, p2)` returns ALL grid cells the continuous line segment passes through. On diagonal crossings (including boundary cases where `e2 == -dy` or `e2 == dx`, i.e. the line passes exactly through a cell corner), both orthogonal neighbor cells AND the diagonal cell are added. This is the most conservative treatment possible.
- **Validation**: `line_of_sight(grid, p1, p2)` returns True only if every cell in `supercover_cells(p1, p2)` is free and within bounds.
- **Consistency**: Same anti-tunneling logic as `neighbors8()` (OnlyWhenNoObstacles).

## Before / After Fix — Invalid Segment Count

| Phase | LOS Version | Boundary Condition | 20×20 Ours invalid segs | 40×40 Ours invalid segs |
|-------|-------------|-------------------|------------------------|------------------------|
| Before (commit 313389f) | Bresenham basic | `e2 > -dy and e2 < dx` (strict inequality) | 4 of 5 segments | not tested |
| Middle (commit ecbb6c1) | Bresenham improved | `e2 > -dy and e2 < dx` (strict, + orthogonal check) | 0 | 0 |
| **Current (this commit)** | **supercover_strict** | `e2 >= -dy and e2 <= dx` (inclusive, covers corner-touch) | **0** | **0** |

Key change from "improved" to "strict": boundary conditions changed from `>` / `<` to `>=` / `<=`, ensuring lines that pass exactly through a cell corner are treated as diagonal crossings. This closes the last theoretical loophole.

## Unit Test Coverage

| Test Class | Tests | Status |
|-----------|-------|--------|
| TestLosCornerTouchCases | 13 | ALL PASS |
| TestSupercoverCellsConsistency | 8 | ALL PASS |
| TestLosVsReference (200 random grids) | 1 | PASS (0 mismatches) |
| TestSmoothingPreservesLegality (50 random grids) | 3 | ALL PASS |
| **Total** | **25** | **25/25 PASS** |

Notably:
- **TestLosVsReference**: Our LOS is compared against a geometric reference (Liang-Barsky segment-AABB intersection). In 200 random tests, our result is AT LEAST as conservative as the geometric reference in every case.
- **TestSmoothingPreservesLegality**: Verified that `simplify_path` + `smooth_corners` never produce an illegal segment on 50 random grids.

## Legality Recheck Results

File: `results/exp_v1_path_legality_recheck.csv`

| Scope | Samples | Invalid Segments | Result |
|-------|---------|-----------------|--------|
| 20x20 demo, 6 algorithms | 6 paths | 0 | ALL LEGAL |
| 40x40 demo, 6 algorithms | 6 paths | 0 | ALL LEGAL |
| MovingAI 5 maps x 5 tasks x 2 smoothed algos | 50 paths | 0 | ALL LEGAL |
| **Total** | **62 paths** | **0** | **ALL LEGAL** |

Additionally: Octile A* optimality verified 30/30 on arena2.map (supercover LOS does not affect search, only smoothing).

## Published Figures (all regenerated with supercover_strict)

| Figure | Source | Legal |
|--------|--------|-------|
| exp_v1_demo_20x20_panel.png | 6 algos x 20x20 demo grid | LEGAL |
| exp_v1_demo_20x20_overlay.png | Euclidean vs Ours x 20x20 | LEGAL |
| exp_v1_demo_40x40_panel.png | 6 algos x 40x40 demo grid | LEGAL |
| exp_v1_demo_40x40_overlay.png | Euclidean vs Ours x 40x40 | LEGAL |

## Caption Template

> 图X 不同算法在同一场景下的路径对比。黑色区域为障碍物，绿色圆点为起点，红色星标为终点。改进算法(红色)在保持路径合法性的前提下，拐点更少、路径更平滑。所有路径均经过严格超覆盖(supercover)逐段碰撞检测验证，确保连续直线段不穿越任何障碍格。
