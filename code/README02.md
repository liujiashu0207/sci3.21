# TurtleBot3 Burger 官方导航启动流程（当前实机环境）

更新时间：2026-09-26。适用于树莓派 4B 与本地电脑均为 Ubuntu 22.04、ROS 2 Humble，机器人为 Burger、雷达为 LDS-01 的当前环境。

本文记录现有官方导航的启动、建图、限速及 RViz 修复环境。命令中的“本地电脑”指 `xiapilang` 的电脑；“树莓派”指 SSH 登录后的 `wuhuan` 主机。不要在 SSH 终端里启动本地导航或 RViz。

## 1. 当前设备分工与文件位置

| 位置 | 运行内容 |
| --- | --- |
| 树莓派 | `turtlebot3_bringup`：底盘、雷达、里程计及机器人相关 TF |
| 本地电脑 | 建图或导航、RViz、键盘遥控、地图保存 |
| 局域网 | ROS 2 DDS 传输传感器数据和速度指令；SSH 用于远程执行命令 |

当前本地实际使用的工作空间和配置：

| 用途 | 路径 |
| --- | --- |
| TurtleBot3 工作空间 | `/home/xiapilang/turtlebot3_ws` |
| 本地环境配置 | `/home/xiapilang/.bashrc` |
| 地图 | `/home/xiapilang/map.yaml`、`/home/xiapilang/map.pgm` |
| Humble Burger 导航参数 | `/home/xiapilang/turtlebot3_ws/src/turtlebot3/turtlebot3_navigation2/param/humble/burger.yaml` |
| 导航 RViz 配置 | `/home/xiapilang/turtlebot3_ws/src/turtlebot3/turtlebot3_navigation2/rviz/tb3_navigation2.rviz` |
| TF2 修复工作空间 | `/home/xiapilang/tb3_tf2_fix_ws` |

本 README 虽然保存在 `sci3.21/turtlebot3`，目前启动命令使用的是 `~/turtlebot3_ws/install` 中的包。修改 `sci3.21/turtlebot3` 里的同名参数，不会自动改变当前导航。

## 2. 电池重新上电后的启动顺序

### 2.1 给机器人上电并连接树莓派

等待树莓派启动、连接 Wi-Fi。本地电脑与树莓派应在可互通的局域网内，网络不能隔离设备间通信。

本地电脑终端 A：

```bash
ssh 大创
```

当前 SSH 别名指向 `wuhuan@10.24.28.191`。如果重启后 IP 改变，应先确认树莓派的新 IP，再更新 `~/.ssh/config` 中的 `HostName`。SSH 连通只代表可以远程登录，仍需检查 ROS 话题数据。

### 2.2 在树莓派启动底盘和雷达

以下命令在终端 A 的 SSH 会话中执行：

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash

export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-01
export ROS_DOMAIN_ID=30
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0

ros2 launch turtlebot3_bringup robot.launch.py
```

树莓派工作空间若不在 `~/turtlebot3_ws`，应将 source 路径替换为实际位置。保留该终端运行。若已配置开机启动且 bringup 正常运行，不要重复启动第二份。

### 2.3 本地加载环境并检查数据

另开本地电脑终端 B：

```bash
source ~/.bashrc

echo "$TURTLEBOT3_MODEL"
echo "$ROS_DOMAIN_ID"
echo "$RMW_IMPLEMENTATION"
echo "$ROS_LOCALHOST_ONLY"

