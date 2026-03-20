#!/usr/bin/env python3
"""
Reproducible experiment script for Residual-Driven Adaptive Weighted A*.

Usage:
    python code/experiments/run_experiment.py
    python code/experiments/run_experiment.py --tasks-per-map 30 --beta 0.2 --out-prefix exp_test

One command, zero manual steps. Outputs all CSVs + figures.
"""

import argparse
import csv
import math
import os
import sys
import time
from pathlib import Path
from statistics import mean, stdev

import numpy as np

# Resolve project root
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

# ── Map / Scen definitions ──────────────────────────────────────────────────

MAP_LIST = [
    ("dao",    "dao-map/arena.map",              "dao/arena.map.scen"),
    ("dao",    "dao-map/arena2.map",             "dao/arena2.map.scen"),
    ("dao",    "dao-map/brc000d.map",            "dao/brc000d.map.scen"),
    ("dao",    "dao-map/brc100d.map",            "dao/brc100d.map.scen"),
    ("dao",    "dao-map/brc101d.map",            "dao/brc101d.map.scen"),
    ("street", "street-map/Berlin_0_256.map",    "street/Berlin_0_256.map.scen"),
    ("street", "street-map/Berlin_0_512.map",    "street/Berlin_0_512.map.scen"),
    ("street", "street-map/Berlin_0_1024.map",   "street/Berlin_0_1024.map.scen"),
    ("street", "street-map/Berlin_1_256.map",    "street/Berlin_1_256.map.scen"),
    ("street", "street-map/Berlin_1_1024.map",   "street/Berlin_1_1024.map.scen"),
    ("wc3",   "wc3-map/battleground.map",        "wc3maps512/battleground.map.scen"),
    ("wc3",   "wc3-map/blastedlands.map",        "wc3maps512/blastedlands.map.scen"),
    ("wc3",   "wc3-map/bloodvenomfalls.map",     "wc3maps512/bloodvenomfalls.map.scen"),
    ("wc3",   "wc3-map/bootybay.map",            "wc3maps512/bootybay.map.scen"),
    ("wc3",   "wc3-map/darkforest.map",          "wc3maps512/darkforest.map.scen"),
]


def parse_scen(scen_path: Path, n: int, mode: str = "first") -> list:
    """
    Parse MovingAI .scen file.
    mode="first": take first n non-trivial tasks (default, strict scen order).
    mode="longest": take n tasks with largest optimal_length.
    Returns list of ((start_row,start_col), (goal_row,goal_col), optimal_length).
    """
    all_tasks = []
    with scen_path.open("r", encoding="utf-8") as f:
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


def check_collision_free(grid, path) -> bool:
    """Full collision check: every point free + every segment line-of-sight."""
    for p in path:
        if grid[p[0], p[1]] == 1:
            return False
    for i in range(1, len(path)):
        if not line_of_sight(grid, path[i - 1], path[i]):
            return False
    return True


RAW_FIELDS = [
    "run_id", "map_type", "map_name", "map_size", "obstacle_ratio",
    "task_id", "start", "goal", "optimal_length", "algorithm",
    "success", "path_length", "turn_count", "expanded_nodes",
    "runtime_ms", "collision_free",
]


