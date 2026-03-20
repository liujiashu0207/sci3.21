# Reproduction Commands — exp_v1

## Environment
```
Python 3.12.3
numpy 2.4.2, scipy 1.17.0, statsmodels 0.14.6, matplotlib 3.10.8
```

## Full experiment
```bash
cd /path/to/repo
python3 code/experiments/run_experiment.py  # (script to be formalized)
```

## Quick verification (single map)
```python
import sys; sys.path.insert(0, 'code')
from planners.algorithms import *
from planners.core import make_integral_image
from utils.map_loader import load_grid_map
import pathlib

grid = load_grid_map(pathlib.Path('data/benchmark_maps/dao-map/arena2.map'))
integral = make_integral_image(grid)
start, goal = (26, 19), (29, 19)

r = residual_astar(grid, start, goal, beta=0.3, precomputed_integral=integral)
print(r['path_length'], r['expanded_nodes'], r['turn_count'])
```

## Deterministic
All algorithms are deterministic. No random seed needed. Same input = same output.
