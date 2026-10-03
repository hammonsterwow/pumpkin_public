from adafruit_servokit import ServoKit
import time

kit = ServoKit(channels=16)

TILT_CHANNEL = 0
CENTER = 60
DOWN = 125
STEP_DELAY = 0.008

current_angle = CENTER


def move_smooth(target_angle: int) -> None:
    global current_angle

    while current_angle != target_angle:
        current_angle += 1 if current_angle < target_angle else -1
        kit.servo[TILT_CHANNEL].angle = current_angle
        time.sleep(STEP_DELAY)

    kit.servo[TILT_CHANNEL].angle = target_angle


def perform_yes() -> None:
    move_smooth(CENTER)
    move_smooth(DOWN)
    move_smooth(CENTER)
    move_smooth(DOWN)
    move_smooth(CENTER)


if __name__ == "__main__":
    kit.servo[TILT_CHANNEL].angle = CENTER
    time.sleep(0.5)
    perform_yes()
    print("YES gesture complete")
