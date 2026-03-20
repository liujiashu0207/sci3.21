# exp_v1 Reproducibility Check

## Commands
```
# Original (within session inline)
# Rerun:
python code/experiments/run_experiment.py --tasks-per-map 50 --beta 0.3 --out-prefix exp_v1_rerun
```

## Key Metrics Comparison

| Algorithm | Metric | Original | Rerun | Match |
|-----------|--------|----------|-------|-------|
| ablation_no_adapt | path_length | 9.6507 | 9.6507 | ✅ exact |
| ablation_no_adapt | turn_count | 0.0560 | 0.0560 | ✅ exact |
| ablation_no_adapt | expanded | 17.9387 | 17.9387 | ✅ exact |
| ablation_no_adapt | runtime_ms | 0.1757 | 0.1669 | ✅ (within 30%) |
| ablation_no_smooth | path_length | 10.1596 | 10.1596 | ✅ exact |
| ablation_no_smooth | turn_count | 1.0013 | 1.0013 | ✅ exact |
| ablation_no_smooth | expanded | 9.9800 | 9.9800 | ✅ exact |
| ablation_no_smooth | runtime_ms | 0.1920 | 0.1911 | ✅ (within 30%) |
| astar_euclidean | path_length | 10.1563 | 10.1563 | ✅ exact |
| astar_euclidean | turn_count | 3.0280 | 3.0280 | ✅ exact |
| astar_euclidean | expanded | 24.4907 | 24.4907 | ✅ exact |
| astar_euclidean | runtime_ms | 0.2162 | 0.2090 | ✅ (within 30%) |
| astar_octile | path_length | 10.1563 | 10.1563 | ✅ exact |
| astar_octile | turn_count | 1.5733 | 1.5733 | ✅ exact |
| astar_octile | expanded | 17.9387 | 17.9387 | ✅ exact |
| astar_octile | runtime_ms | 0.1737 | 0.1695 | ✅ (within 30%) |
| dijkstra | path_length | 10.1563 | 10.1563 | ✅ exact |
| dijkstra | turn_count | 1.4267 | 1.4267 | ✅ exact |
| dijkstra | expanded | 326.0293 | 326.0293 | ✅ exact |
| dijkstra | runtime_ms | 2.3818 | 2.3181 | ✅ (within 30%) |
| improved_ours | path_length | 9.6516 | 9.6516 | ✅ exact |
| improved_ours | turn_count | 0.0573 | 0.0573 | ✅ exact |
| improved_ours | expanded | 9.9800 | 9.9800 | ✅ exact |
| improved_ours | runtime_ms | 0.2254 | 0.1789 | ✅ (within 30%) |
| weighted_1.2 | path_length | 10.1585 | 10.1585 | ✅ exact |
| weighted_1.2 | turn_count | 0.9293 | 0.9293 | ✅ exact |
| weighted_1.2 | expanded | 9.9587 | 9.9587 | ✅ exact |
| weighted_1.2 | runtime_ms | 0.1067 | 0.1072 | ✅ (within 30%) |

## Verdict
**REPRODUCIBLE ✅** — All non-timing metrics exactly match. Runtime variance within acceptable tolerance (deterministic algorithm, timing noise only).

Note: All algorithms are deterministic (no randomness). Path length, turn count, and expanded nodes are integer/exact-float outputs that must match exactly. Runtime is wall-clock and subject to OS scheduling variance.
