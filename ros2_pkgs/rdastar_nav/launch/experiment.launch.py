"""
RD-A* real-robot experiment bringup.

Starts the minimal Nav2 subset needed for the experiment:
  map_server + AMCL (localization) + controller_server (FollowPath execution)
plus the rdastar_planner node and (optionally) RViz.

Deliberately NOT started: planner_server and bt_navigator. Global planning is
done by rdastar_planner with the paper's Python algorithms, and leaving
bt_navigator out means the RViz "Nav2 Goal" tool's /goal_pose message is
consumed only by our node.

Run on the robot PC (after `ros2 launch turtlebot3_bringup robot.launch.py`):
  ros2 launch rdastar_nav experiment.launch.py algorithm:=rdastar
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

TURTLEBOT3_MODEL = os.environ.get('TURTLEBOT3_MODEL', 'burger')
ROS_DISTRO = os.environ.get('ROS_DISTRO', 'humble')


def generate_launch_description():
    pkg_share = get_package_share_directory('rdastar_nav')

    default_map = os.path.join(pkg_share, 'maps', 'my_map.yaml')

    param_file_name = TURTLEBOT3_MODEL + '.yaml'
    tb3_nav2_share = get_package_share_directory('turtlebot3_navigation2')
    if ROS_DISTRO == 'humble':
        default_nav2_params = os.path.join(
            tb3_nav2_share, 'param', ROS_DISTRO, param_file_name)
    else:
        default_nav2_params = os.path.join(
            tb3_nav2_share, 'param', param_file_name)

    default_node_params = os.path.join(pkg_share, 'config', 'params.yaml')
    rviz_config = os.path.join(
        tb3_nav2_share, 'rviz', 'tb3_navigation2.rviz')

    map_yaml = LaunchConfiguration('map')
    nav2_params = LaunchConfiguration('params_file')
    node_params = LaunchConfiguration('node_params_file')
    algorithm = LaunchConfiguration('algorithm')
    use_sim_time = LaunchConfiguration('use_sim_time')
    use_rviz = LaunchConfiguration('use_rviz')

    return LaunchDescription([
        DeclareLaunchArgument(
            'map', default_value=default_map,
            description='Full path to the map yaml (default: scanned my_map)'),
        DeclareLaunchArgument(
            'params_file', default_value=default_nav2_params,
            description='Nav2 params (AMCL + controller), default: turtlebot3'),
        DeclareLaunchArgument(
            'node_params_file', default_value=default_node_params,
            description='rdastar_planner node params'),
        DeclareLaunchArgument(
            'algorithm', default_value='rdastar',
            description='dijkstra | astar_euclidean | astar_octile | '
                        'weighted_astar | rdastar | rdastar_no_smoothing | '
                        'octile_smoothed'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('use_rviz', default_value='true'),

        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            output='screen',
            parameters=[nav2_params,
                        {'yaml_filename': map_yaml,
                         'use_sim_time': use_sim_time}]),

        Node(
            package='nav2_amcl',
            executable='amcl',
            name='amcl',
            output='screen',
            parameters=[nav2_params, {'use_sim_time': use_sim_time}]),

        Node(
            package='nav2_controller',
            executable='controller_server',
            name='controller_server',
            output='screen',
            parameters=[nav2_params, {'use_sim_time': use_sim_time}]),

        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_experiment',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time,
                         'autostart': True,
                         'node_names': ['map_server',
                                        'amcl',
                                        'controller_server']}]),

        Node(
            package='rdastar_nav',
            executable='planner_node',
            name='rdastar_planner',
            output='screen',
            parameters=[node_params,
                        {'algorithm': algorithm,
                         'use_sim_time': use_sim_time}]),

        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': use_sim_time}],
            condition=IfCondition(use_rviz),
            output='screen'),
    ])
