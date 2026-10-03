# Jetson–ESP32 얼굴 LCD 연동 가이드

Jetson Orin Nano에서 USB Serial로 LOLIN D32(ESP32)에 표정 명령을 보내고, ESP32가 3.5인치 ILI9488 LCD에 표정을 출력하는 구성의 **팀 공유용 설치·점검 문서**입니다.

## 최종 확인 상태

2026-08-06 실제 장비에서 아래 전체 경로의 동작을 확인했습니다.

```text
Jetson Python
  → USB Serial 115200 baud
LOLIN D32 / ESP32
  → TFT_eSPI + SPI
3.5-inch ILI9488 LCD
```

확인한 표정 명령:

```text
NEUTRAL
SMILE
HAPPY
QUESTION
ERROR
```

메인 브랜치 파일:

```text
robot_face/jetson/face_controller.py
robot_face/jetson/README.md
robot_face/jetson/requirements.txt
robot_face/esp32_lcd/esp32_lcd_face.ino
```

Jetson 제어 코드는 `feat/jetson-lcd-face-controller`에서 실제 장비 시험을 완료한 뒤 PR #61로 `main`에 병합했습니다.

## 시험한 하드웨어·OS

| 항목 | 확인값 |
|---|---|
| 메인 컴퓨터 | Jetson Orin Nano |
| Jetson Linux | R36.5.0 |
| 커널 | `5.15.185-tegra` |
| ESP32 보드 | WeMos LOLIN D32 |
| USB Serial 칩 | CH340, USB ID `1a86:7523` |
| 얼굴 LCD | 3.5-inch ILI9488 SPI TFT |
| Python 통신 속도 | 115200 baud |

## 처음 막혔던 원인

ESP32를 연결하면 `lsusb`에는 다음 장치가 보였지만 `/dev/ttyUSB0`은 생성되지 않았습니다.

```text
ID 1a86:7523 QinHeng Electronics CH340 serial converter
```

확인 결과 현재 NVIDIA 커널 설정은 다음과 같았습니다.

```text
# CONFIG_USB_SERIAL_CH341 is not set
```

CH340 장치는 Linux의 `ch341` 드라이버가 담당합니다. 해당 Jetson 커널에는 이 드라이버가 기본 포함되어 있지 않아, 동일한 R36.5.0 커널 소스와 현재 설치된 커널 헤더로 `ch341.ko`를 직접 빌드했습니다.

또한 모듈을 로드한 뒤에는 Ubuntu의 점자 디스플레이 서비스 `brltty`가 CH340 장치를 가로채 `/dev/ttyUSB0`을 즉시 끊는 문제가 발생했습니다. `brltty`를 중지·비활성화한 뒤 장치가 정상 유지되었습니다.

마지막으로 일반 사용자에게 Serial 포트 권한이 없어 `Permission denied`가 발생했으며, `pumpkin` 사용자를 `dialout` 그룹에 추가하고 다시 로그인하여 해결했습니다.

## 현재 Jetson에서 확인할 영구 설정

### 1. CH341 모듈 설치 위치

```bash
modinfo ch341 | grep -E 'filename|vermagic'
```

정상 예시:

```text
filename: /lib/modules/5.15.185-tegra/extra/ch341.ko
vermagic: 5.15.185-tegra ...
```

### 2. 부팅 시 모듈 자동 로드

```bash
cat /etc/modules-load.d/ch341.conf
```

정상 출력:

```text
ch341
```

### 3. brltty 충돌 방지

```bash
systemctl is-enabled brltty.service brltty-udev.service 2>/dev/null
```

이 로봇에서 점자 디스플레이를 사용하지 않으므로 두 서비스는 `masked`, `disabled` 또는 설치 제거 상태여야 합니다.

서비스가 다시 활성화되어 CH340을 가로채면 다음 명령으로 중지·차단합니다.

```bash
sudo systemctl stop brltty.service 2>/dev/null
sudo systemctl stop brltty-udev.service 2>/dev/null
sudo systemctl disable brltty.service 2>/dev/null
sudo systemctl disable brltty-udev.service 2>/dev/null
sudo systemctl mask brltty.service 2>/dev/null
sudo systemctl mask brltty-udev.service 2>/dev/null
```

### 4. Serial 포트 사용자 권한

```bash
groups
```

출력에 `dialout`이 포함되어야 합니다. 없다면:

```bash
sudo usermod -aG dialout $USER
```

