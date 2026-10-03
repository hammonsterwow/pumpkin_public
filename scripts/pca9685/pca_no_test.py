from adafruit_servokit import ServoKit
import time

kit = ServoKit(channels=16)

PAN_CHANNEL = 1
CENTER = 90
LEFT = 60
RIGHT = 120
STEP_DELAY = 0.008

current_angle = CENTER


def move_smooth(target_angle: int) -> None:
    global current_angle

    while current_angle != target_angle:
        current_angle += 1 if current_angle < target_angle else -1
        kit.servo[PAN_CHANNEL].angle = current_angle
        time.sleep(STEP_DELAY)

    kit.servo[PAN_CHANNEL].angle = target_angle


def perform_no() -> None:
    move_smooth(CENTER)
    move_smooth(LEFT)
    move_smooth(CENTER)
    move_smooth(RIGHT)
    move_smooth(CENTER)
    move_smooth(LEFT)
    move_smooth(CENTER)


if __name__ == "__main__":
    kit.servo[PAN_CHANNEL].angle = CENTER
    time.sleep(0.5)
    perform_no()
    print("NO gesture complete")
