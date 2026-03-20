# 残差驱动自适应加权 A* 路径规划算法

> Residual-Driven Adaptive Weighted A* Path Planning for Mobile Robots

## 核心公式

```
f(n) = g(n) + α(n) × h_oct(n)
α(n) = 1 + β × (1 − ρ_local(n))
```

## 项目结构

```
├── data/                    # MovingAI 基准数据（15张地图 + 15个scen）
│   ├── benchmark_maps/      # .map 地图文件
│   └── benchmark_scens/     # .scen 任务文件
├── code/
│   ├── planners/
│   │   ├── core.py          # 基础函数（启发、邻居、平滑、碰撞检测）
│   │   └── algorithms.py    # 7种算法配置
│   ├── utils/
│   │   └── map_loader.py    # MovingAI 地图加载器
│   └── experiments/         # 实验脚本
├── results/                 # 实验输出
├── figures/                 # 论文图表
└── docs/                    # 技术文档
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

## 引用

如使用 MovingAI 基准数据，请引用：
```
Sturtevant, N. (2012). Benchmarks for Grid-Based Pathfinding.
Transactions on Computational Intelligence and AI in Games, 4(2), 144-148.
```
