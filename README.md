# 残差驱动自适应加权 A* 路径规划算法

> Residual-Driven Adaptive Weighted A* Path Planning for Mobile Robots

## 核心公式

```
f(n) = g(n) + α(n) × h_oct(n)
α(n) = 1 + β × (1 − ρ_local(n))
```

## 一键复现 exp_v1

```bash
# 短路径实验（论文主实验）
python code/experiments/run_experiment.py \
  --tasks-per-map 50 --beta 0.3 --out-prefix exp_v1 --task-mode first

# 长路径补充实验
python code/experiments/run_experiment.py \
  --tasks-per-map 5 --beta 0.3 --out-prefix exp_v1_longpath --task-mode longest
```

## 项目结构

```
├── data/                    # MovingAI 基准数据（15张地图 + 15个scen）
├── code/
│   ├── planners/
│   │   ├── core.py          # 基础函数（启发、邻居、平滑、碰撞检测）
│   │   └── algorithms.py    # 7种算法配置
│   ├── utils/
│   │   └── map_loader.py    # MovingAI 地图加载器
│   └── experiments/
│       └── run_experiment.py # 可复现实验脚本
├── results/                 # 实验输出CSV
├── figures/                 # 论文图表
└── docs/                    # 技术文档与审计报告
```

## 实验配置

| # | 算法 | 启发 | 权重 | 平滑 |
|---|------|------|------|------|
| 1 | Dijkstra | 无 | — | 无 |
| 2 | A*(欧氏) | 欧氏 | 1.0 | 无 |
| 3 | A*(Octile) | Octile | 1.0 | 无 |
| 4 | 加权A* | Octile | 1.2 | 无 |
| 5 | **改进A*(本文)** | Octile | α(n) | 两阶段 |
| 6 | 消融:无自适应 | Octile | 1.0 | 两阶段 |
| 7 | 消融:无平滑 | Octile | α(n) | 无 |

## 结论边界声明

**可宣称（p<0.001, 15/15 maps）：**
- 路径长度显著缩短（短路径-5.0%，长路径-3.0%）
- 转弯次数显著减少（短路径-98%，长路径-84%）
- 扩展节点数显著减少（短路径-59%，长路径-67%）

**不可宣称：**
- 运行时间改善（短路径上不显著，长路径上仅为趋势 p=0.064）
- 严格最优路径（本文为 α-最优，路径可能略长于绝对最优）

## 引用

```
Sturtevant, N. (2012). Benchmarks for Grid-Based Pathfinding.
Transactions on Computational Intelligence and AI in Games, 4(2), 144-148.
```
