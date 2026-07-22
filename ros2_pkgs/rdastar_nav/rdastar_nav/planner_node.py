"""
RD-A* real-robot experiment node.

Data flow:
  /map (OccupancyGrid, from nav2 map_server)
      -> binary grid -> inflate by robot radius -> integral image (cached)
  /goal_pose (PoseStamped, from RViz "Nav2 Goal" tool)
      -> start pose from TF (map -> base_frame, provided by AMCL)
      -> run the selected paper algorithm (unmodified code from code/planners/)
      -> publish nav_msgs/Path on /rdastar/plan
      -> send FollowPath to the Nav2 controller server for execution
      -> sample TF during execution, log planning + execution metrics to CSV

The planner code is the exact Python implementation used in the paper's
benchmark experiments, so simulation and real-robot results are comparable.
"""

import math
import time

import numpy as np
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import FollowPath
from nav_msgs.msg import OccupancyGrid, Path
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from tf2_ros import Buffer, TransformListener

from . import grid_utils
from .metrics_logger import MetricsLogger
from .planners import (
    ablation_no_adaptive,
    ablation_no_smoothing,
    dijkstra_search,
    euclidean_astar,
    octile_astar,
    residual_astar,
    weighted_astar,
)
from .planners.core import make_integral_image

ALGORITHM_CHOICES = (
    "dijkstra",
    "astar_euclidean",
    "astar_octile",
    "weighted_astar",
    "rdastar",
    "rdastar_no_smoothing",
    "octile_smoothed",
)

_EXEC_STATUS_NAMES = {
    GoalStatus.STATUS_SUCCEEDED: "succeeded",
    GoalStatus.STATUS_ABORTED: "aborted",
    GoalStatus.STATUS_CANCELED: "canceled",
}


def _yaw_to_quaternion(yaw: float):
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


