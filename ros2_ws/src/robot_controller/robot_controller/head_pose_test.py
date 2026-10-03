from __future__ import annotations

import argparse
import time

import cv2

from .head_gesture_frame_estimator import HeadGestureFrameEstimator
from .head_gesture_recognizer import HeadGestureRecognizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test head-pose and head-gesture recognition.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        raise RuntimeError(
            f"Failed to open camera {args.camera}. Try --camera 1 or another index."
        )

    estimator = HeadGestureFrameEstimator(
        calibration_duration_sec=0.45,
        calibration_min_samples=6,
    )
    recognizer = HeadGestureRecognizer()
    last_gesture = HeadGestureRecognizer.NONE
    last_gesture_time = 0.0
    previous_status = None

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("Failed to read a camera frame.")
                break

            now = time.monotonic()
            result = estimator.estimate(frame)
            status = estimator.status

            if status != previous_status:
                print(f"Head-pose status: {status}")
                previous_status = status
                if status != HeadGestureFrameEstimator.READY:
                    recognizer.reset()

            if result is not None and estimator.is_calibrated:
                gesture = recognizer.add_sample(
                    now,
                    result.pitch,
                    result.yaw,
                    nose_rel_x=result.nose_rel_x,
                    nose_rel_y=result.nose_rel_y,
                )
                if gesture != HeadGestureRecognizer.NONE:
                    last_gesture = gesture
                    last_gesture_time = now
                    print(
                        f"Detected {gesture}: pitch={result.pitch:.1f}, "
                        f"yaw={result.yaw:.1f}, nose_x={result.nose_rel_x:.3f}, "
                        f"nose_y={result.nose_rel_y:.3f}"
                    )

                lines = (
                    f"Pitch: {result.pitch:6.1f}",
                    f"Yaw:   {result.yaw:6.1f}",
                    f"Roll:  {result.roll:6.1f}",
                    f"Nose X:{result.nose_rel_x:7.3f}",
                    f"Nose Y:{result.nose_rel_y:7.3f}",
                )
                for index, text in enumerate(lines):
                    cv2.putText(
                        frame,
                        text,
                        (20, 70 + index * 35),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.72,
                        (0, 255, 0) if index < 3 else (0, 220, 220),
                        2,
                    )

            if status == HeadGestureFrameEstimator.CALIBRATING:
                progress = int(estimator.calibration_progress * 100)
                cv2.putText(
                    frame,
                    f"Stay still: calibrating {progress}%",
                    (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (0, 255, 255),
                    2,
                )
            elif status == HeadGestureFrameEstimator.FACE_NOT_DETECTED:
                cv2.putText(
                    frame,
                    "Face not detected",
                    (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

            status_color = (
                (0, 255, 0)
                if status == HeadGestureFrameEstimator.READY
                else (0, 255, 255)
                if status == HeadGestureFrameEstimator.CALIBRATING
                else (0, 0, 255)
            )
            cv2.putText(
                frame,
                f"Status: {status}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                status_color,
                2,
            )

            display_gesture = (
                last_gesture
                if now - last_gesture_time <= 1.0
                else HeadGestureRecognizer.NONE
            )
            cv2.putText(
                frame,
                f"Gesture: {display_gesture}",
                (20, 260),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 0),
                2,
            )
            cv2.putText(
                frame,
                "R: restart calibration  Q: quit",
                (20, frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
            )

            cv2.imshow("Pumpkin Head Gesture Test", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                estimator.restart_calibration()
                recognizer.reset()
                last_gesture = HeadGestureRecognizer.NONE
                last_gesture_time = 0.0
                print("Automatic neutral-pose calibration restarted.")
    finally:
        estimator.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
