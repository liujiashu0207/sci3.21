#!/usr/bin/env python3
"""
bloodvenomfalls Task 1 单任务复现脚本

Usage:
    cd /path/to/repo
    python code/experiments/verify_task1.py

输入: data/benchmark_maps/wc3-map/bloodvenomfalls.map
      data/benchmark_scens/wc3maps512/bloodvenomfalls.map.scen
输出: 7种算法的路径、指标、合法性检查
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "code"))
sys.path.insert(0, str(PROJECT_ROOT / "code" / "experiments"))

import numpy as np
from planners.core import (
    line_of_sight, make_integral_image, obstacle_ratio,
    supercover_cells, path_length, turn_count,
)
from planners.algorithms import (
    dijkstra_search, euclidean_astar, octile_astar,
    weighted_astar, residual_astar,
    ablation_no_adaptive, ablation_no_smoothing,
)
from utils.map_loader import load_grid_map
from run_experiment import parse_scen


def check_collision_free(grid, path):
    """逐点+逐段合法性检查"""
    h, w = grid.shape
    for p in path:
        if not (0 <= p[0] < h and 0 <= p[1] < w):
            return False, f"Point {p} out of bounds"
        if grid[p[0], p[1]] == 1:
            return False, f"Point {p} on obstacle"
    for i in range(1, len(path)):
        if not line_of_sight(grid, path[i-1], path[i]):
            return False, f"LOS fail {path[i-1]}->{path[i]}"
    return True, "OK"


def main():
    # 1. 加载地图
    map_path = PROJECT_ROOT / "data/benchmark_maps/wc3-map/bloodvenomfalls.map"
    scen_path = PROJECT_ROOT / "data/benchmark_scens/wc3maps512/bloodvenomfalls.map.scen"
    
    grid = load_grid_map(map_path)
    h, w = grid.shape
    obs = obstacle_ratio(grid)
    integral = make_integral_image(grid)
    
    print(f"Map: bloodvenomfalls {h}x{w} obs={obs:.1%}")
    
    # 2. 取任务（middle 50-70% 分位，第1条）
    tasks = parse_scen(scen_path, 20, 'middle')
    start, goal, opt = tasks[0]
    print(f"Task 1: S={start} G={goal} opt={opt:.6f}")
    print(f"Start free: {grid[start[0], start[1]] == 0}")
    print(f"Goal free:  {grid[goal[0], goal[1]] == 0}")
    
    # 3. 验证任务来源
    # scen文件1570条非零任务，按optimal_length排序
    # 50%分位=index 785, 70%分位=index 1099
    # tasks[0]应对应排序后的第785条
    all_tasks = []
    with open(scen_path) as f:
        for line in f:
            if line.startswith('version'): continue
            parts = line.strip().split()
            if len(parts) < 9: continue
            sc, sr = int(parts[4]), int(parts[5])
            gc, gr = int(parts[6]), int(parts[7])
            o = float(parts[8])
            if o == 0: continue
            all_tasks.append(((sr, sc), (gr, gc), o))
    all_tasks.sort(key=lambda t: t[2])
    lo = int(len(all_tasks) * 0.5)
    expected = all_tasks[lo]
    assert start == expected[0], f"Start mismatch: {start} != {expected[0]}"
    assert goal == expected[1], f"Goal mismatch: {goal} != {expected[1]}"
    assert abs(opt - expected[2]) < 0.001, f"Opt mismatch: {opt} != {expected[2]}"
    print(f"Task source verified: scen index {lo} of {len(all_tasks)} (50% percentile) ✓")
    
    # 4. 跑7种算法
    algos = [
        ("dijkstra",           lambda: dijkstra_search(grid, start, goal)),
        ("astar_euclidean",    lambda: euclidean_astar(grid, start, goal)),
        ("astar_octile",       lambda: octile_astar(grid, start, goal)),
        ("weighted_1.2",       lambda: weighted_astar(grid, start, goal, weight=1.2)),
        ("improved_ours",      lambda: residual_astar(grid, start, goal, beta=0.3,
                                                      precomputed_integral=integral)),
        ("ablation_no_adapt",  lambda: ablation_no_adaptive(grid, start, goal)),
        ("ablation_no_smooth", lambda: ablation_no_smoothing(grid, start, goal, beta=0.3,
                                                             precomputed_integral=integral)),
    ]
    
    print(f"\n{'Algorithm':<22} {'PL':>8} {'TC':>5} {'EXP':>8} "
          f"{'Pre_ms':>8} {'Search_ms':>10} {'Post_ms':>8} {'Total_ms':>10} "
          f"{'Pts':>5} {'CF':>4}")
    print("-" * 100)
    
    for aname, afunc in algos:
        res = afunc()
        path = res['path']
        cf, reason = check_collision_free(grid, path) if res['success'] else (False, "search failed")
        
        # 验证字段完整性
        required = ['success','path','path_length','turn_count','expanded_nodes',
                     'preprocess_ms','search_ms','postprocess_ms','total_ms']
        missing = [f for f in required if f not in res]
        assert not missing, f"{aname}: missing fields {missing}"
        
        # 验证时间一致性
        tsum = res['preprocess_ms'] + res['search_ms'] + res['postprocess_ms']
        assert abs(res['total_ms'] - tsum) < 0.01, \
            f"{aname}: total_ms={res['total_ms']:.4f} != sum={tsum:.4f}"
        
        # 验证路径起终点
        assert path[0] == start, f"{aname}: path[0]={path[0]} != start={start}"
        assert path[-1] == goal, f"{aname}: path[-1]={path[-1]} != goal={goal}"
        
        status = "✅" if cf else "❌"
        print(f"{aname:<22} {res['path_length']:>8.2f} {res['turn_count']:>5} {res['expanded_nodes']:>8} "
              f"{res['preprocess_ms']:>8.2f} {res['search_ms']:>10.2f} {res['postprocess_ms']:>8.2f} "
              f"{res['total_ms']:>10.2f} {len(path):>5} {status:>4}")
        
        if not cf:
            print(f"  !! {reason}")
    
    print(f"\n{'='*60}")
    print("All assertions passed. Experiment is reproducible.")


if __name__ == "__main__":
    main()