그룹 변경 후에는 현재 SSH 세션을 종료하고 다시 로그인하거나 Jetson을 재부팅해야 적용됩니다.

## 평소 실행 방법

ESP32를 Jetson USB 포트에 연결한 뒤:

```bash
cd ~/pumpkin
git switch main
git pull
source .venv/bin/activate
```

가상환경이 아직 없다면 한 번만 다음을 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r robot_face/jetson/requirements.txt
```

Serial 포트 확인:

```bash
python3 robot_face/jetson/face_controller.py --list-ports
```

정상 예시:

```text
/dev/ttyUSB0 - USB Serial VID:PID=1A86:7523
```

전체 표정 데모:

```bash
python3 robot_face/jetson/face_controller.py --demo
```

표정 하나 출력:

```bash
python3 robot_face/jetson/face_controller.py --face HAPPY
```

대화형 시험:

```bash
python3 robot_face/jetson/face_controller.py --interactive
```

## 빠른 문제 진단

### `No serial ports found`

```bash
lsusb | grep -Ei '1a86|ch340|ch341'
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
lsmod | grep -E 'ch341|usbserial'
```

- `lsusb`에도 없으면 USB 포트·데이터 케이블·ESP32 전원을 확인합니다.
- `lsusb`에는 있는데 `/dev/ttyUSB0`이 없으면 CH341 모듈 또는 `brltty` 충돌을 확인합니다.

### `/dev/ttyUSB0`이 생겼다가 사라짐

```bash
sudo dmesg | grep -Ei 'ch341|ttyUSB|brltty' | tail -n 30
```

아래 로그가 보이면 `brltty` 충돌입니다.

```text
interface 0 claimed by ch341 while 'brltty' sets config #1
ch341-uart converter now disconnected from ttyUSB0
```

### `Permission denied: '/dev/ttyUSB0'`

```bash
ls -l /dev/ttyUSB0
groups
```

장치 소유 그룹이 `dialout`인데 현재 사용자가 해당 그룹에 없다면 사용자를 추가하고 다시 로그인합니다.

### 터미널은 정상인데 LCD 화면이 바뀌지 않음

1. ESP32에 `robot_face/esp32_lcd/esp32_lcd_face.ino`가 업로드되어 있는지 확인합니다.
2. Arduino Serial Monitor 등 다른 프로그램이 같은 포트를 열고 있지 않은지 확인합니다.
3. LCD 점퍼선의 VCC, GND, CS, RESET, DC, MOSI, SCK 접촉을 확인합니다.
4. 백라이트만 켜져 있어도 LCD 전원 또는 SPI 선이 끊겼을 수 있습니다.

## 커널 업데이트 주의

현재 `ch341.ko`는 정확히 `5.15.185-tegra`용으로 빌드했습니다. Jetson의 커널이 업데이트되면 기존 모듈이 새 커널과 맞지 않아 다시 로드되지 않을 수 있습니다.

커널 업데이트 전후에는 반드시 다음을 확인합니다.

```bash
uname -r
modinfo ch341 | grep vermagic
```

두 버전이 다르면 새 커널의 헤더와 동일한 Jetson Linux 소스로 CH341 모듈을 다시 빌드해야 합니다. 다른 버전의 `.ko` 파일을 강제로 로드하지 않습니다.

직접 빌드한 외부 모듈을 로드할 때 다음 경고가 나타날 수 있습니다.

```text
module verification failed: signature and/or required key missing - tainting kernel
```

현재 시험에서는 이 경고 이후 모듈이 정상 등록되고 `/dev/ttyUSB0`이 생성되었습니다. 경고 자체보다 뒤이어 `registered new interface driver ch341`와 `attached to ttyUSB0`이 나타나는지를 확인합니다.

## 팀 작업 원칙

- 앞으로 표정 제어 코드는 `main`의 `robot_face/jetson/`을 기준으로 사용합니다.
- ESP32 펌웨어의 명령 이름과 Jetson의 `Face` enum을 동일하게 유지합니다.
- Arduino Serial Monitor와 Jetson Python 프로그램을 동시에 같은 Serial 포트에 연결하지 않습니다.
- CH341 모듈은 커널 종속 바이너리이므로 저장소에 `.ko` 파일을 올리지 않습니다.
- OS 또는 커널 업데이트 후에는 얼굴 LCD 시험을 가장 먼저 다시 수행합니다.
- 최종 로봇 조립 전 LCD와 ESP32 점퍼선을 커넥터·납땜·스트레인 릴리프로 고정합니다.
