# Experiment Protocol Lock

- Protocol-Version: EXP-v1.0-node-alpha-no-jump
- Code-Commit: 20e5bbe
- Data-Snapshot: MovingAI 15 maps (DAO×5 + Street×5 + WC3×5) + 15 scen files
- Task-Per-Map: 50
- Diagonal-Rule: OnlyWhenNoObstacles (AND logic)
- Main-Baseline: A*(Euclidean)
- Strong-Control: A*(Octile)
- Jump-Like: disabled
- Beta-Search: {0.1, 0.2, 0.3, 0.4, 0.5}
- Final-Beta: 0.3 (selected: best expansion reduction with avg PL diff < 5%)
- Smoothing-Radius: 5 (integral image window)
- Run-ID: exp_v1
