### NoMachine打开方法
sudo systemctl stop gdm     # 关闭桌面管理器
sudo /etc/NX/nxserver --restart     #重启NoMachine服务

## 机器人底盘供电
ros2 launch turtlebot3_bringup robot.launch.py

## 机器人启动电机
ros2 service call /motor_power std_srvs/SetBool "{data: true}

## 机器人启动键盘操作
ros2 run turtlebot3_teleop teleop_keyboard

## 机器人终端打开rviz2
ros2 launch turtlebot3_bringup rviz2.launch.py

## 机器人打开slam功能
ros2 launch turtlebot3_cartographer cartographer.launch.py      #测试已通过，开扫图不用单独开rviz2

## 保存扫描地图
ros2 run nav2_map_server map_saver_cli -f ~/turtlebot3_ws/my_map --ros-args -p map_subscribe_transient_local:=true     #测试已通过

## 将扫描地图传输到windows上
用windows终端输入 scp wuhuan@10.27.62.108:~/turtlebot3_ws/my_map.pgm Users/34449/Desktop/project/turtlebot3_ws/
                 scp wuhuan@10.27.62.108:~/turtlebot3_ws/my_map.yaml Users/34449/Desktop/project/turtlebot3_ws/


目前最大问题是电池续航，其他均没问题



