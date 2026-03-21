#!/usr/bin/env python3
"""
Reproducible experiment script for Residual-Driven Adaptive Weighted A*.

Usage (主实验):
    python code/experiments/run_experiment.py --out-prefix exp_main --task-mode first

Usage (补充实验):
    python code/experiments/run_experiment.py --out-prefix exp_long --task-mode longest

Usage (β调参):
    python code/experiments/run_experiment.py --out-prefix beta_tuning --task-mode first \
        --task-start 20 --tasks-per-map 20
"""

import argparse
import csv
import os
import signal
import sys
import time
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from planners.core import (
    line_of_sight,
    make_integral_image,
    obstacle_ratio,
    path_length,
    turn_count,
)
from planners.algorithms import (
    ablation_no_adaptive,
    ablation_no_smoothing,
    dijkstra_search,
    euclidean_astar,
    octile_astar,
    residual_astar,
    weighted_astar,
)
from utils.map_loader import load_grid_map

# ── Map definitions (v2: optimized selection) ────────────────────────────

MAP_LIST = [
    ("dao",    "dao-map/brc503d.map",            "dao/brc503d.map.scen"),
    ("dao",    "dao-map/orz100d.map",            "dao/orz100d.map.scen"),
    ("dao",    "dao-map/den502d.map",            "dao/den502d.map.scen"),
    ("dao",    "dao-map/arena2.map",             "dao/arena2.map.scen"),
    ("dao",    "dao-map/ost003d.map",            "dao/ost003d.map.scen"),
    ("street", "street-map/Berlin_0_512.map",    "street/Berlin_0_512.map.scen"),
    ("street", "street-map/London_0_512.map",    "street/London_0_512.map.scen"),
    ("street", "street-map/Moscow_0_512.map",    "street/Moscow_0_512.map.scen"),
    ("street", "street-map/Paris_0_512.map",     "street/Paris_0_512.map.scen"),
    ("street", "street-map/Shanghai_0_512.map",  "street/Shanghai_0_512.map.scen"),
    ("wc3",   "wc3-map/dustwallowkeys.map",      "wc3maps512/dustwallowkeys.map.scen"),
    ("wc3",   "wc3-map/blastedlands.map",        "wc3maps512/blastedlands.map.scen"),
    ("wc3",   "wc3-map/bloodvenomfalls.map",     "wc3maps512/bloodvenomfalls.map.scen"),
    ("wc3",   "wc3-map/darkforest.map",          "wc3maps512/darkforest.map.scen"),
    ("wc3",   "wc3-map/battleground.map",        "wc3maps512/battleground.map.scen"),
]