class RDAStarPlannerNode(Node):

    def __init__(self):
        super().__init__("rdastar_planner")

        self.declare_parameter("algorithm", "rdastar")
        self.declare_parameter("beta", 0.3)
        self.declare_parameter("radius", 5)
        self.declare_parameter("weight", 1.2)
        self.declare_parameter("robot_radius", 0.105)
        self.declare_parameter("safety_margin", 0.05)
        self.declare_parameter("occupied_thresh", 65)
        self.declare_parameter("unknown_as_obstacle", True)
        self.declare_parameter("base_frame", "base_footprint")
        self.declare_parameter("goal_topic", "/goal_pose")
        self.declare_parameter("execute", True)
        self.declare_parameter("controller_id", "")
        self.declare_parameter("goal_checker_id", "")
        self.declare_parameter("densify_step", 0.05)
        self.declare_parameter("snap_radius", 0.3)
        self.declare_parameter("log_dir", "~/rdastar_results")

        self.algorithm = self.get_parameter("algorithm").value
        if self.algorithm not in ALGORITHM_CHOICES:
            raise ValueError(
                f"Unknown algorithm '{self.algorithm}'. "
                f"Choices: {ALGORITHM_CHOICES}"
            )
        self.beta = float(self.get_parameter("beta").value)
        self.radius = int(self.get_parameter("radius").value)
        self.weight = float(self.get_parameter("weight").value)
        self.robot_radius = float(self.get_parameter("robot_radius").value)
        self.safety_margin = float(self.get_parameter("safety_margin").value)
        self.occupied_thresh = int(self.get_parameter("occupied_thresh").value)
        self.unknown_as_obstacle = bool(
            self.get_parameter("unknown_as_obstacle").value)
        self.base_frame = self.get_parameter("base_frame").value
        self.execute = bool(self.get_parameter("execute").value)
        self.controller_id = self.get_parameter("controller_id").value
        self.goal_checker_id = self.get_parameter("goal_checker_id").value
        self.densify_step = max(
            0.005, float(self.get_parameter("densify_step").value))
        self.snap_radius = float(self.get_parameter("snap_radius").value)

        self.logger = MetricsLogger(self.get_parameter("log_dir").value)

        # Cached per map message
        self._map_msg = None
        self._grid = None          # inflated binary grid the planner runs on
        self._grid_raw = None      # un-inflated grid (walls only)
        self._integral = None      # integral image of the inflated grid

        # Current execution state (None when idle)
        self._exec = None
        self._trial_seq = 0

        map_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.create_subscription(OccupancyGrid, "/map", self._on_map, map_qos)
        self.create_subscription(
            PoseStamped, self.get_parameter("goal_topic").value,
            self._on_goal, 10)

        self.plan_pub = self.create_publisher(Path, "/rdastar/plan", map_qos)
        # Also publish on /plan: the turtlebot3 RViz config already displays
        # that topic, so the path shows up without manual RViz setup.
        self.plan_pub_rviz = self.create_publisher(Path, "/plan", map_qos)
        self.inflated_pub = self.create_publisher(
            OccupancyGrid, "/rdastar/inflated_map", map_qos)

        self.tf_buffer = Buffer()
        # TF gets its own node spun in a dedicated thread: attaching the
        # listener to *this* node with spin_thread=True would steal the node
        # from the main executor, and a lookup timeout inside our callbacks
        # would starve the /tf subscriptions it is waiting on.
        self._tf_node = rclpy.create_node("rdastar_tf_listener")
        self.tf_listener = TransformListener(
            self.tf_buffer, self._tf_node, spin_thread=True)

        self.follow_client = ActionClient(self, FollowPath, "follow_path")

        self.create_timer(0.1, self._sample_execution)

        self.get_logger().info(
            f"rdastar_planner ready: algorithm={self.algorithm} "
            f"beta={self.beta} radius={self.radius} "
            f"robot_radius={self.robot_radius}+{self.safety_margin}m "
            f"execute={self.execute} log={self.logger.path}")

    # ------------------------------------------------------------------
    # Map handling
    # ------------------------------------------------------------------

    def _on_map(self, msg: OccupancyGrid):
        yaw_q = msg.info.origin.orientation
        if abs(yaw_q.z) > 1e-6 or abs(yaw_q.x) > 1e-6 or abs(yaw_q.y) > 1e-6:
            self.get_logger().warn(
                "Map origin has non-zero rotation; world<->grid conversion "
                "assumes yaw=0 and will be wrong.")
        self._map_msg = msg
        self._grid = None
        self._grid_raw = None
        self._integral = None
        self.get_logger().info(
            f"Map received: {msg.info.width}x{msg.info.height} "
            f"@ {msg.info.resolution} m/cell")

    def _ensure_grid(self) -> bool:
        """Build (once per map) the inflated planning grid + integral image."""
        if self._grid is not None:
            return True
        if self._map_msg is None:
            return False
        t0 = time.perf_counter()
        raw = grid_utils.occupancy_grid_to_planner_grid(
            self._map_msg, self.occupied_thresh, self.unknown_as_obstacle)
        res = self._map_msg.info.resolution
        inflate_cells = int(math.ceil(
            (self.robot_radius + self.safety_margin) / res))
        self._grid_raw = raw
        self._grid = grid_utils.inflate_obstacles(raw, inflate_cells)
        self._integral = make_integral_image(self._grid)
        ms = (time.perf_counter() - t0) * 1000.0
        self.get_logger().info(
            f"Planning grid built: inflation={inflate_cells} cells "
            f"({inflate_cells * res:.2f} m), prep={ms:.1f} ms")

        out = OccupancyGrid()
        out.header = self._map_msg.header
        out.info = self._map_msg.info
        out.data = (self._grid.astype(np.int8) * 100).flatten().tolist()
        self.inflated_pub.publish(out)
        return True

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def _run_algorithm(self, start, goal):
        g = self._grid
        if self.algorithm == "dijkstra":
            return dijkstra_search(g, start, goal)
        if self.algorithm == "astar_euclidean":
            return euclidean_astar(g, start, goal)
        if self.algorithm == "astar_octile":
            return octile_astar(g, start, goal)
        if self.algorithm == "weighted_astar":
            return weighted_astar(g, start, goal, weight=self.weight)
        if self.algorithm == "rdastar":
            return residual_astar(
                g, start, goal, beta=self.beta, radius=self.radius,
                use_smoothing=True, precomputed_integral=self._integral)
        if self.algorithm == "rdastar_no_smoothing":
            return ablation_no_smoothing(
                g, start, goal, beta=self.beta, radius=self.radius,
                precomputed_integral=self._integral)
        if self.algorithm == "octile_smoothed":
            return ablation_no_adaptive(g, start, goal)
        raise ValueError(self.algorithm)

    def _robot_pose(self):
        """Robot pose in the map frame from TF (AMCL), or None."""
        frame = self._map_msg.header.frame_id or "map"
        try:
            tf = self.tf_buffer.lookup_transform(
                frame, self.base_frame, Time(),
                timeout=Duration(seconds=0.2))
        except Exception as exc:  # tf2 raises several lookup error types
            self.get_logger().error(f"TF {frame}->{self.base_frame}: {exc}")
            return None
        t = tf.transform.translation
        return (t.x, t.y)

    def _on_goal(self, msg: PoseStamped):
        if not self._ensure_grid():
            self.get_logger().error("No map yet; is map_server active?")
            return
        if self._exec is not None:
            self._finish_execution("preempted")

        pose = self._robot_pose()
        if pose is None:
            return
        goal_xy, goal_q = self._goal_in_map_frame(msg)
        if goal_xy is None:
            return
        info = self._map_msg.info
        snap_cells = max(1, int(self.snap_radius / info.resolution))
        # Snapping may traverse the inflation band but never a real wall,
        # otherwise a goal clicked next to a wall could land in the next room.
        passable = self._grid_raw == 0

        start = grid_utils.nearest_free_cell(
            self._grid, grid_utils.world_to_cell(*pose, info),
            snap_cells, passable)
        goal = grid_utils.nearest_free_cell(
            self._grid, grid_utils.world_to_cell(*goal_xy, info),
            snap_cells, passable)

        self._trial_seq += 1
        row = {
            "stamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "algorithm": self.algorithm,
            "beta": self.beta,
            "radius": self.radius,
            "weight": self.weight if self.algorithm == "weighted_astar" else "",
            "start_x": round(pose[0], 3), "start_y": round(pose[1], 3),
            "goal_x": round(goal_xy[0], 3),
            "goal_y": round(goal_xy[1], 3),
            "executed": False, "exec_status": "-",
        }

        if start is None or goal is None:
            self.get_logger().error(
                "Start or goal is inside an obstacle (even after snapping) "
                "or outside the map.")
            row["plan_success"] = False
            self.logger.log(row)
            return

        result = self._run_algorithm(start, goal)
        row.update({
            "plan_success": result["success"],
            "path_length_m": round(
                result["path_length"] * info.resolution, 4),
            "turn_count": result["turn_count"],
            "expanded_nodes": result["expanded_nodes"],
            "search_ms": round(result["search_ms"], 3),
            "preprocess_ms": round(result.get("preprocess_ms", 0.0), 3),
            "postprocess_ms": round(result.get("postprocess_ms", 0.0), 3),
            "total_ms": round(result.get("total_ms", 0.0), 3),
        })

        if not result["success"]:
            self.get_logger().warn("No path found.")
            self.logger.log(row)
            return

        world_pts = [grid_utils.cell_to_world(c, info) for c in result["path"]]
        dense = grid_utils.densify_polyline(world_pts, self.densify_step)
        path_msg = self._to_path_msg(dense, goal_q)
        self.plan_pub.publish(path_msg)
        self.plan_pub_rviz.publish(path_msg)

        self.get_logger().info(
            f"[{self.algorithm}] plan ok: {row['path_length_m']} m, "
            f"{result['turn_count']} turns, "
            f"{result['expanded_nodes']} expanded, "
            f"{row['total_ms']} ms")

        if self.execute:
            self._send_follow_path(path_msg, dense, row)
        else:
            self.logger.log(row)

    def _goal_in_map_frame(self, msg: PoseStamped):
        """Return goal ((x, y), orientation) in the map frame, or (None, None).

        RViz publishes /goal_pose in its fixed frame; if that is not the map
        frame (e.g. odom), using the raw coordinates would silently plan to
        the wrong place. Planar (2D) transform is sufficient for TurtleBot3.
        """
        frame = self._map_msg.header.frame_id or "map"
        gframe = msg.header.frame_id
        x, y = msg.pose.position.x, msg.pose.position.y
        if not gframe or gframe == frame:
            return (x, y), msg.pose.orientation
        try:
            tf = self.tf_buffer.lookup_transform(
                frame, gframe, Time(), timeout=Duration(seconds=0.2))
        except Exception as exc:
            self.get_logger().error(
                f"Goal is in frame '{gframe}' and TF to '{frame}' failed: "
                f"{exc}")
            return None, None
        t, r = tf.transform.translation, tf.transform.rotation
        tf_yaw = math.atan2(2.0 * (r.w * r.z + r.x * r.y),
                            1.0 - 2.0 * (r.y * r.y + r.z * r.z))
        cos_y, sin_y = math.cos(tf_yaw), math.sin(tf_yaw)
        mx = t.x + x * cos_y - y * sin_y
        my = t.y + x * sin_y + y * cos_y
        gq = msg.pose.orientation
        goal_yaw = tf_yaw + math.atan2(2.0 * (gq.w * gq.z + gq.x * gq.y),
                                       1.0 - 2.0 * (gq.y * gq.y + gq.z * gq.z))
        _, _, qz, qw = _yaw_to_quaternion(goal_yaw)
        return (mx, my), Quaternion(x=0.0, y=0.0, z=qz, w=qw)

    def _to_path_msg(self, dense_pts, goal_q: Quaternion) -> Path:
        path = Path()
        path.header.frame_id = self._map_msg.header.frame_id or "map"
        path.header.stamp = self.get_clock().now().to_msg()
        n = len(dense_pts)
        for i, (x, y) in enumerate(dense_pts):
            p = PoseStamped()
            p.header = path.header
            p.pose.position.x = x
            p.pose.position.y = y
            if i == n - 1:
                p.pose.orientation = goal_q
            else:
                nx, ny = dense_pts[i + 1]
                _, _, qz, qw = _yaw_to_quaternion(
                    math.atan2(ny - y, nx - x))
                p.pose.orientation.z = qz
                p.pose.orientation.w = qw
            path.poses.append(p)
        return path

    # ------------------------------------------------------------------
    # Execution via Nav2 FollowPath
    # ------------------------------------------------------------------

    def _send_follow_path(self, path_msg: Path, dense_pts, row):
        if not self.follow_client.server_is_ready():
            self.get_logger().error(
                "follow_path action server not ready; is controller_server "
                "active? Logging plan-only result.")
            row["exec_status"] = "rejected"
            self.logger.log(row)
            return

        goal = FollowPath.Goal()
        goal.path = path_msg
        goal.controller_id = self.controller_id
        goal.goal_checker_id = self.goal_checker_id

        trial_id = self._trial_seq
        self._exec = {
            "id": trial_id,
            "row": row,
            "path_pts": np.asarray(dense_pts, dtype=np.float64),
            "accepted": False,
            "t_start": None,  # set on acceptance; exec_time excludes send latency
            "last_pose": None,
            "traj_len": 0.0,
            "err_sum": 0.0,
            "err_max": 0.0,
            "err_n": 0,
            "goal_handle": None,
        }
        row["executed"] = True
        future = self.follow_client.send_goal_async(goal)
        future.add_done_callback(
            lambda fut: self._on_goal_response(fut, trial_id))

    def _on_goal_response(self, future, trial_id):
        try:
            handle = future.result()
        except Exception as exc:
            self.get_logger().error(f"FollowPath send failed: {exc}")
            if self._exec is not None and self._exec["id"] == trial_id:
                self._finish_execution("error")
            return
        if self._exec is None or self._exec["id"] != trial_id:
            # This trial was preempted before the controller accepted its
            # goal; nothing else holds the handle, so cancel it here or the
            # robot keeps driving the stale path.
            if handle.accepted:
                handle.cancel_goal_async()
            return
        if not handle.accepted:
            self.get_logger().error("FollowPath goal rejected by controller.")
            self._finish_execution("rejected")
            return
        self._exec["goal_handle"] = handle
        self._exec["accepted"] = True
        self._exec["t_start"] = time.monotonic()
        result_future = handle.get_result_async()
        result_future.add_done_callback(
            lambda fut: self._on_result(fut, trial_id))

    def _on_result(self, future, trial_id):
        if self._exec is None or self._exec["id"] != trial_id:
            return  # stale result from a preempted trial
        try:
            status = future.result().status
        except Exception as exc:
            self.get_logger().error(f"FollowPath result failed: {exc}")
            self._finish_execution("error")
            return
        self._finish_execution(
            _EXEC_STATUS_NAMES.get(status, f"status_{status}"))

    def _finish_execution(self, status: str):
        ex = self._exec
        self._exec = None
        if ex is None:
            return
        if status == "preempted" and ex["goal_handle"] is not None:
            ex["goal_handle"].cancel_goal_async()
        row = ex["row"]
        row["exec_status"] = status
        if ex["t_start"] is not None:
            row["exec_time_s"] = round(time.monotonic() - ex["t_start"], 2)
        row["exec_traj_len_m"] = round(ex["traj_len"], 4)
        if ex["err_n"] > 0:
            row["track_err_mean_m"] = round(ex["err_sum"] / ex["err_n"], 4)
            row["track_err_max_m"] = round(ex["err_max"], 4)
        path = self.logger.log(row)
        self.get_logger().info(
            f"Trial finished: {status}, exec={row.get('exec_time_s', '-')} s, "
            f"traj={row['exec_traj_len_m']} m -> {path}")

    def _sample_execution(self):
        """10 Hz: accumulate actual trajectory length and tracking error."""
        if self._exec is None or not self._exec["accepted"] \
                or self._map_msg is None:
            return
        pose = self._robot_pose()
        if pose is None:
            return
        ex = self._exec
        if ex["last_pose"] is not None:
            d = math.hypot(pose[0] - ex["last_pose"][0],
                           pose[1] - ex["last_pose"][1])
            if d > 0.01:  # ignore AMCL jitter below 1 cm
                ex["traj_len"] += d
                ex["last_pose"] = pose
        else:
            ex["last_pose"] = pose

        diff = ex["path_pts"] - np.asarray(pose)
        err = float(np.min(np.hypot(diff[:, 0], diff[:, 1])))
        ex["err_sum"] += err
        ex["err_max"] = max(ex["err_max"], err)
        ex["err_n"] += 1


def main(args=None):
    rclpy.init(args=args)
    node = RDAStarPlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
