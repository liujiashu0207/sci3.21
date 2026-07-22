# 残差驱动自适应加权 A* 路径规划算法

> Residual-Driven Adaptive Weighted A* (RD-A*) Path Planning for Mobile Robots

项目分两条线推进:

| 线 | 内容 | 状态 |
|----|------|------|
| **算法 / 论文** | RD-A* 算法实现 + MovingAI 基准实验(15 张地图,Wilcoxon + BH-FDR) | 实验完成,论文 v6.1 |
| **机器人 / 实机** | TurtleBot3 + ROS 2 Humble:扫图建图 → 地图格式互转 → 实机跑论文算法 | 扫图已通过,实机实验包已就绪 |

## 核心公式

```
f(n) = g(n) + α(n) × h_oct(n)
α(n) = 1 + β × (1 − ρ_local(n))
```

其中 ρ_local(n) 为节点 n 邻域内的障碍占比(积分图 O(1) 查询),β 为残差增益(标定值 0.3)。障碍越稀疏 α 越大、搜索越贪心;障碍越密集 α 越接近 1、越保守。

## 项目结构

```
├── code/                        # 算法与仿真实验(论文线)
│   ├── planners/
│   │   ├── core.py              #   基础函数(启发、邻居、平滑、碰撞检测)
│   │   └── algorithms.py        #   7 种算法配置(见下表)
│   ├── utils/map_loader.py      #   MovingAI 地图加载器
│   └── experiments/
│       ├── run_experiment.py    #   主实验脚本(可复现)
│       ├── run_exp_long.py      #   长路径补充实验
│       └── preexp_25x25.py      #   预实验
├── data/                        # MovingAI 基准数据(15 张地图 + 15 个 scen)
├── results/                     # 仿真实验输出 CSV
├── figures/                     # 论文图表
├── tests/                       # 单元测试(超覆盖线视线检测等)
├── docs/                        # 实验协议、审查报告、项目状态存档
│
├── turtlebot3/                  # 机器人线:ROBOTIS 官方包(v2.3.6,未修改)
│   └── README01.md              #   实机操作手册(启动/扫图/保存地图,已验证)
├── ros2_pkgs/
│   └── rdastar_nav/             # 实机实验包(ament_python),详见包内 README
├── transform.py                 # ROS 地图(.pgm+.yaml) ↔ MovingAI(.map+.scen)互转
└── my_map.pgm / my_map.yaml     # Cartographer 实扫地图(已通过测试)
```

## 算法线

### 一键复现 exp_v1

```bash
# 短路径实验(论文主实验)
python code/experiments/run_experiment.py \
  --tasks-per-map 50 --beta 0.3 --out-prefix exp_v1 --task-mode first

# 长路径补充实验
python code/experiments/run_experiment.py \
  --tasks-per-map 5 --beta 0.3 --out-prefix exp_v1_longpath --task-mode longest
```

### 实验配置(7 种算法)

| # | 算法 | 启发 | 权重 | 平滑 |
|---|------|------|------|------|
| 1 | Dijkstra | 无 | — | 无 |
| 2 | A*(欧氏) | 欧氏 | 1.0 | 无 |
| 3 | A*(Octile) | Octile | 1.0 | 无 |
| 4 | 加权A* | Octile | 1.2 | 无 |
| 5 | **RD-A*(本文)** | Octile | α(n) | 两阶段 |
| 6 | 消融:无自适应 | Octile | 1.0 | 两阶段 |
| 7 | 消融:无平滑 | Octile | α(n) | 无 |

### 结论边界声明

**可宣称(p<0.001, 15/15 maps):**
- 路径长度显著缩短(短路径 −5.0%,长路径 −3.0%)
- 转弯次数显著减少(短路径 −98%,长路径 −84%)
- 扩展节点数显著减少(短路径 −59%,长路径 −67%)

**不可宣称:**
- 运行时间改善(短路径上不显著,长路径上仅为趋势 p=0.064)
- 严格最优路径(本文为 α-最优,路径可能略长于绝对最优)

## 机器人线

完整流程链(前两步已实测通过):

1. **扫图建图** — TurtleBot3 bringup + Cartographer SLAM,`map_saver_cli` 保存地图。
   逐条命令见 [`turtlebot3/README01.md`](turtlebot3/README01.md)。
2. **格式互转** — `transform.py` 在 ROS 地图与 MovingAI 格式之间双向转换,
   实扫地图可直接进论文的仿真实验管线。
3. **实机实验** — [`ros2_pkgs/rdastar_nav/`](ros2_pkgs/rdastar_nav/README.md):
   用论文**原版 Python 算法**做全局规划(`planners/` 与 `code/planners/` 同源拷贝),
   执行交给 Nav2 controller(FollowPath/DWB),AMCL 定位;RViz 点目标即跑一次试验,
   规划 + 执行指标自动追加到 CSV,7 种算法经 launch 参数 `algorithm:=` 切换:

   ```bash
   ros2 launch rdastar_nav experiment.launch.py algorithm:=rdastar
   ```

   部署、RViz 操作、参数与注意事项见包内 README。

已知问题:机器人电池续航有限,对比实验建议用 `execute: false` 先验证规划,再上真机。

## 引用

```
Sturtevant, N. (2012). Benchmarks for Grid-Based Pathfinding.
Transactions on Computational Intelligence and AI in Games, 4(2), 144-148.
```
