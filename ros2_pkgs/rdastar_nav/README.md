# rdastar_nav — RD-A* 实机实验包

用论文里的**原版 Python 算法**(`code/planners/` 的拷贝)在 TurtleBot3 实机上做全局规划,
执行交给 Nav2 controller server(FollowPath / DWB),定位用 AMCL。
每次实验自动记录"规划指标 + 执行指标"到 CSV,格式与 `results/` 的仿真实验对齐。

架构:不启动 Nav2 的 planner_server 和 bt_navigator,RViz 里点的目标点
(`/goal_pose`)只会被本包的 `rdastar_planner` 节点消费,不会触发默认规划器。

## 一、部署到服务器(首次)

```bash
# 在 Windows/Mac 上把包传到服务器(或直接在服务器上 git pull 本仓库)
scp -r ros2_pkgs/rdastar_nav wuhuan@10.27.62.108:~/turtlebot3_ws/src/

# 在服务器上编译
cd ~/turtlebot3_ws
colcon build --packages-select rdastar_nav --symlink-install
source install/setup.bash
```

依赖只有 rclpy / nav2 组件 / numpy,Humble 桌面版全都自带,无需额外安装。

## 二、跑一次实验

```bash
# 终端1:机器人底盘(已测试通过的流程)
ros2 launch turtlebot3_bringup robot.launch.py

# 终端2:实验 bringup(map_server + AMCL + controller + 规划节点 + RViz)
export TURTLEBOT3_MODEL=burger        # 按实际型号,waffle 则同时改 robot_radius
ros2 launch rdastar_nav experiment.launch.py algorithm:=rdastar
```

RViz 里的操作:

1. 用 **2D Pose Estimate** 给 AMCL 设初始位姿(必须先做,否则 TF 不通);
2. 用 **Nav2 Goal** 点目标点 → 节点规划并驱动机器人执行,结束后自动写一行 CSV。
   规划路径自动显示(节点同时发布 `/plan`,tb3 的 RViz 配置自带该显示);
   想看膨胀后的规划栅格可 Add → By topic → `/rdastar/inflated_map`。

结果在服务器 `~/rdastar_results/real_exp_<时间戳>.csv`。

## 三、算法对比实验

同一组起终点,换算法各跑一遍(controller、地图、定位完全相同,天然公平):

```bash
ros2 launch rdastar_nav experiment.launch.py algorithm:=rdastar          # 本文方法
ros2 launch rdastar_nav experiment.launch.py algorithm:=astar_octile     # 基线
ros2 launch rdastar_nav experiment.launch.py algorithm:=weighted_astar   # 固定权重
ros2 launch rdastar_nav experiment.launch.py algorithm:=octile_smoothed  # 消融:无自适应
ros2 launch rdastar_nav experiment.launch.py algorithm:=rdastar_no_smoothing  # 消融:无平滑
```

只想比规划、不动机器人(省电池):在 `config/params.yaml` 里把 `execute: false`。

CSV 字段:规划侧 `path_length_m / turn_count / expanded_nodes / search_ms / total_ms`,
执行侧 `exec_status / exec_time_s / exec_traj_len_m / track_err_mean_m / track_err_max_m`。

## 四、常用参数(config/params.yaml)

| 参数 | 默认 | 说明 |
|------|------|------|
| `algorithm` | rdastar | 7 选 1,与论文算法配置一一对应 |
| `beta` / `radius` | 0.3 / 5 | RD-A* 参数,与论文标定一致 |
| `robot_radius` | 0.105 | **burger=0.105,waffle=0.22,换车必改** |
| `safety_margin` | 0.05 | 额外安全膨胀(米) |
| `execute` | true | false = 只规划不执行 |
| `map`(launch 参数) | 包内 my_map.yaml | 换新扫的地图时传绝对路径 |

## 五、注意事项

- 规划在**膨胀后**的栅格上进行(机器人半径 + 安全余量),未知区域按障碍处理;
  ρ_local 也在膨胀后栅格上算,和论文"规划所见即障碍"的口径一致。
- 地图 origin 必须无旋转(map_saver_cli 保存的图都满足)。
- `my_map.yaml` 的 `free_thresh: 0.25` 会让 pgm 里的未知灰色(205,occ≈0.196)
  被 map_server 当作**自由**加载(`unknown_as_obstacle` 只拦截值为 -1 的格子)。
  如果发现路径穿过没扫到的区域,把 yaml 里 `free_thresh` 改成 `0.196` 再启动。
- 机器人紧贴墙时起点会落进膨胀带,节点会自动就近吸附到自由格(≤0.3 m)。
- 换了新地图记得同步更新包内 `maps/`,或 launch 时传 `map:=/绝对路径/xxx.yaml`。
- `rdastar_nav/planners/` 是 `code/planners/` 的拷贝;若算法代码有改动,
  重新拷贝一份保持同源(实验声明"实机与仿真同一实现"依赖这一点)。
