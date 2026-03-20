# Experiment Protocol Lock

- Protocol-Version: EXP-v1.0-node-alpha-no-jump
- Code-Commit: 24f488d (exp_v1 results generated at this commit)
- Run-ID: exp_v1
- Data-Snapshot: MovingAI 15 maps (DAO×5 + Street×5 + WC3×5) + 15 scen files
- Task-Per-Map: 50 (first 50 non-trivial scen tasks, strict order)
- Task-Mode: first
- Diagonal-Rule: OnlyWhenNoObstacles (AND logic)
- Main-Baseline: A*(Euclidean)
- Strong-Control: A*(Octile)
- Jump-Like: disabled
- Beta-Search: {0.1, 0.2, 0.3, 0.4, 0.5}
- Final-Beta: 0.3 (selected: best expansion reduction with avg PL diff < 5%)
- Smoothing-Radius: 5 (integral image window)
- Script-Entrypoint: code/experiments/run_experiment.py

## Reproduce Command

```bash
python code/experiments/run_experiment.py \
  --tasks-per-map 50 --beta 0.3 --out-prefix exp_v1 --task-mode first
```

## Output Files

- results/exp_v1_raw_records.csv
- results/exp_v1_summary.csv
- results/exp_v1_key_metrics.csv
- results/exp_v1_stats_tests.csv
- results/exp_v1_task_manifest.csv
- figures/exp_v1_expanded_nodes.png
- figures/exp_v1_path_length.png
- figures/exp_v1_turn_count.png
- figures/exp_v1_ablation.png
