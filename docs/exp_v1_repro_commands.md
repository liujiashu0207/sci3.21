# Reproduction Commands — exp_v1

## Environment

```
Python 3.12.3
numpy 2.4.2, scipy 1.17.0, statsmodels 0.14.6, matplotlib 3.10.8
```

## Full experiment (short paths, exp_v1)

```bash
# Linux / macOS
python code/experiments/run_experiment.py \
  --tasks-per-map 50 --beta 0.3 --out-prefix exp_v1 --task-mode first

# Windows
python code\experiments\run_experiment.py --tasks-per-map 50 --beta 0.3 --out-prefix exp_v1 --task-mode first
```

## Long-path supplementary (exp_v1_longpath)

```bash
python code/experiments/run_experiment.py \
  --tasks-per-map 5 --beta 0.3 --out-prefix exp_v1_longpath --task-mode longest
```

Note: Dijkstra is included by default but extremely slow on long paths (>7s per task on 1024×1024 maps). The long-path audit was run with Dijkstra excluded via inline script.

## Reproducibility

All algorithms are deterministic. No random seed needed. Same input = same output.
Path length, turn count, and expanded nodes must match exactly across runs.
Runtime is wall-clock and subject to OS scheduling variance (expect <30% fluctuation).

## Quick single-map verification

```python
import sys; sys.path.insert(0, 'code')
from planners.algorithms import residual_astar, octile_astar
from planners.core import make_integral_image
from utils.map_loader import load_grid_map
import pathlib

grid = load_grid_map(pathlib.Path('data/benchmark_maps/dao-map/arena2.map'))
integral = make_integral_image(grid)

r_oct = octile_astar(grid, (26, 19), (29, 19))
r_res = residual_astar(grid, (26, 19), (29, 19), beta=0.3, precomputed_integral=integral)
print(f"Octile: PL={r_oct['path_length']:.4f} EXP={r_oct['expanded_nodes']}")
print(f"Ours:   PL={r_res['path_length']:.4f} EXP={r_res['expanded_nodes']}")
```
