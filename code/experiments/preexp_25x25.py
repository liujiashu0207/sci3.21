#!/usr/bin/env python3
"""
25×25 预实验完整代码（可独立运行）

Usage:
    cd /path/to/repo
    python code/experiments/preexp_25x25.py

输入: data/preexp_25x25.npy（25×25栅格地图）
输出: 6张单图 + 1张拼图 + 控制台数据表
"""

import sys
import numpy as np
from pathlib import Path

# Resolve project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "code"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from planners.core import (
    line_of_sight,
    make_integral_image,
    obstacle_ratio,
    supercover_cells,
)
from planners.algorithms import (
    euclidean_astar,
    octile_astar,
    weighted_astar,
    residual_astar,
    ablation_no_adaptive,
    ablation_no_smoothing,
)


# ============================================================
# 1. 加载地图
# ============================================================

GRID_PATH = PROJECT_ROOT / "data" / "preexp_25x25.npy"
grid = np.load(str(GRID_PATH))
N = grid.shape[0]  # 25
start = (23, 1)     # 左下角
goal = (2, 23)      # 右上角
BETA = 0.3
integral = make_integral_image(grid)

print(f"Grid: {N}x{N}, obs={obstacle_ratio(grid):.4f}")
print(f"Start: {start}, Goal: {goal}")
print(f"Start free: {grid[start[0], start[1]] == 0}")
print(f"Goal free:  {grid[goal[0], goal[1]] == 0}")


# ============================================================
# 2. 定义算法组
# ============================================================

ALGO_DEFS = [
    ("A*(Euclidean)", "#2196F3",
     lambda: euclidean_astar(grid, start, goal)),

    ("A*(Octile)", "#4CAF50",
     lambda: octile_astar(grid, start, goal)),

    ("WA*(1.2)", "#FF9800",
     lambda: weighted_astar(grid, start, goal, weight=1.2)),

    ("Ours (RDA*)", "#F44336",
     lambda: residual_astar(grid, start, goal, beta=BETA,
                            precomputed_integral=integral)),

    ("NoAdaptive", "#9C27B0",
     lambda: ablation_no_adaptive(grid, start, goal)),

    ("NoSmooth", "#795548",
     lambda: ablation_no_smoothing(grid, start, goal, beta=BETA,
                                   precomputed_integral=integral)),
]


# ============================================================
# 3. 执行算法 + 合法性检查
# ============================================================

def check_legality(grid, path):
    """严格合法性检查：每个点在自由格 + 每段通过 supercover LOS"""
    for p in path:
        if grid[p[0], p[1]] == 1:
            return False, f"Point {p} is obstacle"
    for i in range(1, len(path)):
        if not line_of_sight(grid, path[i - 1], path[i]):
            return False, f"Segment {path[i-1]}->{path[i]} fails LOS"
    return True, "OK"


results = []

print(f"\n{'Algorithm':<18} {'PL':>7} {'TC':>4} {'EXP':>5} "
      f"{'Time(ms)':>10} {'Pts':>4} {'Legal':>6}")
print("-" * 60)

for aname, color, func in ALGO_DEFS:
    res = func()
    path = res["path"]
    legal, reason = check_legality(grid, path)
    results.append((aname, color, res, legal, reason))

    status = "✅" if legal else "❌"
    print(f"{aname:<18} {res['path_length']:>7.2f} {res['turn_count']:>4} "
          f"{res['expanded_nodes']:>5} {res['runtime_ms']:>10.4f} "
          f"{len(path):>4} {status:>6}")


# ============================================================
# 4. 打印路径坐标（供人工审查）
# ============================================================

print("\n=== 路径坐标 ===")
for aname, _, res, legal, reason in results:
    path = res["path"]
    print(f"\n{aname} ({len(path)} points, legal={legal}):")
    print(f"  {path}")


# ============================================================
# 5. 打印对比表
# ============================================================

euc_pl = results[0][2]["path_length"]
euc_tc = results[0][2]["turn_count"]
euc_exp = results[0][2]["expanded_nodes"]
euc_rt = results[0][2]["runtime_ms"]

print(f"\n{'='*90}")
print(f"{'Algorithm':<18} {'PL':>7} {'TC':>4} {'EXP':>5} {'Time(ms)':>10} "
      f"| {'vEuc PL':>8} {'vEuc TC':>8} {'vEuc EXP':>9} {'vEuc Time':>10}")
print(f"{'='*90}")

for aname, _, res, _, _ in results:
    dp = (res["path_length"] / euc_pl - 1) * 100
    dt = (res["turn_count"] / euc_tc - 1) * 100 if euc_tc > 0 else 0
    de = (res["expanded_nodes"] / euc_exp - 1) * 100
    dr = (res["runtime_ms"] / euc_rt - 1) * 100
    print(f"{aname:<18} {res['path_length']:>7.2f} {res['turn_count']:>4} "
          f"{res['expanded_nodes']:>5} {res['runtime_ms']:>10.4f} "
          f"| {dp:>+7.1f}% {dt:>+7.1f}% {de:>+8.1f}% {dr:>+9.1f}%")


# ============================================================
# 6. 消融分析
# ============================================================

print("\n=== 消融分析 ===")

ours = results[3][2]      # Ours (RDA*)
noadapt = results[4][2]   # NoAdaptive
nosmooth = results[5][2]  # NoSmooth
octile = results[1][2]    # A*(Octile)

print(f"\n自适应权重的贡献（Ours vs NoAdaptive）:")
print(f"  EXP: {ours['expanded_nodes']} vs {noadapt['expanded_nodes']} "
      f"(自适应减少 {(1 - ours['expanded_nodes']/noadapt['expanded_nodes'])*100:.1f}%)")
