# Experiment Protocol Lock (v3)

- Protocol-Version: EXP-v3.0-dual-track
- Code-Commit: 20593ad
- Data-Snapshot: MovingAI 15 maps (DAO×5 + Street×5 + WC3×5)
- Diagonal-Rule: OnlyWhenNoObstacles (AND logic)
- LOS-Mode: strict supercover (>=/<= boundary, 25 unit tests)
- Script: code/experiments/run_experiment.py

## Maps (15)

| # | Type | Map | Size | Obs% |
|---|------|-----|------|------|
| 1 | DAO | brc503d | 257×320 | 18.1% |
| 2 | DAO | orz100d | 395×412 | 38.8% |
| 3 | DAO | den502d | 251×211 | 48.6% |
| 4 | DAO | arena2 | 209×281 | 58.6% |
| 5 | DAO | ost003d | 194×194 | 64.9% |
| 6 | Street | Berlin_0_512 | 512×512 | 25.0% |
| 7 | Street | London_0_512 | 512×512 | 25.0% |
| 8 | Street | Moscow_0_512 | 512×512 | 25.0% |
| 9 | Street | Paris_0_512 | 512×512 | 25.0% |
| 10 | Street | Shanghai_0_512 | 512×512 | 25.0% |
| 11 | WC3 | dustwallowkeys | 512×512 | 31.5% |
| 12 | WC3 | blastedlands | 512×512 | 49.9% |
| 13 | WC3 | bloodvenomfalls | 512×512 | 55.7% |
| 14 | WC3 | darkforest | 512×512 | 61.9% |
| 15 | WC3 | battleground | 512×512 | 64.8% |

## Algorithms (7)

| # | Name | Heuristic | Weight | Smoothing |
|---|------|-----------|--------|-----------|
| G1 | dijkstra | h=0 | — | No |
| G2 | astar_euclidean | Euclidean | 1.0 | No |
| G3 | astar_octile | Octile | 1.0 | No |
| G4 | weighted_1.2 | Octile | 1.2 fixed | No |
| G5 | improved_ours | Octile | α(n)=1+0.3(1-ρ) | Two-stage |
| G6 | ablation_no_adapt | Octile | 1.0 | Two-stage |
| G7 | ablation_no_smooth | Octile | α(n)=1+0.3(1-ρ) | No |

All 7 algorithms run on the same task set per experiment.

## β Tuning (isolated)

- Prefix: beta_tuning
- Maps: 15 (all)
- Tasks: 20/map, mode=middle_lo (30%-50% percentile by optimal_length)
- task_source: middle_30_50
- Beta grid: {0.1, 0.2, 0.3, 0.4, 0.5}
- Isolation: zero overlap with main (50-70%) and long (top-20) task sets
- **Final-Beta: 0.3** (EXP reduction +52.2%, PL increase +4.5% < 5% constraint)
- Command: `python code/experiments/run_experiment.py --out-prefix beta_tuning --task-mode middle_lo --tasks-per-map 20 --beta 0.3 --timeout 30`

## Main Experiment

- Prefix: exp_main
- Maps: 15
- Tasks: 20/map, mode=middle (50%-70% percentile by optimal_length, avg PL≈300)
- task_source: middle_50_70
- Algorithms: 7 (all same task set)
- Beta: 0.3 (locked)
- Timeout: 30s per task
- Timeout handling: timeout=True recorded, capped_total_ms=30000, not silently dropped
- Statistics: Wilcoxon (n=15) + BH-FDR + Cohen's d + rank-biserial r
- Comparisons: improved_vs_euclidean, improved_vs_octile, improved_vs_noadapt, improved_vs_nosmooth
- Command: `python code/experiments/run_experiment.py --out-prefix exp_main --task-mode middle --tasks-per-map 20 --beta 0.3 --timeout 30`

## Supplementary Experiment (long paths)

- Prefix: exp_long
- Maps: 15
- Tasks: 20/map, mode=longest (top 20 by optimal_length, avg PL≈500+)
- task_source: longest_top20
- Algorithms: 7
- Beta: 0.3
- Timeout: 30s per task
- Purpose: robustness validation under difficult scenarios
- Conclusions reported separately, not mixed with main
- Command: `python code/experiments/run_experiment.py --out-prefix exp_long --task-mode longest --tasks-per-map 20 --beta 0.3 --timeout 30`

## Time Fields

- preprocess_ms: integral image construction (G5/G7 only, 0 for others)
- search_ms: A* core loop
- postprocess_ms: two-stage smoothing (G5/G6 only, 0 for others)
- total_ms: preprocess + search + postprocess
- capped_total_ms: if timeout=True then 30000, else total_ms

## Raw Record Fields (21)

run_id, map_type, map_name, map_size, obstacle_ratio, task_id, start, goal,
optimal_length, algorithm, success, timeout, path_length, turn_count,
expanded_nodes, preprocess_ms, search_ms, postprocess_ms, total_ms,
capped_total_ms, collision_free

## Task Manifest Fields (9)

map_type, map_name, map_size, obstacle_ratio, task_id, start, goal,
optimal_length, task_source

## Statistics Output Fields (15)

compare_pair, metric, n_pairs, W, p_raw, q_bh, reject_fdr,
cohen_d, rank_biserial_r, wins, ties, losses, base_mean, imp_mean, change_pct
