from __future__ import annotations

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


FACE_TO_CODE = {
    'NEUTRAL': '1',
    'SMILE': '2',
    'HAPPY': '3',
    'QUESTION': '4',
    'ERROR': '5',
}


class FaceControllerNode(Node):
    def __init__(self) -> None:
        super().__init__('face_controller_node')

        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('topic', '/robot_action')

        try:
            import serial
        except ImportError as exc:
            raise RuntimeError(
                'pyserial is required for face_controller_node. Install it with: '
                'python3 -m pip install pyserial'
            ) from exc

        self._serial = serial.Serial(
            port=str(self.get_parameter('serial_port').value),
            baudrate=int(self.get_parameter('baudrate').value),
            timeout=1.0,
        )

        self.subscription = self.create_subscription(
            String,
            str(self.get_parameter('topic').value),
            self._on_robot_action,
            10,
        )

        self.get_logger().info(
            f'Face controller started on {self.get_parameter("serial_port").value}'
        )

    def _on_robot_action(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.get_logger().error(f'Invalid /robot_action JSON: {exc}')
            return

        face = str(payload.get('face') or 'NEUTRAL').upper()
        code = FACE_TO_CODE.get(face)
        if code is None:
            self.get_logger().warning(f'Unknown face {face!r}; using NEUTRAL')
            face = 'NEUTRAL'
            code = FACE_TO_CODE[face]

        self._serial.write(f'{code}\n'.encode('ascii'))
        self._serial.flush()
        self.get_logger().info(f'Face {face} -> ESP code {code}')

    def destroy_node(self) -> bool:
        if self._serial.is_open:
            self._serial.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FaceControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
