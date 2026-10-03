# Motor controller

This branch adds a ROS 2 pan/tilt motor controller designed to work before the MG996 servos and power wiring are ready.

## Architecture

- `/motor_command` (`std_msgs/String`) is the stable integration interface.
- `motor_controller_node.py` owns angle limits and command parsing.
- `motor_driver.py` isolates the hardware backend.
- `mock` backend logs movement without hardware.
- `serial` backend sends one compact command to an Arduino:

```text
SET,<pan>,<tilt>\n
```

The ROS node therefore does not need to be rewritten when hardware is connected.

## Build

```bash
cd ~/pumpkin
git switch feat/motor-controller
cd ros2_ws
colcon build --packages-select robot_controller
source install/setup.bash
```

## Hardware-free test

Start the controller with the default mock backend:

```bash
ros2 run robot_controller motor_controller_node
```

In another terminal:

```bash
source ~/pumpkin/ros2_ws/install/setup.bash
ros2 topic pub --once /motor_command std_msgs/msg/String "{data: 'LEFT'}"
ros2 topic pub --once /motor_command std_msgs/msg/String "{data: 'RIGHT'}"
ros2 topic pub --once /motor_command std_msgs/msg/String "{data: 'UP'}"
ros2 topic pub --once /motor_command std_msgs/msg/String "{data: 'DOWN'}"
ros2 topic pub --once /motor_command std_msgs/msg/String "{data: 'CENTER'}"
```

Direct angle command:

```bash
ros2 topic pub --once /motor_command std_msgs/msg/String \
  "{data: '{\"pan\": 120, \"tilt\": 70}'}"
```

Expected output includes:

```text
[MOCK MOTOR] pan=120.0, tilt=70.0
```

## Serial backend for later hardware testing

Install serial support if needed:

```bash
sudo apt install python3-serial
```

Run with Arduino connected:

```bash
ros2 run robot_controller motor_controller_node --ros-args \
  -p backend:=serial \
  -p serial_port:=/dev/ttyACM0 \
  -p baudrate:=115200
```

## Parameters

```text
backend       mock or serial
serial_port   /dev/ttyACM0
baudrate      115200
pan_min       20.0
pan_max       160.0
tilt_min      40.0
tilt_max      130.0
pan_center    90.0
tilt_center   85.0
step          5.0
```

Start with conservative limits when the 3D-printed assembly is powered for the first time. Adjust parameters rather than editing the node.

## Future integration

The decision or action node should only publish commands to `/motor_command`. It should not access Arduino pins, PWM values, or serial ports directly. The only hardware-specific work remaining is Arduino firmware that accepts the `SET,<pan>,<tilt>` protocol and drives the two MG996 servos.
