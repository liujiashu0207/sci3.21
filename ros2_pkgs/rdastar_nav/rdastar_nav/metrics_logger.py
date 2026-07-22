"""CSV logger for real-robot experiment trials (one row per goal)."""

import csv
import os
import time
from typing import Dict

FIELDS = [
    "stamp",              # wall-clock ISO time when the goal was received
    "algorithm",
    "beta",
    "radius",
    "weight",
    "start_x", "start_y",
    "goal_x", "goal_y",
    "plan_success",
    "path_length_m",      # planned path length (meters, = cells * resolution)
    "turn_count",
    "expanded_nodes",
    "search_ms",
    "preprocess_ms",
    "postprocess_ms",
    "total_ms",
    "executed",           # whether the plan was sent to the controller
    "exec_status",        # succeeded / aborted / canceled / preempted / rejected / -
    "exec_time_s",        # wall time from FollowPath accept to result
    "exec_traj_len_m",    # actual robot trajectory length (from TF sampling)
    "track_err_mean_m",   # mean distance robot <-> planned path during execution
    "track_err_max_m",
]


class MetricsLogger:
    """Appends one CSV row per trial; creates file + header on first write."""

    def __init__(self, log_dir: str, filename_prefix: str = "real_exp"):
        self.log_dir = os.path.expanduser(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(self.log_dir, f"{filename_prefix}_{stamp}.csv")
        self._header_written = False

    def log(self, row: Dict) -> str:
        full = {k: row.get(k, "") for k in FIELDS}
        write_header = not self._header_written and not os.path.exists(self.path)
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerow(full)
        self._header_written = True
        return self.path