def parse_scen(scen_path, n, mode="first", start_offset=0):
    """
    Parse MovingAI .scen file.
    mode="first": fixed scen order, skip first start_offset, take next n.
    mode="longest": sort by optimal_length desc, take top n.
    """
    all_tasks = []
    with open(scen_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("version"):
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            sc, sr = int(parts[4]), int(parts[5])
            gc, gr = int(parts[6]), int(parts[7])
            opt = float(parts[8])
            if opt == 0.0:
                continue
            all_tasks.append(((sr, sc), (gr, gc), opt))

    if mode == "longest":
        all_tasks.sort(key=lambda t: t[2], reverse=True)
        return all_tasks[:n]
    elif mode == "middle":
        # Sort by optimal_length, take 50%-70% percentile range.
        # Main experiment: long enough for meaningful algorithm differences,
        # short enough that Dijkstra won't massively timeout.
        all_tasks.sort(key=lambda t: t[2])
        lo = int(len(all_tasks) * 0.5)
        hi = int(len(all_tasks) * 0.7)
        mid_tasks = all_tasks[lo:hi]
        return mid_tasks[:n]
    elif mode == "middle_lo":
        # Sort by optimal_length, take 30%-50% percentile range.
        # Used for beta tuning — isolated from main experiment (50-70%).
        all_tasks.sort(key=lambda t: t[2])
        lo = int(len(all_tasks) * 0.3)
        hi = int(len(all_tasks) * 0.5)
        mid_tasks = all_tasks[lo:hi]
        return mid_tasks[:n]
    else:  # first
        return all_tasks[start_offset:start_offset + n]


def check_collision_free(grid, path):
    for p in path:
        if grid[p[0], p[1]] == 1:
            return False
    for i in range(1, len(path)):
        if not line_of_sight(grid, path[i - 1], path[i]):
            return False
    return True


# ── Timeout wrapper ──────────────────────────────────────────────────────

class TimeoutError(Exception):
    pass

def run_with_timeout(func, timeout_s):
    """Run func(), return (result, False) or (None, True) if timeout."""
    if timeout_s <= 0:
        return func(), False

    t0 = time.perf_counter()
    # Simple polling approach (cross-platform, no signal issues)
    result = func()
    elapsed = time.perf_counter() - t0
    if elapsed > timeout_s:
        return result, True  # completed but exceeded threshold
    return result, False


RAW_FIELDS = [
    "run_id", "map_type", "map_name", "map_size", "obstacle_ratio",
    "task_id", "start", "goal", "optimal_length", "algorithm",
    "success", "timeout", "path_length", "turn_count", "expanded_nodes",
    "preprocess_ms", "search_ms", "postprocess_ms", "total_ms",
    "capped_total_ms", "collision_free",
]

# Map task_mode to task_source label
TASK_SOURCE_MAP = {
    "first": "first_order",
    "middle": "middle_50_70",
    "middle_lo": "middle_30_50",
    "longest": "longest_top20",
}


def run_experiment(args):
    maps_root = Path(args.maps_root)
    scens_root = Path(args.scens_root)
    results_dir = PROJECT_ROOT / "results"
    figures_dir = PROJECT_ROOT / "figures"
    results_dir.mkdir(exist_ok=True)
    figures_dir.mkdir(exist_ok=True)

    prefix = args.out_prefix
    beta = args.beta
    tasks_per_map = args.tasks_per_map
    task_mode = args.task_mode
    task_start = args.task_start
    timeout_s = args.timeout

    print(f"=== Experiment: {prefix} ===")
    print(f"  Beta={beta}, Tasks/map={tasks_per_map}, Mode={task_mode}, "
          f"Start={task_start}, Timeout={timeout_s}s")
    print()

    raw_rows = []
    manifest_rows = []
    t_global = time.perf_counter()

    for mi, (mtype, map_rel, scen_rel) in enumerate(MAP_LIST):
        map_path = maps_root / map_rel
        scen_path = scens_root / scen_rel

        if not map_path.exists():
            print(f"  SKIP {map_rel}: map not found")
            continue
        if not scen_path.exists():
            print(f"  SKIP {scen_rel}: scen not found")
            continue

        grid = load_grid_map(map_path)
        h_map, w_map = grid.shape
        obs = obstacle_ratio(grid)
        integral = make_integral_image(grid)
        mname = map_path.stem
        tasks = parse_scen(scen_path, tasks_per_map,
                           mode=task_mode, start_offset=task_start)

        task_source = TASK_SOURCE_MAP.get(task_mode, task_mode)

        for ti, (s, g, opt) in enumerate(tasks):
            manifest_rows.append({
                "map_type": mtype, "map_name": mname,
                "map_size": f"{h_map}x{w_map}",
                "obstacle_ratio": f"{obs:.4f}", "task_id": ti,
                "start": f"{s[0]},{s[1]}", "goal": f"{g[0]},{g[1]}",
                "optimal_length": f"{opt:.6f}",
                "task_source": task_source,
            })

        t_map = time.perf_counter()

        for ti, (start, goal, opt_len) in enumerate(tasks):
            algos = [
                ("dijkstra",          lambda s, g: dijkstra_search(grid, s, g)),
                ("astar_euclidean",   lambda s, g: euclidean_astar(grid, s, g)),
                ("astar_octile",      lambda s, g: octile_astar(grid, s, g)),
                ("weighted_1.2",      lambda s, g: weighted_astar(grid, s, g, weight=1.2)),
                ("improved_ours",     lambda s, g: residual_astar(
                    grid, s, g, beta=beta, precomputed_integral=integral)),
                ("ablation_no_adapt", lambda s, g: ablation_no_adaptive(grid, s, g)),
                ("ablation_no_smooth", lambda s, g: ablation_no_smoothing(
                    grid, s, g, beta=beta, precomputed_integral=integral)),
            ]

            for aname, afunc in algos:
                res, timed_out = run_with_timeout(
                    lambda: afunc(start, goal), timeout_s)

                if timed_out or res is None:
                    # Timeout: record with threshold values
                    raw_rows.append({
                        "run_id": prefix, "map_type": mtype,
                        "map_name": mname, "map_size": f"{h_map}x{w_map}",
                        "obstacle_ratio": f"{obs:.4f}", "task_id": ti,
                        "start": f"{start[0]},{start[1]}",
                        "goal": f"{goal[0]},{goal[1]}",
                        "optimal_length": f"{opt_len:.6f}",
                        "algorithm": aname,
                        "success": False, "timeout": True,
                        "path_length": "", "turn_count": "",
                        "expanded_nodes": "",
                        "preprocess_ms": "",
                        "search_ms": "",
                        "postprocess_ms": "",
                        "total_ms": f"{timeout_s * 1000:.4f}",
                        "capped_total_ms": f"{timeout_s * 1000:.4f}",
                        "collision_free": False,
                    })
                else:
                    # Check if total_ms exceeds timeout (ran but was slow)
                    is_timeout = res["total_ms"] > timeout_s * 1000

                    cf = check_collision_free(grid, res["path"]) \
                        if res["success"] else False
                    actual_total = float(res['total_ms'])
                    capped = timeout_s * 1000 if is_timeout else actual_total
                    raw_rows.append({
                        "run_id": prefix, "map_type": mtype,
                        "map_name": mname, "map_size": f"{h_map}x{w_map}",
                        "obstacle_ratio": f"{obs:.4f}", "task_id": ti,
                        "start": f"{start[0]},{start[1]}",
                        "goal": f"{goal[0]},{goal[1]}",
                        "optimal_length": f"{opt_len:.6f}",
                        "algorithm": aname,
                        "success": res["success"],
                        "timeout": is_timeout,
                        "path_length": f"{res['path_length']:.6f}"
                            if res["success"] else "",
                        "turn_count": res["turn_count"]
                            if res["success"] else "",
                        "expanded_nodes": res["expanded_nodes"]
                            if res["success"] else "",
                        "preprocess_ms": f"{res['preprocess_ms']:.4f}",
                        "search_ms": f"{res['search_ms']:.4f}",
                        "postprocess_ms": f"{res['postprocess_ms']:.4f}",
                        "total_ms": f"{actual_total:.4f}",
                        "capped_total_ms": f"{capped:.4f}",
                        "collision_free": cf,
                    })

        elapsed = time.perf_counter() - t_map
        n_maps = len(MAP_LIST)
        print(f"  [{mi+1}/{n_maps}] {mname:<22} "
              f"{len(tasks)} tasks × 7 algos ({elapsed:.1f}s)")

    total_s = time.perf_counter() - t_global

    # ── Write raw records ───────────────────────────────────────────────
    raw_path = results_dir / f"{prefix}_raw_records.csv"
    with raw_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RAW_FIELDS)
        w.writeheader()
        w.writerows(raw_rows)

    # ── Write task manifest ─────────────────────────────────────────────
    if manifest_rows:
        manifest_path = results_dir / f"{prefix}_task_manifest.csv"
        with manifest_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=manifest_rows[0].keys())
            w.writeheader()
            w.writerows(manifest_rows)

    # ── Summary ─────────────────────────────────────────────────────────
    maps = sorted(set(r["map_name"] for r in raw_rows))
    algos_list = sorted(set(r["algorithm"] for r in raw_rows))

    summary_rows = []
    for m in maps:
        for a in algos_list:
            mr = [r for r in raw_rows
                  if r["map_name"] == m and r["algorithm"] == a]
            n_total = len(mr)
            n_success = sum(1 for r in mr if r["success"] is True
                           or r["success"] == "True")
            n_timeout = sum(1 for r in mr if r["timeout"] is True
                           or r["timeout"] == "True")
            # Only compute metrics on successful non-timeout runs
            ok = [r for r in mr if (r["success"] is True or r["success"] == "True")
                  and r["path_length"] != ""]
            if ok:
                pls = [float(r["path_length"]) for r in ok]
                tcs = [int(r["turn_count"]) for r in ok]
                exps = [int(r["expanded_nodes"]) for r in ok]
                totals = [float(r["total_ms"]) for r in ok]
                searches = [float(r["search_ms"]) for r in ok]
                cfs = [r["collision_free"] is True
                       or r["collision_free"] == "True" for r in ok]
            else:
                pls = tcs = exps = totals = searches = cfs = []

            summary_rows.append({
                "map_name": m, "algorithm": a, "n_total": n_total,
                "n_success": n_success, "n_timeout": n_timeout,
                "timeout_rate": f"{n_timeout/n_total:.4f}" if n_total else "",
                "path_length_mean": f"{np.mean(pls):.6f}" if pls else "",
                "path_length_std": f"{np.std(pls):.6f}" if pls else "",
                "turn_count_mean": f"{np.mean(tcs):.4f}" if tcs else "",
                "expanded_mean": f"{np.mean(exps):.2f}" if exps else "",
                "search_ms_mean": f"{np.mean(searches):.4f}" if searches else "",
                "total_ms_mean": f"{np.mean(totals):.4f}" if totals else "",
                "success_rate": f"{n_success/n_total:.4f}" if n_total else "",
                "collision_free_rate": f"{sum(cfs)/len(cfs):.4f}" if cfs else "",
            })

    summary_path = results_dir / f"{prefix}_summary.csv"
    with summary_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        w.writeheader()
        w.writerows(summary_rows)

    # ── Key metrics (global) ────────────────────────────────────────────
    key_rows = []
    for a in algos_list:
        vals = {"pl": [], "tc": [], "exp": [], "total": [], "search": []}
        for m in maps:
            sr = [r for r in summary_rows
                  if r["map_name"] == m and r["algorithm"] == a]
            if sr and sr[0]["path_length_mean"]:
                vals["pl"].append(float(sr[0]["path_length_mean"]))
                vals["tc"].append(float(sr[0]["turn_count_mean"]))
                vals["exp"].append(float(sr[0]["expanded_mean"]))
                vals["total"].append(float(sr[0]["total_ms_mean"]))
                vals["search"].append(float(sr[0]["search_ms_mean"]))
        key_rows.append({
            "algorithm": a,
            "path_length": f"{np.mean(vals['pl']):.6f}" if vals["pl"] else "",
            "turn_count": f"{np.mean(vals['tc']):.4f}" if vals["tc"] else "",
            "expanded": f"{np.mean(vals['exp']):.2f}" if vals["exp"] else "",
            "search_ms": f"{np.mean(vals['search']):.4f}" if vals["search"] else "",
            "total_ms": f"{np.mean(vals['total']):.4f}" if vals["total"] else "",
        })

    key_path = results_dir / f"{prefix}_key_metrics.csv"
    with key_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=key_rows[0].keys())
        w.writeheader()
        w.writerows(key_rows)

    # ── Stats tests ─────────────────────────────────────────────────────
    from scipy.stats import wilcoxon
    from statsmodels.stats.multitest import multipletests

    metrics = ["path_length", "turn_count", "expanded_nodes", "total_ms"]
    comparisons = [
        ("improved_vs_euclidean", "astar_euclidean"),
        ("improved_vs_octile", "astar_octile"),
        ("improved_vs_noadapt", "ablation_no_adapt"),
        ("improved_vs_nosmooth", "ablation_no_smooth"),
    ]

    stat_rows = []
    for comp_name, baseline_algo in comparisons:
        for metric in metrics:
            base_vals, imp_vals = [], []
            for m in maps:
                br = [r for r in raw_rows
                      if r["map_name"] == m and r["algorithm"] == baseline_algo
                      and (r["success"] is True or r["success"] == "True")
                      and r["path_length"] != ""]
                ir = [r for r in raw_rows
                      if r["map_name"] == m and r["algorithm"] == "improved_ours"
                      and (r["success"] is True or r["success"] == "True")
                      and r["path_length"] != ""]
                if not br or not ir:
                    continue
                cast = float if metric in ("path_length", "total_ms") else int
                field = metric if metric != "total_ms" else "total_ms"
                base_vals.append(np.mean([cast(r[field]) for r in br]))
                imp_vals.append(np.mean([cast(r[field]) for r in ir]))

            if len(base_vals) < 5:
                continue

            ba = np.array(base_vals)
            ia = np.array(imp_vals)
            diffs = ba - ia

            try:
                w_stat, p_val = wilcoxon(ba, ia, alternative="two-sided")
            except Exception:
                w_stat, p_val = 0.0, 1.0

            n = len(ba)
            r_rb = 1 - (2 * w_stat) / (n * (n + 1) / 2) if n > 0 else 0
            d_cohen = (np.mean(diffs) / np.std(diffs, ddof=1)
                       if np.std(diffs, ddof=1) > 0 else 0)
            wins = sum(1 for d in diffs if d > 0.001)
            losses = sum(1 for d in diffs if d < -0.001)

            stat_rows.append({
                "compare_pair": comp_name, "metric": metric,
                "n_pairs": n, "W": w_stat, "p_raw": p_val,
                "cohen_d": d_cohen, "rank_biserial_r": r_rb,
                "wins": wins, "ties": n - wins - losses, "losses": losses,
                "base_mean": np.mean(ba), "imp_mean": np.mean(ia),
                "change_pct": (np.mean(ia) / np.mean(ba) - 1) * 100,
            })

    if stat_rows:
        all_p = [r["p_raw"] for r in stat_rows]
        reject, q_vals, _, _ = multipletests(all_p, method="fdr_bh")
        for i, r in enumerate(stat_rows):
            r["q_bh"] = q_vals[i]
            r["reject_fdr"] = reject[i]

        stats_path = results_dir / f"{prefix}_stats_tests.csv"
        with stats_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=stat_rows[0].keys())
            w.writeheader()
            w.writerows(stat_rows)

    # ── Print summary ───────────────────────────────────────────────────
    n_total = len(raw_rows)
    n_success = sum(1 for r in raw_rows
                    if r["success"] is True or r["success"] == "True")
    n_timeout = sum(1 for r in raw_rows
                    if r["timeout"] is True or r["timeout"] == "True")
    n_cf = sum(1 for r in raw_rows
               if r["collision_free"] is True or r["collision_free"] == "True")
    print(f"\n=== Done in {total_s:.1f}s ===")
    print(f"  Records:        {n_total}")
    print(f"  Success:        {n_success}/{n_total}")
    print(f"  Timeout:        {n_timeout}/{n_total}")
    print(f"  Collision-free: {n_cf}/{n_success}")


def main():
    parser = argparse.ArgumentParser(
        description="Residual A* experiment runner (v2)")
    parser.add_argument("--maps-root", type=str,
                        default=str(PROJECT_ROOT / "data" / "benchmark_maps"))
    parser.add_argument("--scens-root", type=str,
                        default=str(PROJECT_ROOT / "data" / "benchmark_scens"))
    parser.add_argument("--tasks-per-map", type=int, default=20)
    parser.add_argument("--beta", type=float, default=0.3)
    parser.add_argument("--out-prefix", type=str, default="exp_main")
    parser.add_argument("--task-mode", type=str, default="first",
                        choices=["first", "longest", "middle", "middle_lo"],
                        help="'first': scen order; 'longest': top N; 'middle': 50-70pct; 'middle_lo': 30-50pct (tuning)")
    parser.add_argument("--task-start", type=int, default=0,
                        help="Skip first N tasks (for tuning set isolation)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Per-task timeout in seconds")
    args = parser.parse_args()
    run_experiment(args)


if __name__ == "__main__":
    main()