def run_experiment(args):
    """Main experiment loop."""
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

    print(f"=== Experiment: {prefix} ===")
    print(f"  Beta={beta}, Tasks/map={tasks_per_map}, Mode={task_mode}")
    print(f"  Maps root: {maps_root}")
    print(f"  Scens root: {scens_root}")
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
        tasks = parse_scen(scen_path, tasks_per_map, mode=task_mode)

        # Write manifest entries
        for ti, (s, g, opt) in enumerate(tasks):
            manifest_rows.append({
                "map_type": mtype, "map_name": mname,
                "map_size": f"{h_map}x{w_map}",
                "obstacle_ratio": f"{obs:.4f}", "task_id": ti,
                "start": f"{s[0]},{s[1]}", "goal": f"{g[0]},{g[1]}",
                "optimal_length": f"{opt:.6f}",
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
                res = afunc(start, goal)
                cf = check_collision_free(grid, res["path"]) if res["success"] else False
                raw_rows.append({
                    "run_id": prefix,
                    "map_type": mtype,
                    "map_name": mname,
                    "map_size": f"{h_map}x{w_map}",
                    "obstacle_ratio": f"{obs:.4f}",
                    "task_id": ti,
                    "start": f"{start[0]},{start[1]}",
                    "goal": f"{goal[0]},{goal[1]}",
                    "optimal_length": f"{opt_len:.6f}",
                    "algorithm": aname,
                    "success": res["success"],
                    "path_length": f"{res['path_length']:.6f}" if res["success"] else "",
                    "turn_count": res["turn_count"] if res["success"] else "",
                    "expanded_nodes": res["expanded_nodes"],
                    "runtime_ms": f"{res['runtime_ms']:.4f}",
                    "collision_free": cf,
                })

        elapsed = time.perf_counter() - t_map
        print(f"  [{mi+1}/15] {mname:<20} {len(tasks)} tasks × 7 algos ({elapsed:.1f}s)")

    total_s = time.perf_counter() - t_global

    # ── Write raw records ───────────────────────────────────────────────
    raw_path = results_dir / f"{prefix}_raw_records.csv"
    with raw_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RAW_FIELDS)
        w.writeheader()
        w.writerows(raw_rows)

    # ── Write task manifest ─────────────────────────────────────────────
    manifest_path = results_dir / f"{prefix}_task_manifest.csv"
    with manifest_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=manifest_rows[0].keys())
        w.writeheader()
        w.writerows(manifest_rows)

    # ── Summary & key metrics ───────────────────────────────────────────
    maps = sorted(set(r["map_name"] for r in raw_rows))
    algos_list = sorted(set(r["algorithm"] for r in raw_rows))

    summary_rows = []
    for m in maps:
        for a in algos_list:
            mr = [r for r in raw_rows if r["map_name"] == m and r["algorithm"] == a and r["success"]]
            if not mr:
                continue
            pls = [float(r["path_length"]) for r in mr]
            tcs = [int(r["turn_count"]) for r in mr]
            exps = [int(r["expanded_nodes"]) for r in mr]
            rts = [float(r["runtime_ms"]) for r in mr]
            cfs = [r["collision_free"] for r in mr]
            summary_rows.append({
                "map_name": m, "algorithm": a, "n": len(mr),
                "path_length_mean": np.mean(pls), "path_length_std": np.std(pls),
                "turn_count_mean": np.mean(tcs), "turn_count_std": np.std(tcs),
                "expanded_mean": np.mean(exps), "expanded_std": np.std(exps),
                "runtime_mean": np.mean(rts), "runtime_std": np.std(rts),
                "success_rate": 1.0,
                "collision_free_rate": sum(1 for c in cfs if c) / len(cfs),
            })

    summary_path = results_dir / f"{prefix}_summary.csv"
    with summary_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        w.writeheader()
        w.writerows(summary_rows)

    # Key metrics (per-map means → global)
    key_rows = []
    for a in algos_list:
        map_vals = {}
        for m in maps:
            mr = [r for r in raw_rows if r["map_name"] == m and r["algorithm"] == a and r["success"]]
            if not mr:
                continue
            map_vals[m] = {
                "pl": np.mean([float(r["path_length"]) for r in mr]),
                "tc": np.mean([int(r["turn_count"]) for r in mr]),
                "exp": np.mean([int(r["expanded_nodes"]) for r in mr]),
                "rt": np.mean([float(r["runtime_ms"]) for r in mr]),
            }
        key_rows.append({
            "algorithm": a,
            "path_length": np.mean([v["pl"] for v in map_vals.values()]),
            "turn_count": np.mean([v["tc"] for v in map_vals.values()]),
            "expanded": np.mean([v["exp"] for v in map_vals.values()]),
            "runtime_ms": np.mean([v["rt"] for v in map_vals.values()]),
        })

    key_path = results_dir / f"{prefix}_key_metrics.csv"
    with key_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=key_rows[0].keys())
        w.writeheader()
        w.writerows(key_rows)

    # ── Statistical tests ───────────────────────────────────────────────
    from scipy.stats import wilcoxon
    from statsmodels.stats.multitest import multipletests

    metrics = ["path_length", "turn_count", "expanded_nodes", "runtime_ms"]
    comparisons = [
        ("improved_vs_euclidean", "astar_euclidean"),
        ("improved_vs_octile", "astar_octile"),
    ]

    stat_rows = []
    for comp_name, baseline_algo in comparisons:
        for metric in metrics:
            base_vals, imp_vals = [], []
            for m in maps:
                br = [r for r in raw_rows if r["map_name"] == m and r["algorithm"] == baseline_algo and r["success"]]
                ir = [r for r in raw_rows if r["map_name"] == m and r["algorithm"] == "improved_ours" and r["success"]]
                cast = float if metric in ("path_length", "runtime_ms") else int
                base_vals.append(np.mean([cast(r[metric]) for r in br]))
                imp_vals.append(np.mean([cast(r[metric]) for r in ir]))

            ba = np.array(base_vals)
            ia = np.array(imp_vals)
            diffs = ba - ia

            try:
                w_stat, p_val = wilcoxon(ba, ia, alternative="two-sided")
            except Exception:
                w_stat, p_val = 0.0, 1.0

            n = len(maps)
            r_rb = 1 - (2 * w_stat) / (n * (n + 1) / 2) if n > 0 else 0
            d_cohen = np.mean(diffs) / np.std(diffs, ddof=1) if np.std(diffs, ddof=1) > 0 else 0
            wins = sum(1 for d in diffs if d > 0.001)
            losses = sum(1 for d in diffs if d < -0.001)

            stat_rows.append({
                "comparison": comp_name, "metric": metric,
                "W": w_stat, "p_value": p_val,
                "cohen_d": d_cohen, "rank_biserial_r": r_rb,
                "wins": wins, "ties": n - wins - losses, "losses": losses,
                "base_mean": np.mean(ba), "imp_mean": np.mean(ia),
                "change_pct": (np.mean(ia) / np.mean(ba) - 1) * 100,
            })

    # BH-FDR
    all_p = [r["p_value"] for r in stat_rows]
    reject, q_vals, _, _ = multipletests(all_p, method="fdr_bh")
    for i, r in enumerate(stat_rows):
        r["q_value"] = q_vals[i]
        r["reject_fdr"] = reject[i]

    stats_path = results_dir / f"{prefix}_stats_tests.csv"
    with stats_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=stat_rows[0].keys())
        w.writeheader()
        w.writerows(stat_rows)

    # ── Figures ─────────────────────────────────────────────────────────
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    algos_order = ["astar_euclidean", "astar_octile", "weighted_1.2",
                   "improved_ours", "ablation_no_adapt", "ablation_no_smooth"]
    algo_labels = ["A*(Euc)", "A*(Oct)", "WA*(1.2)",
                   "Ours", "Abl-NoAdapt", "Abl-NoSmooth"]
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#F44336", "#9C27B0", "#795548"]

    def get_map_means(metric_name, cast=float):
        result = {}
        for a in algos_order:
            vals = []
            for m in maps:
                mr = [r for r in raw_rows if r["map_name"] == m and r["algorithm"] == a and r["success"]]
                vals.append(np.mean([cast(r[metric_name]) for r in mr]))
            result[a] = vals
        return result

    x = np.arange(len(maps))
    bw = 0.12

    for metric, ylabel, cast_fn in [
        ("expanded_nodes", "Expanded Nodes", int),
        ("path_length", "Path Length", float),
        ("turn_count", "Turn Count", int),
    ]:
        fig, ax = plt.subplots(figsize=(14, 5))
        data = get_map_means(metric, cast_fn)
        for i, (a, label, c) in enumerate(zip(algos_order, algo_labels, colors)):
            ax.bar(x + (i - 2.5) * bw, data[a], bw, label=label, color=c, alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels([m[:12] for m in maps], rotation=45, ha="right", fontsize=8)
        ax.set_ylabel(ylabel)
        ax.set_title(f"{ylabel} — {prefix} (15 maps × {tasks_per_map} tasks, β={beta})")
        ax.legend(fontsize=8, ncol=3)
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        fig_path = figures_dir / f"{prefix}_{metric}.png"
        plt.savefig(str(fig_path), dpi=200)
        plt.close()

    # Ablation figure
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    abl_algos = ["astar_octile", "ablation_no_adapt", "ablation_no_smooth", "improved_ours"]
    abl_labels = ["A*(Octile)", "NoAdaptive", "NoSmooth", "Full(Ours)"]
    abl_colors = ["#4CAF50", "#9C27B0", "#795548", "#F44336"]
    for ax, (met, yl, cf) in zip(axes, [
        ("expanded_nodes", "Expanded Nodes", int),
        ("path_length", "Path Length", float),
        ("turn_count", "Turn Count", int),
    ]):
        data = get_map_means(met, cf)
        gm = [np.mean(data[a]) for a in abl_algos]
        bars = ax.bar(abl_labels, gm, color=abl_colors, alpha=0.85)
        ax.set_ylabel(yl)
        for bar, val in zip(bars, gm):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle(f"Ablation Study — {prefix}", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(str(figures_dir / f"{prefix}_ablation.png"), dpi=200)
    plt.close()

    # ── Print summary ───────────────────────────────────────────────────
    n_total = len(raw_rows)
    n_success = sum(1 for r in raw_rows if r["success"])
    n_cf = sum(1 for r in raw_rows if r["collision_free"])
    print(f"\n=== Done in {total_s:.1f}s ===")
    print(f"  Records:        {n_total}")
    print(f"  Success:        {n_success}/{n_total}")
    print(f"  Collision-free: {n_cf}/{n_success}")
    print(f"\n  Output files:")
    for p in [raw_path, manifest_path, summary_path, key_path, stats_path]:
        print(f"    {p.relative_to(PROJECT_ROOT)}")
    print(f"    figures/{prefix}_expanded_nodes.png")
    print(f"    figures/{prefix}_path_length.png")
    print(f"    figures/{prefix}_turn_count.png")
    print(f"    figures/{prefix}_ablation.png")


def main():
    parser = argparse.ArgumentParser(description="Residual A* experiment runner")
    parser.add_argument("--maps-root", type=str,
                        default=str(PROJECT_ROOT / "data" / "benchmark_maps"))
    parser.add_argument("--scens-root", type=str,
                        default=str(PROJECT_ROOT / "data" / "benchmark_scens"))
    parser.add_argument("--tasks-per-map", type=int, default=50)
    parser.add_argument("--beta", type=float, default=0.3)
    parser.add_argument("--out-prefix", type=str, default="exp_v1")
    parser.add_argument("--task-mode", type=str, default="first",
                        choices=["first", "longest"],
                        help="'first': first N scen tasks; 'longest': N longest tasks")
    parser.add_argument("--disable-jump-like", action="store_true", default=True,
                        help="Jump-like expansion disabled (always true, compatibility placeholder)")
    parser.add_argument("--strict-scen", action="store_true", default=True,
                        help="Use fixed scen tasks (always true)")
    args = parser.parse_args()
    run_experiment(args)


if __name__ == "__main__":
    main()