ros2 pkg prefix turtlebot3_navigation2
ros2 pkg prefix tf2
ros2 pkg prefix tf2_ros
```

前四项应依次为 `burger`、`30`、`rmw_fastrtps_cpp`、`0`。包路径应分别位于：

```text
/home/xiapilang/turtlebot3_ws/install/turtlebot3_navigation2
/home/xiapilang/tb3_tf2_fix_ws/install/tf2
/home/xiapilang/tb3_tf2_fix_ws/install/tf2_ros
```

检查实时数据：

```bash
ros2 topic list
ros2 topic echo /scan sensor_msgs/msg/LaserScan --no-arr --qos-reliability best_effort --once
ros2 topic echo /odom nav_msgs/msg/Odometry --no-arr --once
```

应能看到 `/scan`、`/odom`、`/imu`、`/tf`、`/tf_static`、`/cmd_vel` 等话题，并实际收到雷达和里程计消息。只有话题名称不能证明实时数据正常到达。

若修改过 DDS 环境变量但话题发现仍异常，可在本地重新启动 CLI daemon 后再查：

```bash
ros2 daemon stop
ros2 daemon start
ros2 topic list
```

两端 `ROS_DOMAIN_ID` 必须一致；当前均为 `30`，这个数字本身没有特殊含义。排查跨机通信时也要检查双方时间同步状态，尤其是出现 TF 时间外推错误时。

## 3. 使用已有地图进行官方导航

### 3.1 本地启动导航

先结束本地 Cartographer 建图和键盘遥控，保留树莓派 bringup。不要同时运行两套定位/导航系统。

本地电脑终端 B：

```bash
source ~/.bashrc
ls -l "$HOME/map.yaml" "$HOME/map.pgm"

ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  map:="$HOME/map.yaml" \
  use_sim_time:=false
```

该启动文件会同时打开 RViz，不需要再启动一个 `rviz2`。真实机器人使用 `use_sim_time:=false`。

`map.yaml` 中的 `image: map.pgm` 指向同目录的图片。更换地图时，传入对应 YAML 的绝对路径，并保证它引用的图片存在。

如果需要明确指定当前限速配置，可使用：

```bash
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  map:="$HOME/map.yaml" \
  params_file:="$HOME/turtlebot3_ws/src/turtlebot3/turtlebot3_navigation2/param/humble/burger.yaml" \
  use_sim_time:=false
```

以上两条启动命令选一条运行。

### 3.2 在 RViz 设置初始位置

1. 等待地图出现，确认 Fixed Frame 为 `map`。
2. 点击 **2D Pose Estimate**。
3. 在地图上机器人实际所在的位置按下鼠标，沿真实车头方向拖动后松开。
4. 检查雷达点与地图墙面是否基本重合；偏差明显时重新设置初始位姿。

如果需要通过轻微移动辅助定位，可单独启动键盘遥控，缓慢移动后按空格停止并退出遥控，再发送导航目标。

### 3.3 发送导航目标

确认定位正常、导航节点完成激活后，使用官方导航 RViz 中的 **Nav2 Goal** 工具，在可通行区域点击并拖动设置目标朝向。

首次选取附近的空旷位置，观察规划路径、雷达和机器人实际运动。取消任务使用 Navigation 2 面板的 **Cancel**。导航运行期间，不要同时用键盘遥控发布速度。

## 4. 当前导航线速度限制

当前实际使用的 `param/humble/burger.yaml` 中已设置：

```yaml
controller_server:
  ros__parameters:
    FollowPath:
      plugin: "dwb_core::DWBLocalPlanner"
      max_vel_x: 0.10
      max_speed_xy: 0.10
```

这是现有完整配置中的片段，不要用它覆盖整个 YAML。数值单位为 m/s，`0.10` 即约 10 cm/s；这是控制器规划的速度上限，实际速度取决于路径和障碍物等条件。

导航启动后，在另一个本地终端检查实际加载值：

```bash
source ~/.bashrc
ros2 param get /controller_server FollowPath.max_vel_x
ros2 param get /controller_server FollowPath.max_speed_xy
```

两项应均为 `0.1`。今后需要进一步降低时，可将这两项一起调整为例如 `0.08`，然后重新启动本地导航。当前安装目录里的该 YAML 是源码文件的符号链接，因此修改此配置不需要重新编译。

这两项限制针对导航 DWB 控制器，不是整个机器人的统一速度限制；键盘遥控速度单独控制。

## 5. 需要重新建图时

已有适用地图时跳过本节。建图时结束本地导航，保留树莓派 bringup。

本地电脑终端 B，启动建图：

```bash
source ~/.bashrc
ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=false
```

本地电脑终端 C，启动遥控：

```bash
source ~/.bashrc
ros2 run turtlebot3_teleop teleop_keyboard
```

按 `w/x` 增减线速度，`a/d` 调整角速度，空格或 `s` 停车。松开按键不等于停车。慢速探索环境，避免快速旋转造成地图重影。

完成后先停车，保持建图节点运行。在本地终端 D 保存地图：

```bash
source ~/.bashrc
ros2 run nav2_map_server map_saver_cli -f "$HOME/map"
```

此命令保存 `~/map.yaml` 和 `~/map.pgm`；若需要保留旧图，请先改用其他文件名前缀，例如 `"$HOME/map_new"`，导航时也使用对应的 `map_new.yaml`。

确认保存成功后，退出遥控和 Cartographer，再按第 3 节启动导航。

## 6. RViz 卡死修复如何保持生效

之前的线程回溯指向 TF2 等待变换时的锁顺序死锁。当前已在独立工作空间构建官方 geometry2 `0.25.24` 中的 `tf2` 和 `tf2_ros`，并通过本地 `~/.bashrc` 加载；你已反馈实际运行不再卡死。

现有环境加载顺序为：

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source ~/tb3_tf2_fix_ws/install/local_setup.bash
```

