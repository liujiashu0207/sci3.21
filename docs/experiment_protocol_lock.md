# Experiment Protocol Lock (v2)

- Protocol-Version: EXP-v2.0-dual-track
- Code-Commit: dcffd0f
- Data-Snapshot: MovingAI 15 maps (DAO×5 + Street×5 + WC3×5)
- Diagonal-Rule: OnlyWhenNoObstacles (AND logic)
- LOS-Mode: strict supercover (>=/<= boundary, 25 unit tests)
- Jump-Like: disabled
- Script: code/experiments/run_experiment.py

## β Tuning (isolated)

- Maps: 5 (orz100d, Moscow_0_512, bloodvenomfalls, brc503d, battleground)
- Tasks: 20/map, mode=middle (30-50 percentile by optimal_length)
- Beta grid: {0.1, 0.2, 0.3, 0.4, 0.5}
- Isolation: zero overlap with main and long task sets (verified)
- Final-Beta: TBD
- Command: `python code/experiments/run_experiment.py --out-prefix beta_tuning --task-mode middle`

## Main Experiment

- Prefix: exp_main
- Maps: 15
- Tasks: 20/map, mode=first (scen fixed order, deterministic)
- Algorithms: 7 (Dijkstra / A*Euc / A*Oct / WA*1.2 / Ours / NoAdapt / NoSmooth)
- Beta: Final-Beta from tuning
- Timeout: 30s per task (timeout recorded, not silently dropped)
- Statistics: Wilcoxon (n=15) + BH-FDR + Cohen's d + rank-biserial r
- Command: `python code/experiments/run_experiment.py --out-prefix exp_main --task-mode first`

## Supplementary Experiment (long paths)

- Prefix: exp_long
- Maps: 15
- Tasks: 20/map, mode=longest (top 20 by optimal_length)
- Algorithms: 7
- Beta: same Final-Beta
- Purpose: robustness validation under difficult scenarios
- Conclusions reported separately, not mixed with main
- Command: `python code/experiments/run_experiment.py --out-prefix exp_long --task-mode longest`

## Time Fields

- preprocess_ms: integral image construction (G5/G7 only)
- search_ms: A* core loop
- postprocess_ms: two-stage smoothing (G5/G6 only)
- total_ms: sum of above three (primary comparison metric)
