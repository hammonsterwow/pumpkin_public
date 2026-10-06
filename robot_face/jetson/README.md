# Jetson LCD Face Controller

Jetson Orin Nano에서 USB Serial로 LOLIN D32(ESP32)에 표정 명령을 보내고, ESP32가 ILI9488 LCD에 표정을 그리는 모듈입니다.

실제 장비에서 Jetson → ESP32 → ILI9488 경로와 5종 표정 출력을 확인했으며 현재 `main`의 ROS2 `face_display_node`가 이 모듈을 사용합니다.

## 지원 표정

```text
NEUTRAL
SMILE
HAPPY
QUESTION
ERROR
```

## 현재 구조

```text
/robot_action.face
→ robot_controller.face_display_node
→ FaceController
→ USB Serial 115200 baud
→ LOLIN D32 / ESP32
→ TFT_eSPI
→ ILI9488 LCD
```

ESP32 펌웨어:

```text
robot_face/esp32_lcd/esp32_lcd_face.ino
```

Jetson CH340/CH341 드라이버, `brltty`, `dialout` 권한과 커널 관련 내용은 [`hardware/JETSON_ESP32_LCD_SETUP.md`](../../hardware/JETSON_ESP32_LCD_SETUP.md)를 참고합니다.

## 저장소 준비

```bash
git clone https://github.com/hammonsterwow/pumpkin_public.git
cd pumpkin_public
git switch main
```

이미 받은 저장소는:

```bash
cd ~/pumpkin_public
git switch main
git pull --ff-only
```

## Python 환경

```bash
cd ~/pumpkin_public
python3 -m venv .venv
source .venv/bin/activate
pip install -r robot_face/jetson/requirements.txt
```

필수 Python 패키지는 `pyserial`입니다.

## Serial 포트 확인

LOLIN D32를 Jetson USB에 연결한 뒤:

```bash
python3 robot_face/jetson/face_controller.py --list-ports
```

일반적으로 `/dev/ttyUSB0` 또는 `/dev/ttyACM0`로 나타납니다. 자동 탐지가 가능하므로 ESP32가 하나만 연결된 환경에서는 포트를 직접 지정할 필요가 없습니다.

권한 오류가 있으면 현재 사용자의 `dialout` 그룹 상태를 확인합니다.

## 단독 시험

전체 표정 데모:

```bash
python3 robot_face/jetson/face_controller.py --demo
```

표정 하나:

```bash
python3 robot_face/jetson/face_controller.py --face HAPPY
```

대화형 시험:

```bash
python3 robot_face/jetson/face_controller.py --interactive
```

## ROS2 통합

실물 로봇에서는 직접 `FaceController`를 반복 생성하지 않고 `face_display_node`가 하나의 controller를 유지합니다.

```text
Action Node
→ /robot_action
→ Face Display Node
→ FaceController.set_face()
→ ESP32
```

전체 로봇 실행은 저장소 루트에서:

```bash
bash scripts/run_robot_with_monitor.sh
```

얼굴 LCD만 ROS2 파이프라인에 포함할 때는 `PUMPKIN_ENABLE_FACE_DISPLAY=1`을 사용하며 기본 통합 런처에서는 활성화되어 있습니다.

## 동작 특징

- CH340/CH341, CP210x 등 USB-UART 후보 자동 탐지
- Serial 연결 후 ESP32 reset 대기
- `표정이름 + newline` 전송
- 같은 표정의 불필요한 중복 전송 방지
- 일시적인 USB 연결 실패 시 재연결 시도
- 여러 ROS2 콜백에서도 안전하도록 전송 구간 잠금

## 주의 사항

- Arduino Serial Monitor와 Jetson 프로그램을 동시에 같은 포트에 연결하지 않습니다.
- LCD 점퍼선/커넥터가 움직여 접촉 불량이 생기지 않도록 고정합니다.
- Jetson은 픽셀을 직접 그리지 않고 표정 이름만 전송합니다.
- ESP32 펌웨어의 명령 이름과 Jetson의 `Face` enum을 일치시킵니다.
- Jetson 커널을 업데이트하면 CH341 모듈 호환성을 다시 확인합니다.