日常只需在本地终端执行 `source ~/.bashrc`。以上顺序用于核对，不需要重复追加到 `.bashrc`。

- 保留 `~/tb3_tf2_fix_ws` 的源码、build 和 install；当前使用符号链接安装，不要只移动或保留 install。
- 加载其他工作空间后如覆盖了 TF2 路径，应最后重新 source 该修复工作空间的 `install/local_setup.bash`。
- 环境变化只影响之后启动的程序，已运行的 RViz/Nav2 必须退出后重启。
- 本修复不是开机自动启动导航；每次上电仍按本文启动。
- 修复来源与验证记录见 `/home/xiapilang/tb3_tf2_fix_ws/README.md`。

当前 RViz 导航配置也已移除与本机 Humble 不兼容的 Selector/Docking 面板项。若又出现整个窗口无响应，先检查本终端 `ros2 pkg prefix tf2_ros` 是否指向修复工作空间，再保留日志和线程回溯排查。

## 7. 常见问题快速定位

| 现象 | 首先检查 |
| --- | --- |
| `/scan` 显示 Unknown topic | 树莓派 bringup 是否运行、LDS-01 驱动是否启动、双方 DDS 环境是否一致 |
| 有话题名称但收不到数据 | 用带消息类型和 best-effort QoS 的 `/scan` echo 实际验证，再检查网络隔离 |
| `Package 'turtlebot3_teleop' not found` | 本地执行 `source ~/.bashrc`，再用 `ros2 pkg prefix turtlebot3_teleop` 检查；仍不存在则需要另行安装或构建该包 |
| 地图显示但机器人定位不对 | 用 2D Pose Estimate 重设位置和朝向，检查雷达与地图是否对齐 |
| 导航速度仍快 | 查询运行中 controller_server 的两个限速参数，确认启动加载的是正确工作空间 |
| RViz 整窗卡死 | 检查 TF2 修复覆盖层是否生效；不要只依据 CPU 占用判断原因 |
| TF 时间外推或数据时间异常 | 检查两台机器的系统时钟、时间同步及 use_sim_time 配置 |
| Cartographer 出现 `Dropped 1 earlier points` | 该日志来自雷达点时间排序，不等同于网络丢包；需结合连续 `/scan` 时间戳和地图效果判断 |

## 8. 结束使用

1. 取消导航目标，确认机器人停止；若正在遥控，先按空格停车。
2. 在本地导航或建图、遥控终端按 `Ctrl+C` 结束程序。
3. 在树莓派 bringup 终端按 `Ctrl+C`。
4. 在树莓派执行 `sudo shutdown -h now`，等待关机后再断开电池供电。

## 9. 参考来源

- [ROBOTIS 官方 Bringup](https://emanual.robotis.com/docs/en/platform/turtlebot3/bringup/)
- [ROBOTIS 官方 SLAM](https://emanual.robotis.com/docs/en/platform/turtlebot3/slam/)
- [ROBOTIS 官方 Navigation](https://emanual.robotis.com/docs/en/platform/turtlebot3/navigation/)
- [geometry2 官方 Humble 死锁修复 PR #990](https://github.com/ros2/geometry2/pull/990)

官方页面包含多个 ROS 版本，阅读时应选择 Humble。本文的路径、限速值和修复环境以当前电脑的实际配置为准。
