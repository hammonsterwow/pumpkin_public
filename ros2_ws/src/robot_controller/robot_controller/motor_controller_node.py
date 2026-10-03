from __future__ import annotations

import json
import threading
import time
from typing import Any, Iterable, Mapping, Tuple

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from robot_controller.arm_motion import (
    ArmMotionConfig,
    ArmMotionController,
    normalize_arm_action,
)
from robot_controller.motor_driver import (
    MockMotorDriver,
    MotorCommand,
    MotorDriver,
    PCA9685MotorDriver,
)


class MotorControllerNode(Node):
    def __init__(self) -> None:
        super().__init__('motor_controller_node')

        self.declare_parameter('backend', 'mock')
        self.declare_parameter('pca_channels', 16)
        self.declare_parameter('tilt_channel', 0)
        self.declare_parameter('pan_channel', 1)

        self.declare_parameter('pan_min', 60.0)
        self.declare_parameter('pan_max', 120.0)
        self.declare_parameter('tilt_min', 40.0)
        self.declare_parameter('tilt_max', 125.0)
        self.declare_parameter('pan_center', 90.0)
        # Physical calibration on the Pumpkin robot: 40 degrees gives the most
        # natural forward-facing neutral pose. The previous 60-degree default
        # left the head visibly pitched downward.
        self.declare_parameter('tilt_center', 40.0)
        self.declare_parameter('pan_left', 60.0)
        self.declare_parameter('pan_right', 120.0)
        # Physical nod calibration: test a moderate nod from the 40-degree
        # neutral pose by moving down to 80 degrees before returning to center.
        self.declare_parameter('nod_down', 80.0)
        self.declare_parameter('gesture_step_delay', 0.008)

        # Arm motion is opt-in until the physical arm is placed at HOME. The
        # physical demo launcher exposes this as PUMPKIN_ENABLE_ARM=true.
        self.declare_parameter('arm_enabled', False)
        self.declare_parameter('arm_pose_steps', 140)
        self.declare_parameter('arm_pose_step_delay', 0.01)
        self.declare_parameter('arm_home_steps', 220)
        self.declare_parameter('arm_home_step_delay', 0.01)
        self.declare_parameter('arm_pose_hold_seconds', 1.2)
        self.declare_parameter('arm_wave_dwell_seconds', 0.35)

        self.pan = float(self.get_parameter('pan_center').value)
        self.tilt = float(self.get_parameter('tilt_center').value)
        self.driver = self._build_driver()
        self.gesture_running = False
        self.arm_enabled = bool(self.get_parameter('arm_enabled').value)
        self._arm_lock = threading.Lock()
        self._arm_thread: threading.Thread | None = None
        self.arm_controller: ArmMotionController | None = None

        self.subscription = self.create_subscription(
            String,
            '/motor_command',
            self._on_command,
            10,
        )

        self.robot_action_subscription = self.create_subscription(
            String,
            '/robot_action',
            self._on_robot_action,
            10,
        )

        if self.arm_enabled:
            self.arm_controller = ArmMotionController(
                self._apply_arm_angles,
                config=ArmMotionConfig(
                    pose_steps=int(self.get_parameter('arm_pose_steps').value),
                    pose_step_delay=float(
                        self.get_parameter('arm_pose_step_delay').value
                    ),
                    home_steps=int(self.get_parameter('arm_home_steps').value),
                    home_step_delay=float(
                        self.get_parameter('arm_home_step_delay').value
                    ),
                    pose_hold_seconds=float(
                        self.get_parameter('arm_pose_hold_seconds').value
                    ),
                    wave_dwell_seconds=float(
                        self.get_parameter('arm_wave_dwell_seconds').value
                    ),
                ),
            )

        self.get_logger().info(
            'Motor controller started with '
            f'backend={self.get_parameter("backend").value}, '
            f'arm_enabled={self.arm_enabled}'
        )
        if self.arm_enabled:
            self.get_logger().warning(
                'Arm runtime enabled. Confirm the physical arm starts at HOME '
                'before publishing POINT_LEFT/POINT_RIGHT/UNSURE/GOODBYE_WAVE.'
            )
        self._apply()

    def _build_driver(self) -> MotorDriver:
        backend = str(self.get_parameter('backend').value).lower()
        if backend == 'mock':
            return MockMotorDriver()
        if backend == 'pca9685':
            return PCA9685MotorDriver(
                channels=int(self.get_parameter('pca_channels').value),
                tilt_channel=int(self.get_parameter('tilt_channel').value),
                pan_channel=int(self.get_parameter('pan_channel').value),
                release_on_close=not bool(
                    self.get_parameter('arm_enabled').value
                ),
            )
        raise ValueError(f'Unsupported motor backend: {backend}')

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    def _set_angles(self, pan: float, tilt: float) -> None:
        self.pan = self._clamp(
            pan,
            float(self.get_parameter('pan_min').value),
            float(self.get_parameter('pan_max').value),
        )
        self.tilt = self._clamp(
            tilt,
            float(self.get_parameter('tilt_min').value),
            float(self.get_parameter('tilt_max').value),
        )
        self._apply()

    def _apply(self) -> None:
        command = MotorCommand(pan=self.pan, tilt=self.tilt)
        self.driver.set_angles(command)
        self.get_logger().info(f'Applied pan={self.pan:.1f}, tilt={self.tilt:.1f}')

    def _move_smooth(self, target_pan: float, target_tilt: float) -> None:
        delay = max(0.0, float(self.get_parameter('gesture_step_delay').value))
        current_pan = int(round(self.pan))
        current_tilt = int(round(self.tilt))
        target_pan_i = int(round(target_pan))
        target_tilt_i = int(round(target_tilt))

        while current_pan != target_pan_i or current_tilt != target_tilt_i:
            if current_pan < target_pan_i:
                current_pan += 1
            elif current_pan > target_pan_i:
                current_pan -= 1

            if current_tilt < target_tilt_i:
                current_tilt += 1
            elif current_tilt > target_tilt_i:
                current_tilt -= 1

            self._set_angles(float(current_pan), float(current_tilt))
            if delay > 0.0:
                time.sleep(delay)

    def _run_gesture(
        self,
        name: str,
        positions: Iterable[Tuple[float, float]],
    ) -> None:
        if self.gesture_running:
            self.get_logger().warning(
                f'Ignoring gesture {name!r}: another gesture is already running.'
            )
            return

        self.gesture_running = True
        self.get_logger().info(f'Starting {name} gesture.')
        try:
            for pan, tilt in positions:
                self._move_smooth(pan, tilt)
        finally:
            self.gesture_running = False
            self.get_logger().info(f'Finished {name} gesture.')

    def _perform_nod(self) -> None:
        pan_center = float(self.get_parameter('pan_center').value)
        tilt_center = float(self.get_parameter('tilt_center').value)
        nod_down = float(self.get_parameter('nod_down').value)

        # One semantic NOD is one physical nod: center -> down -> center.
        self._run_gesture(
            'NOD',
            (
                (pan_center, tilt_center),
                (pan_center, nod_down),
                (pan_center, tilt_center),
            ),
        )

    def _perform_double_nod(self) -> None:
        pan_center = float(self.get_parameter('pan_center').value)
        tilt_center = float(self.get_parameter('tilt_center').value)
        nod_down = float(self.get_parameter('nod_down').value)

        # DOUBLE_NOD repeats the same calibrated 40 -> 80 -> 40 motion twice.
        self._run_gesture(
            'DOUBLE_NOD',
            (
                (pan_center, tilt_center),
                (pan_center, nod_down),
                (pan_center, tilt_center),
                (pan_center, nod_down),
                (pan_center, tilt_center),
            ),
        )

    def _perform_shake(self) -> None:
        pan_center = float(self.get_parameter('pan_center').value)
        tilt_center = float(self.get_parameter('tilt_center').value)
        pan_left = float(self.get_parameter('pan_left').value)
        pan_right = float(self.get_parameter('pan_right').value)

        self._run_gesture(
            'SHAKE',
            (
                (pan_center, tilt_center),
                (pan_left, tilt_center),
                (pan_center, tilt_center),
                (pan_right, tilt_center),
                (pan_center, tilt_center),
                (pan_left, tilt_center),
                (pan_center, tilt_center),
            ),
        )

    def _on_command(self, msg: String) -> None:
        raw = msg.data.strip()
        if not raw:
            return

        try:
            self._handle_command(raw)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.get_logger().error(f'Invalid motor command {raw!r}: {exc}')

    def _handle_command(self, raw: str) -> None:
        upper = raw.upper()

        if upper == 'CENTER':
            self._move_smooth(
                float(self.get_parameter('pan_center').value),
                float(self.get_parameter('tilt_center').value),
            )
            return
        if upper == 'TURN_LEFT':
            self._move_smooth(
                float(self.get_parameter('pan_left').value),
                float(self.get_parameter('tilt_center').value),
            )
            return
        if upper == 'TURN_RIGHT':
            self._move_smooth(
                float(self.get_parameter('pan_right').value),
                float(self.get_parameter('tilt_center').value),
            )
            return
        if upper == 'NOD':
            self._perform_nod()
            return
        if upper == 'DOUBLE_NOD':
            self._perform_double_nod()
            return
        if upper == 'SHAKE':
            self._perform_shake()
            return

        payload: Any = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('JSON command must be an object')

        pan = float(payload.get('pan', self.pan))
        tilt = float(payload.get('tilt', self.tilt))
        self._set_angles(pan, tilt)

    def _apply_arm_angles(self, angles: Mapping[int, float]) -> None:
        self.driver.set_servo_angles(angles)

    def _on_robot_action(self, msg: String) -> None:
        if not self.arm_enabled or self.arm_controller is None:
            return

        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().warning(f'Invalid /robot_action JSON for arm: {exc}')
            return

        if not isinstance(payload, dict):
            self.get_logger().warning('Ignoring non-object /robot_action arm payload')
            return

        action = normalize_arm_action(payload.get('arm'))
        if action is None:
            return

        with self._arm_lock:
            if self._arm_thread is not None and self._arm_thread.is_alive():
                self.get_logger().warning(
                    f'Ignoring arm action {action}: another arm gesture is running.'
                )
                return
            self._arm_thread = threading.Thread(
                target=self._run_arm_action,
                args=(action,),
                daemon=True,
                name=f'pumpkin-arm-{action.lower()}',
            )
            self._arm_thread.start()

    def _run_arm_action(self, action: str) -> None:
        self.get_logger().info(f'Starting arm action: {action}')
        try:
            if self.arm_controller is not None:
                self.arm_controller.run_action(action)
            self.get_logger().info(f'Finished arm action at HOME: {action}')
        except Exception as exc:
            self.get_logger().error(f'Arm action {action} failed: {exc}')

    def destroy_node(self) -> bool:
        with self._arm_lock:
            arm_thread = self._arm_thread
        if arm_thread is not None and arm_thread.is_alive():
            self.get_logger().warning(
                'Waiting for the active arm gesture to return HOME before shutdown.'
            )
            arm_thread.join(timeout=8.0)
        self.driver.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MotorControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
