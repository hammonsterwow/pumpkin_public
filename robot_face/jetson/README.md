# Jetson LCD Face Controller

Jetson Orin Nano에서 USB Serial을 통해 LOLIN D32(ESP32)에 표정 명령을 보내는 코드입니다.

2026-08-06 실제 장비에서 Jetson → ESP32 → ILI9488 LCD 전체 표정 데모를 확인했으며, 현재 코드는 `main` 브랜치를 기준으로 사용합니다.

LCD 그림은 ESP32가 직접 그립니다. Jetson은 아래 다섯 개의 표정 이름만 전송합니다.

```text
NEUTRAL
SMILE
HAPPY
QUESTION
ERROR
```

현재 구조는 다음과 같습니다.

```text
Jetson Python
  -> USB Serial (115200 baud, 명령 + 줄바꿈)
LOLIN D32 / ESP32
  -> TFT_eSPI
ILI9488 LCD
```

ESP32 펌웨어는 다음 파일을 사용합니다.

```text
robot_face/esp32_lcd/esp32_lcd_face.ino
```

Jetson CH340 드라이버 설치, `brltty` 충돌, `dialout` 권한과 커널 업데이트 주의사항은 다음 문서를 참고합니다.

```text
hardware/JETSON_ESP32_LCD_SETUP.md
```

## 1. Jetson에 저장소 받기

```bash
git clone https://github.com/yulllee0829/pumpkin.git
cd pumpkin
git switch main
```

이미 저장소를 받은 상태라면 다음처럼 갱신합니다.

```bash
cd ~/pumpkin
git fetch origin
git switch main
git pull
```

## 2. Python 환경 준비

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r robot_face/jetson/requirements.txt
```

필요한 Python 패키지는 `pyserial` 하나입니다.

## 3. ESP32 연결 확인

LOLIN D32를 Jetson USB 포트에 연결한 뒤 다음 명령을 실행합니다.

```bash
python3 robot_face/jetson/face_controller.py --list-ports
```

보통 다음 중 하나로 나타납니다.

```text
/dev/ttyUSB0
/dev/ttyACM0
```

자동 탐지가 되므로 ESP32가 하나만 연결되어 있다면 포트 번호를 직접 적지 않아도 됩니다.

권한 오류가 발생하면 현재 사용자를 `dialout` 그룹에 추가합니다.

```bash
sudo usermod -aG dialout $USER
```

명령 실행 후 로그아웃·로그인하거나 Jetson을 재부팅해야 권한이 적용됩니다.

`lsusb`에 CH340이 보이는데 `/dev/ttyUSB0`이 없거나, 장치가 생성 직후 사라지면 `hardware/JETSON_ESP32_LCD_SETUP.md`의 CH341 모듈과 `brltty` 점검 절차를 따릅니다.

## 4. 전체 표정 데모

```bash
python3 robot_face/jetson/face_controller.py --demo
```

다음 순서로 출력되고 마지막에 기본 표정으로 돌아갑니다.

```text
NEUTRAL -> SMILE -> HAPPY -> QUESTION -> ERROR -> NEUTRAL
```

표정 사이 시간을 2초로 하고 두 번 반복하려면 다음처럼 실행합니다.

```bash
python3 robot_face/jetson/face_controller.py --demo --delay 2 --repeat 2
```

자동 포트 탐지가 실패하면 포트를 직접 지정합니다.

```bash
python3 robot_face/jetson/face_controller.py \
  --port /dev/ttyUSB0 \
  --demo
```

## 5. 표정 하나 출력

```bash
python3 robot_face/jetson/face_controller.py --face HAPPY
```

다른 예시는 다음과 같습니다.

```bash
python3 robot_face/jetson/face_controller.py --face NEUTRAL
python3 robot_face/jetson/face_controller.py --face SMILE
python3 robot_face/jetson/face_controller.py --face QUESTION
python3 robot_face/jetson/face_controller.py --face ERROR
```

## 6. 대화형 시험

```bash
python3 robot_face/jetson/face_controller.py --interactive
```

실행 후 아래 명령을 입력할 수 있습니다.

```text
face> HAPPY
face> QUESTION
face> DEMO
face> QUIT
```

대화형 모드는 Serial 연결을 계속 유지하므로 여러 표정을 연속 시험할 때 가장 안정적입니다.

## 7. 주문 흐름 코드에서 사용

`FaceController`를 한 번 생성한 뒤 로봇 프로그램이 종료될 때까지 유지하는 방식으로 사용합니다.

```python
from robot_face.jetson import Face, FaceController

face_controller = FaceController(port="auto")

# 주문 대기
face_controller.set_face(Face.NEUTRAL)

# 사용자의 주문을 정상적으로 인식
face_controller.set_face(Face.SMILE)

# 누락 정보가 있어 다시 질문
face_controller.set_face(Face.QUESTION)

# 주문 확인 완료
face_controller.set_face(Face.HAPPY)

# 처리 실패 또는 지원하지 않는 요청
face_controller.set_face(Face.ERROR)
```

향후 FSM이나 ROS2 노드가 표정 값을 결정하면 해당 출력값을 그대로 전달할 수 있습니다.

```python
def apply_dialogue_output(output: dict, face_controller: FaceController) -> None:
    # 예: output["face"] == "QUESTION"
    face_controller.set_face(output.get("face", "NEUTRAL"))
```

표정 정책은 주문 FSM에서 정하고, 이 모듈은 표정 이름을 ESP32로 안전하게 전달하는 역할만 담당합니다.

## 8. 코드 동작 특징

- ESP32 후보 포트 자동 탐지
- `/dev/ttyUSB*`, `/dev/ttyACM*`, CH340, CH341, CP210x 계열 인식
- Serial 연결 시 ESP32가 재부팅될 수 있어 기본 2초 대기
- 전송 형식은 `표정이름 + \n`
- 같은 표정의 불필요한 중복 전송 방지
- USB 연결이 잠시 끊긴 경우 한 번 재연결 후 재전송
- 여러 스레드나 ROS2 콜백에서 사용할 수 있도록 전송 구간 잠금 처리

## 9. 주의 사항

- Arduino IDE 시리얼 모니터와 Jetson 프로그램을 동시에 열지 않습니다. 한 Serial 포트는 한 프로그램만 사용해야 합니다.
- LCD 점퍼선이 흔들리면 백라이트만 켜지고 그림이 사라질 수 있으므로 실제 로봇 장착 전 커넥터를 고정합니다.
- Jetson 코드는 LCD 픽셀을 직접 그리지 않습니다. 실제 표정 모양은 ESP32 펌웨어에 보존됩니다.
- ESP32 펌웨어의 명령 이름과 Jetson의 `Face` enum은 항상 동일하게 유지해야 합니다.
- 현재 Jetson의 `ch341.ko`는 커널 `5.15.185-tegra`용입니다. 커널 업데이트 후에는 모듈 호환성을 다시 확인합니다.
