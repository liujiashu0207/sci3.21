# Technical Audit Report — exp_v1

## A) Protocol Freeze
- Protocol-Version: EXP-v1.0-node-alpha-no-jump
- Code-Commit: 20e5bbe
- Data-Snapshot: MovingAI 15 maps + 15 scen (DAO×5, Street×5, WC3×5)
- Final-Beta: 0.3
- Tasks: 50 per map (first 50 non-trivial scen tasks)
- Total records: 5250 (15 maps × 50 tasks × 7 algorithms)

## B) Quality Gates
- G1 Geometric Legality: **PASS** (5250/5250 success, 5250/5250 collision-free)
- G2 Caliber Consistency: **PASS** (15 maps, 7 algos, 50 tasks/map)
- G3 Statistical Consistency: **PASS** (PL/TC/EXP all significant, RT not claimed)
- G4 Figure Consistency: **PASS** (4 figures generated from run data)
- G5 Reproducibility: **PASS** (spot check exact match)

## C) Key Metrics (15-map global means)

| Algorithm | Path Length | Turn Count | Expanded | Runtime(ms) |
|-----------|-----------|------------|----------|-------------|
| Dijkstra | 10.16 | 1.43 | 326.0 | 2.3818 |
| A*(Euclidean) | 10.16 | 3.03 | 24.5 | 0.2162 |
| A*(Octile) | 10.16 | 1.57 | 17.9 | 0.1737 |
| Weighted A*(1.2) | 10.16 | 0.93 | 10.0 | 0.1067 |
| **Improved (Ours)** | **9.65** | **0.06** | **10.0** | **0.2254** |
| Ablation: No Adaptive | 9.65 | 0.06 | 17.9 | 0.1757 |
| Ablation: No Smooth | 10.16 | 1.00 | 10.0 | 0.1920 |

## D) Statistical Tests

### improved_ours vs A*(Euclidean)

| Metric | W | p-value | Cohen's d | r_rb | W/T/L | Sig |
|--------|---|---------|-----------|------|-------|-----|
| Path Length | 0 | 6.10e-05 | +13.154 | +1.000 | 15/0/0 | *** |
| Turn Count | 0 | 6.52e-04 | +7.173 | +1.000 | 15/0/0 | *** |
| Expanded Nodes | 0 | 6.10e-05 | +6.417 | +1.000 | 15/0/0 | *** |
| Runtime | 60 | 1.00 | -0.110 | 0.000 | 8/0/7 | ns |

### improved_ours vs A*(Octile)

| Metric | W | p-value | Cohen's d | r_rb | W/T/L | Sig |
|--------|---|---------|-----------|------|-------|-----|
| Path Length | 0 | 6.10e-05 | +13.154 | +1.000 | 15/0/0 | *** |
| Turn Count | 0 | 6.37e-04 | +12.579 | +1.000 | 15/0/0 | *** |
| Expanded Nodes | 0 | 6.10e-05 | +4.258 | +1.000 | 15/0/0 | *** |
| Runtime | 8 | 1.53e-03 | -0.817 | +0.867 | 2/0/13 | ** |

## E) Claim Boundary

### 可宣称结论（p<0.05, 15/15 maps consistent）
1. 改进A*的路径长度显著短于传统A*和Octile A*（-5.0%，p=6.1e-05）
2. 改进A*的转弯次数显著少于传统A*（-98%，p=6.5e-04）
3. 改进A*的扩展节点数显著少于传统A*（-59.2%，p=6.1e-05）和Octile A*（-44.1%，p=6.1e-05）

### 趋势结论（有数据支持但有限制条件）
4. 消融显示自适应权重主要贡献扩展节点减少（17.9→10.0），平滑主要贡献路径质量
5. 路径质量改善来自两阶段平滑（消融组验证）

### 不可宣称结论
6. ❌ 不可宣称运行时间改善（vs Euclidean p=1.0，vs Octile 实际更慢 p=0.0015）
7. ❌ 不可宣称严格最优性（α-最优，路径可能略长于绝对最优）
8. ❌ 当前数据基于短路径任务（mean PL≈10），长路径效果需补充验证

## F) Risks

### 高风险
- **H1: 任务路径过短。** 当前50个任务来自scen文件前50条（bucket 0-2），平均路径长度仅≈10。短路径上权重差异几乎无效果，且per-node开销占比高导致运行时间反而增加。**建议：补充长路径任务实验。**

### 中风险
- **M1: 运行时间不占优。** 积分图查询的per-node开销在短路径上不可忽略。长路径上预期改善。
- **M2: β=0.3 的路径增长。** 在长路径beta搜索中，β=0.3对应+4.0%路径增长。平滑可补偿约5%，但需验证。

### 低风险
- **L1: 基线用欧氏。** 论文需说明理由。
- **L2: 确定性算法无随机性。** 复现性已验证。
