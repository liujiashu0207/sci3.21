# Experiment Protocol Lock (v3)

- Protocol-Version: EXP-v3.0-dual-track
- Code-Commit: f3d60a5
- Data-Snapshot: MovingAI 15 maps (DAO×5 + Street×5 + WC3×5)
- Diagonal-Rule: OnlyWhenNoObstacles (AND logic)
- LOS-Mode: strict supercover (>=/<= boundary, 25 unit tests)
- Script: code/experiments/run_experiment.py

## β Tuning (isolated)

- Prefix: beta_tuning
- Maps: 15 (same as main experiment, but different task percentile range)
- Tasks: 20/map, mode=middle_lo (30%-50% percentile by optimal_length)
- Beta grid: {0.1, 0.2, 0.3, 0.4, 0.5}
- Isolation: 30-50% percentile tasks have zero overlap with main experiment (50-70%) — verified
- Final-Beta: 0.3
- Command: `python code/experiments/run_experiment.py --out-prefix beta_tuning --task-mode middle_lo --tasks-per-map 20 --beta 0.3 --timeout 30`

## Main Experiment

- Prefix: exp_main
- Maps: 15
- Tasks: 20/map, mode=middle (50%-70% percentile by optimal_length)
- Algorithms: 7 (Dijkstra / A*Euc / A*Oct / WA*1.2 / Ours / NoAdapt / NoSmooth)
- All 7 algorithms run on the same task set per map
- Beta: 0.3 (locked from tuning)
- Timeout: 30s per task
- Timeout handling: timeout field=True, capped_total_ms=30000, timeout_rate reported
- Statistics: Wilcoxon (n=15) + BH-FDR + Cohen's d + rank-biserial r
- Command: `python code/experiments/run_experiment.py --out-prefix exp_main --task-mode middle --tasks-per-map 20 --beta 0.3 --timeout 30`

## Supplementary Experiment (long paths)

- Prefix: exp_long
- Maps: 15
- Tasks: 20/map, mode=longest (top 20 by optimal_length)
- Algorithms: 7 (same as main)
- Beta: 0.3 (same)
- Timeout: 30s
- Purpose: robustness validation under difficult scenarios
- Conclusions reported separately, not mixed with main
- Command: `python code/experiments/run_experiment.py --out-prefix exp_long --task-mode longest --tasks-per-map 20 --beta 0.3 --timeout 30`

## Time Fields

- preprocess_ms: integral image construction (Ours/NoSmooth only)
- search_ms: A* core loop
- postprocess_ms: two-stage smoothing (Ours/NoAdapt only)
- total_ms: sum of above three (primary comparison metric)
- capped_total_ms: min(total_ms, 30000) for timeout cases

## Raw Records Fields (20 columns)

run_id, map_type, map_name, map_size, obstacle_ratio, task_id, start, goal,
optimal_length, algorithm, success, timeout, path_length, turn_count,
expanded_nodes, preprocess_ms, search_ms, postprocess_ms, total_ms,
capped_total_ms, collision_free

## Task Manifest Fields

map_type, map_name, map_size, obstacle_ratio, task_id, start, goal,
optimal_length, task_source

## Stats Test Fields

compare_pair, metric, n_pairs, W, p_raw, q_bh, cohen_d,
rank_biserial_r, wins, ties, losses, base_mean, imp_mean, change_pct, reject_fdr

## Task Source Labels

- mode=middle    -> task_source=middle_50_70
- mode=middle_lo -> task_source=middle_30_50
- mode=longest   -> task_source=longest_top20
- mode=first     -> task_source=first_order
