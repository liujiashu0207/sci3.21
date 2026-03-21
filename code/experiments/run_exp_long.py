#!/usr/bin/env python3
"""
Supplementary experiment: long paths (longest top-20 tasks).

Usage:
    python code/experiments/run_exp_long.py --phase core --timeout 30
    python code/experiments/run_exp_long.py --phase dijkstra --timeout 10
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "code"))
sys.path.insert(0, str(PROJECT_ROOT / "code" / "experiments"))

from planners.core import (
    line_of_sight, make_integral_image, obstacle_ratio,
)
from planners.algorithms import (
    ablation_no_adaptive, ablation_no_smoothing,
    dijkstra_search, euclidean_astar, octile_astar,
    residual_astar, weighted_astar,
)
from utils.map_loader import load_grid_map
from run_experiment import MAP_LIST, parse_scen, check_collision_free, RAW_FIELDS

BETA = 0.3
TASKS_PER_MAP = 20
TASK_MODE = "longest"
TASK_SOURCE = "longest_top20"


def get_algos(grid, integral, phase):
    """Return algorithm list based on phase."""
    if phase == "core":
        return [
            ("astar_euclidean",    lambda s, g: euclidean_astar(grid, s, g)),
            ("astar_octile",       lambda s, g: octile_astar(grid, s, g)),
            ("weighted_1.2",       lambda s, g: weighted_astar(grid, s, g, weight=1.2)),
            ("improved_ours",      lambda s, g: residual_astar(
                grid, s, g, beta=BETA, precomputed_integral=integral)),
            ("ablation_no_adapt",  lambda s, g: ablation_no_adaptive(grid, s, g)),
            ("ablation_no_smooth", lambda s, g: ablation_no_smoothing(
                grid, s, g, beta=BETA, precomputed_integral=integral)),
        ]
    else:  # dijkstra
        return [
            ("dijkstra", lambda s, g: dijkstra_search(grid, s, g)),
        ]


def run_phase(phase, timeout_s):
    maps_root = PROJECT_ROOT / "data" / "benchmark_maps"
    scens_root = PROJECT_ROOT / "data" / "benchmark_scens"
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)

    prefix = f"exp_long_{phase}"
    raw_rows = []
    manifest_rows = []
    t_global = time.perf_counter()

    for mi, (mtype, map_rel, scen_rel) in enumerate(MAP_LIST):
        map_path = maps_root / map_rel
        scen_path = scens_root / scen_rel
        if not map_path.exists() or not scen_path.exists():
            continue

        grid = load_grid_map(map_path)
        h_map, w_map = grid.shape
        obs = obstacle_ratio(grid)
        integral = make_integral_image(grid)
        mname = map_path.stem
        tasks = parse_scen(scen_path, TASKS_PER_MAP, TASK_MODE)
        algos = get_algos(grid, integral, phase)

        # Manifest (only write once per phase)
        if phase == "core":
            for ti, (s, g, opt) in enumerate(tasks):
                manifest_rows.append({
                    "map_type": mtype, "map_name": mname,
                    "map_size": f"{h_map}x{w_map}",
                    "obstacle_ratio": f"{obs:.4f}",
                    "task_id": ti,
                    "start": f"{s[0]},{s[1]}",
                    "goal": f"{g[0]},{g[1]}",
                    "optimal_length": f"{opt:.6f}",
                    "task_source": TASK_SOURCE,
                })

        t_map = time.perf_counter()
        for ti, (start, goal, opt_len) in enumerate(tasks):
            for aname, afunc in algos:
                t_start = time.perf_counter()
                res = afunc(start, goal)
                elapsed_s = time.perf_counter() - t_start
                is_timeout = elapsed_s > timeout_s

                if res["success"] and not is_timeout:
                    cf = check_collision_free(grid, res["path"])
                    capped = res["total_ms"]
                    raw_rows.append({
                        "run_id": prefix, "map_type": mtype,
                        "map_name": mname, "map_size": f"{h_map}x{w_map}",
                        "obstacle_ratio": f"{obs:.4f}", "task_id": ti,
                        "start": f"{start[0]},{start[1]}",
                        "goal": f"{goal[0]},{goal[1]}",
                        "optimal_length": f"{opt_len:.6f}",
                        "algorithm": aname,
                        "success": True, "timeout": False,
                        "path_length": f"{res['path_length']:.6f}",
                        "turn_count": res["turn_count"],
                        "expanded_nodes": res["expanded_nodes"],
                        "preprocess_ms": f"{res['preprocess_ms']:.4f}",
                        "search_ms": f"{res['search_ms']:.4f}",
                        "postprocess_ms": f"{res['postprocess_ms']:.4f}",
                        "total_ms": f"{res['total_ms']:.4f}",
                        "capped_total_ms": f"{capped:.4f}",
                        "collision_free": cf,
                    })
                else:
                    # Timeout or failed
                    raw_rows.append({
                        "run_id": prefix, "map_type": mtype,
                        "map_name": mname, "map_size": f"{h_map}x{w_map}",
                        "obstacle_ratio": f"{obs:.4f}", "task_id": ti,
                        "start": f"{start[0]},{start[1]}",
                        "goal": f"{goal[0]},{goal[1]}",
                        "optimal_length": f"{opt_len:.6f}",
                        "algorithm": aname,
                        "success": res["success"] if not is_timeout else False,
                        "timeout": True,
                        "path_length": "", "turn_count": "",
                        "expanded_nodes": "",
                        "preprocess_ms": "",
                        "search_ms": "",
                        "postprocess_ms": "",
                        "total_ms": f"{timeout_s * 1000:.4f}",
                        "capped_total_ms": f"{timeout_s * 1000:.4f}",
                        "collision_free": False,
                    })

        elapsed = time.perf_counter() - t_map
        n_algos = len(algos)
        print(f"  [{mi+1}/15] {mname:<22} 20 tasks x {n_algos} algos ({elapsed:.1f}s)")

    total_s = time.perf_counter() - t_global

    # Write raw records
    raw_path = results_dir / f"{prefix}_raw_records.csv"
    with raw_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RAW_FIELDS)
        w.writeheader()
        w.writerows(raw_rows)

    # Write manifest (core only)
    if manifest_rows:
        mf_path = results_dir / f"{prefix}_task_manifest.csv"
        with mf_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=manifest_rows[0].keys())
            w.writeheader()
            w.writerows(manifest_rows)

    # Summary
    maps = sorted(set(r["map_name"] for r in raw_rows))
    algos_list = sorted(set(r["algorithm"] for r in raw_rows))
    summary_rows = []
    for m in maps:
        for a in algos_list:
            mr = [r for r in raw_rows if r["map_name"] == m and r["algorithm"] == a]
            n_total = len(mr)
            n_success = sum(1 for r in mr if r["success"] is True or r["success"] == "True")
            n_timeout = sum(1 for r in mr if r["timeout"] is True or r["timeout"] == "True")
            ok = [r for r in mr if (r["success"] is True or r["success"] == "True")
                  and r["path_length"] != ""]
            if ok:
                pls = [float(r["path_length"]) for r in ok]
                tcs = [int(r["turn_count"]) for r in ok]
                exps = [int(r["expanded_nodes"]) for r in ok]
                tots = [float(r["total_ms"]) for r in ok]
                searches = [float(r["search_ms"]) for r in ok]
                cfs = [r["collision_free"] is True or r["collision_free"] == "True" for r in ok]
            else:
                pls = tcs = exps = tots = searches = cfs = []
            summary_rows.append({
                "map_name": m, "algorithm": a, "n_total": n_total,
                "n_success": n_success, "n_timeout": n_timeout,
                "timeout_rate": f"{n_timeout/n_total:.4f}" if n_total else "",
                "path_length_mean": f"{np.mean(pls):.6f}" if pls else "",
                "turn_count_mean": f"{np.mean(tcs):.4f}" if tcs else "",
                "expanded_mean": f"{np.mean(exps):.2f}" if exps else "",
                "search_ms_mean": f"{np.mean(searches):.4f}" if searches else "",
                "total_ms_mean": f"{np.mean(tots):.4f}" if tots else "",
                "success_rate": f"{n_success/n_total:.4f}" if n_total else "",
                "collision_free_rate": f"{sum(cfs)/len(cfs):.4f}" if cfs else "",
            })

    sum_path = results_dir / f"{prefix}_summary.csv"
    with sum_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        w.writeheader()
        w.writerows(summary_rows)

    # Stats tests (core only)
    if phase == "core":
        from scipy.stats import wilcoxon
        from statsmodels.stats.multitest import multipletests

        metrics_map = {
            "path_length": ("path_length", float),
            "turn_count": ("turn_count", int),
            "expanded_nodes": ("expanded_nodes", int),
            "total_ms": ("total_ms", float),
            "search_ms": ("search_ms", float),
        }
        comparisons = [
            ("improved_vs_euclidean", "astar_euclidean"),
            ("improved_vs_octile", "astar_octile"),
            ("improved_vs_noadapt", "ablation_no_adapt"),
            ("improved_vs_nosmooth", "ablation_no_smooth"),
        ]
        stat_rows = []
        for comp_name, baseline in comparisons:
            for metric, (field, cast) in metrics_map.items():
                base_vals, imp_vals = [], []
                for m in maps:
                    br = [r for r in raw_rows if r["map_name"] == m
                          and r["algorithm"] == baseline
                          and (r["success"] is True or r["success"] == "True")
                          and r["path_length"] != ""]
                    ir = [r for r in raw_rows if r["map_name"] == m
                          and r["algorithm"] == "improved_ours"
                          and (r["success"] is True or r["success"] == "True")
                          and r["path_length"] != ""]
                    if br and ir:
                        base_vals.append(np.mean([cast(r[field]) for r in br]))
                        imp_vals.append(np.mean([cast(r[field]) for r in ir]))
                if len(base_vals) < 5:
                    continue
                ba, ia = np.array(base_vals), np.array(imp_vals)
                diffs = ba - ia
                if np.all(np.abs(diffs) < 1e-10):
                    stat_rows.append({
                        "compare_pair": comp_name, "metric": metric,
                        "n_pairs": len(ba), "W": "N/A", "p_raw": "N/A",
                        "cohen_d": 0.0, "rank_biserial_r": "N/A",
                        "wins": 0, "ties": len(ba), "losses": 0,
                        "base_mean": np.mean(ba), "imp_mean": np.mean(ia),
                        "change_pct": 0.0, "q_bh": "N/A", "reject_fdr": False,
                    })
                    continue
                try:
                    w_stat, p_val = wilcoxon(ba, ia, alternative="two-sided")
                except:
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
                    "q_bh": None, "reject_fdr": None,
                })

        if stat_rows:
            valid_idx = [i for i, r in enumerate(stat_rows) if isinstance(r["p_raw"], float)]
            if valid_idx:
                valid_p = [stat_rows[i]["p_raw"] for i in valid_idx]
                reject, q_vals, _, _ = multipletests(valid_p, method="fdr_bh")
                for j, i in enumerate(valid_idx):
                    stat_rows[i]["q_bh"] = q_vals[j]
                    stat_rows[i]["reject_fdr"] = reject[j]

            stats_path = results_dir / f"{prefix}_stats_tests.csv"
            with stats_path.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=stat_rows[0].keys())
                w.writeheader()
                w.writerows(stat_rows)

    # Dijkstra timeout_by_map
    if phase == "dijkstra":
        timeout_rows = []
        for m in maps:
            mr = [r for r in raw_rows if r["map_name"] == m]
            n_total = len(mr)
            n_timeout = sum(1 for r in mr if r["timeout"] is True or r["timeout"] == "True")
            capped = [float(r["capped_total_ms"]) for r in mr]
            timeout_rows.append({
                "map_name": m, "n_total": n_total, "n_timeout": n_timeout,
                "timeout_rate": f"{n_timeout/n_total:.4f}",
                "capped_total_ms_mean": f"{np.mean(capped):.4f}",
            })
        to_path = results_dir / "exp_long_dijkstra_timeout_by_map.csv"
        with to_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=timeout_rows[0].keys())
            w.writeheader()
            w.writerows(timeout_rows)

    # Print summary
    n_total = len(raw_rows)
    n_success = sum(1 for r in raw_rows if r["success"] is True or r["success"] == "True")
    n_timeout = sum(1 for r in raw_rows if r["timeout"] is True or r["timeout"] == "True")
    n_cf = sum(1 for r in raw_rows if r["collision_free"] is True or r["collision_free"] == "True")
    print(f"\n=== {prefix} Done in {total_s:.1f}s ===")
    print(f"  Records:        {n_total}")
    print(f"  Success:        {n_success}/{n_total}")
    print(f"  Timeout:        {n_timeout}/{n_total}")
    print(f"  Collision-free: {n_cf}/{n_success if n_success else 1}")


def main():
    parser = argparse.ArgumentParser(description="exp_long runner")
    parser.add_argument("--phase", choices=["core", "dijkstra"], required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    run_phase(args.phase, args.timeout)


if __name__ == "__main__":
    main()