print(f"  Time: {ours['runtime_ms']:.3f} vs {noadapt['runtime_ms']:.3f}ms")

print(f"\n平滑的贡献（Ours vs NoSmooth）:")
print(f"  PL: {ours['path_length']:.2f} vs {nosmooth['path_length']:.2f} "
      f"(平滑缩短 {(1 - ours['path_length']/nosmooth['path_length'])*100:.1f}%)")
print(f"  TC: {ours['turn_count']} vs {nosmooth['turn_count']} "
      f"(平滑减少 {(1 - ours['turn_count']/nosmooth['turn_count'])*100:.1f}%)")

print(f"\n自适应 vs 固定权重（NoSmooth vs WA*1.2）:")
print(f"  EXP: {nosmooth['expanded_nodes']} vs {results[2][2]['expanded_nodes']} "
      f"(自适应比固定少 {(1 - nosmooth['expanded_nodes']/results[2][2]['expanded_nodes'])*100:.1f}%)")


# ============================================================
# 7. 生成 6 张单图
# ============================================================

OUTPUT_DIR = PROJECT_ROOT / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)

for idx, (aname, color, res, legal, _) in enumerate(results):
    fig, ax = plt.subplots(figsize=(8, 8))
    path = res["path"]

    # 画栅格
    for r in range(N):
        for c in range(N):
            if grid[r, c] == 1:
                ax.add_patch(Rectangle((c, N-1-r), 1, 1,
                             fc="black", ec="#333", lw=0.3))
            else:
                ax.add_patch(Rectangle((c, N-1-r), 1, 1,
                             fc="white", ec="#DDDDDD", lw=0.4))

    # 画路径
    px = [c + 0.5 for (r, c) in path]
    py = [N - 1 - r + 0.5 for (r, c) in path]
    ax.plot(px, py, color=color, lw=2.5, marker="o", ms=3,
            zorder=5, alpha=0.9,
            solid_capstyle="round", solid_joinstyle="round")

    # 起终点
    ax.plot(start[1]+0.5, N-1-start[0]+0.5, "o",
            color="#00E676", ms=12, zorder=10, mec="black", mew=1.5)
    ax.plot(goal[1]+0.5, N-1-goal[0]+0.5, "*",
            color="#FF1744", ms=16, zorder=10, mec="black", mew=1)

    # 坐标轴
    ax.set_xticks(np.arange(0.5, N+0.5, 3))
    ax.set_xticklabels(np.arange(0, N, 3), fontsize=8)
    ax.set_yticks(np.arange(0.5, N+0.5, 3))
    ax.set_yticklabels(np.arange(0, N, 3), fontsize=8)
    ax.set_xlim(0, N)
    ax.set_ylim(0, N)
    ax.set_aspect("equal")

    letter = chr(97 + idx)
    ax.set_title(
        f"({letter}) {aname}\n"
        f"PL={res['path_length']:.2f}  TC={res['turn_count']}  "
        f"EXP={res['expanded_nodes']}  Time={res['runtime_ms']:.3f}ms",
        fontsize=11, fontweight="bold",
    )

    plt.tight_layout()
    safename = (aname.replace("*", "star").replace("(", "")
                .replace(")", "").replace(" ", "_"))
    fig_path = OUTPUT_DIR / f"preexp25_{letter}_{safename}.png"
    plt.savefig(str(fig_path), dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  ✅ {fig_path.name}")


# ============================================================
# 8. 生成 2×3 拼图
# ============================================================

fig, axes = plt.subplots(2, 3, figsize=(20, 14))

for idx, (aname, color, res, _, _) in enumerate(results):
    ax = axes[idx // 3][idx % 3]
    path = res["path"]

    for r in range(N):
        for c in range(N):
            fc = "black" if grid[r, c] == 1 else "white"
            ec = "#444" if grid[r, c] == 1 else "#EEE"
            ax.add_patch(Rectangle((c, N-1-r), 1, 1, fc=fc, ec=ec, lw=0.3))

    px = [c + 0.5 for (r, c) in path]
    py = [N - 1 - r + 0.5 for (r, c) in path]
    ax.plot(px, py, color=color, lw=2.0, marker="o", ms=2.5,
            zorder=5, alpha=0.9,
            solid_capstyle="round", solid_joinstyle="round")

    ax.plot(start[1]+0.5, N-1-start[0]+0.5, "o",
            color="#00E676", ms=10, zorder=10, mec="black", mew=1.5)
    ax.plot(goal[1]+0.5, N-1-goal[0]+0.5, "*",
            color="#FF1744", ms=14, zorder=10, mec="black", mew=1)

    ax.set_xticks(np.arange(0.5, N+0.5, 3))
    ax.set_xticklabels(np.arange(0, N, 3), fontsize=7)
    ax.set_yticks(np.arange(0.5, N+0.5, 3))
    ax.set_yticklabels(np.arange(0, N, 3), fontsize=7)
    ax.set_xlim(0, N)
    ax.set_ylim(0, N)
    ax.set_aspect("equal")

    letter = chr(97 + idx)
    ax.set_title(
        f"({letter}) {aname}\n"
        f"PL={res['path_length']:.2f}  TC={res['turn_count']}  "
        f"EXP={res['expanded_nodes']}  T={res['runtime_ms']:.3f}ms",
        fontsize=9, fontweight="bold",
    )

plt.tight_layout()
panel_path = OUTPUT_DIR / "preexp25_panel.png"
plt.savefig(str(panel_path), dpi=200, bbox_inches="tight")
plt.close()
print(f"  ✅ {panel_path.name}")

print("\nDone.")
