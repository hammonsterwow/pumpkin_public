# ESP32 및 3.5인치 얼굴 LCD

로봇 얼굴 표시 장치를 Jetson과 분리하여 LOLIN D32에서 구동하기 위한 **실물 기준 최종 배선, TFT_eSPI 설정, 펌웨어와 Jetson 연동 상태**를 정리합니다.

> 2026-08-06 기준으로 LOLIN D32와 ILI9488 LCD의 단색 화면, 5종 표정 출력, Jetson Orin Nano의 USB Serial 표정 제어까지 실제 확인했습니다. 현재 암-암 점퍼선은 움직일 때 접촉이 끊겨 백라이트만 남는 현상이 있으므로 최종 조립 전 커넥터 고정이 필요합니다.

## 전체 연결 구조

```text
Jetson Orin Nano
    │
    │ USB Serial 115200 baud + ESP32 전원
    ▼
WeMos LOLIN D32 V1.0.0
    │
    │ 4-wire SPI, 3.3 V logic
    ▼
3.5-inch ILI9488 TFT LCD
```

- Jetson은 표정 이름만 USB Serial로 전송합니다.
- ESP32가 TFT_eSPI를 이용해 LCD에 실제 표정을 그립니다.
- LCD는 Jetson에 직접 연결하지 않습니다.
- ESP32와 LCD는 반드시 GND를 공통으로 연결합니다.

## 1. 사용 부품

### WeMos LOLIN D32 V1.0.0

| 항목 | 사양 |
|---|---|
| MCU 모듈 | ESP32-WROOM-32 REV1 |
| 최대 클럭 | 240 MHz |
| Flash | 4 MB |
| USB 보드 전원 | 5 V |
| GPIO 로직 전압 | 3.3 V |
| 개발 환경 | Arduino IDE |
| USB Serial 칩 | CH340, USB ID `1a86:7523` |
| Jetson 장치명 | `/dev/ttyUSB0` 확인 |

### 3.5인치 SPI TFT LCD

| 항목 | 사양 |
|---|---|
| 제품 표기 | 3.5-inch SPI TFT Module |
| SKU | MSP3520 |
| LCD 드라이버 | ILI9488 |
| 해상도 | 320 × 480 px, 가로 사용 시 480 × 320 px |
| 통신 | 4-wire SPI |
| VCC | 3.3~5 V |
| 로직 레벨 | 3.3 V TTL |
| 터치 | 지원 모듈이지만 현재 사용하지 않음 |
| 추가 기능 | microSD 카드 슬롯 |

LCD 보드 헤더의 실크스크린 순서는 다음과 같습니다.

```text
VCC, GND, CS, RESET, DC/RS, SDI(MOSI), SCK, LED, SDO(MISO),
T_CLK, T_CS, T_DIN, T_DO, T_IRQ
```

## 2. 최종 배선

현재 실제 동작을 확인한 최종 배선은 아래 8가닥입니다.

| LCD 핀 | LOLIN D32 핀 | 기능 | 상태 |
|---|---|---|---|
| `VCC` | `USB` | LCD 본체 5 V 전원 | 연결 |
| `GND` | `GND` | 공통 접지 | 연결 |
| `CS` | `GPIO15` | LCD Chip Select | 연결 |
| `RESET` | `GPIO4` | LCD 하드웨어 리셋 | 연결 |
| `DC/RS` | `GPIO2` | 데이터/명령 선택 | 연결 |
| `SDI(MOSI)` | `GPIO23` | ESP32 → LCD 데이터 | 연결 |
| `SCK` | `GPIO18` | SPI 클럭 | 연결 |
| `LED` | `3V` | LCD 백라이트 | 연결 |

### 연결하지 않는 핀

```text
SDO(MISO)
T_CLK
T_CS
T_DIN
T_DO
T_IRQ
```

- 화면 출력은 MOSI 단방향 통신만으로 동작하므로 `SDO(MISO)`는 현재 필요하지 않습니다.
- 터치 기능은 주문 로봇 얼굴 출력에 필요하지 않아 비활성 상태입니다.
- LOLIN D32의 `BAT` 핀은 LCD 전원으로 사용하지 않습니다.
- LCD VCC는 보드의 `USB` 5 V 핀에 연결하고 신호선은 ESP32의 3.3 V GPIO만 사용합니다.

### CS 핀 기준

초기 시험에서는 GPIO5도 사용했지만, 현재 저장소와 실제 최종 배선은 아래 값으로 통일합니다.

```text
LCD CS → GPIO15
```

GPIO15는 ESP32 부팅 스트래핑 핀이므로 향후 부팅·업로드 이상이 생기면 LCD CS 연결 상태를 먼저 확인합니다. 현재 구성에서는 정상 부팅과 표정 출력을 확인했습니다.

## 3. TFT_eSPI 설정

권장 사용자 설정 파일명:

```text
Setup_Pumpkin_ILI9488.h
```

설정 내용:

```cpp
#define USER_SETUP_INFO "Pumpkin LOLIN D32 + ILI9488"
#define ILI9488_DRIVER

#define TFT_MOSI 23
#define TFT_SCLK 18
// #define TFT_MISO 19

#define TFT_CS   15
#define TFT_DC    2
#define TFT_RST   4

#define LOAD_GLCD
#define LOAD_FONT2
#define LOAD_FONT4
#define LOAD_FONT6
#define LOAD_GFXFF
#define SMOOTH_FONT

#define SPI_FREQUENCY 5000000
```

`User_Setup_Select.h`에서는 아래 설정 파일 하나만 활성화합니다.

```cpp
// #include <User_Setup.h>
#include <User_Setups/Setup_Pumpkin_ILI9488.h>
```

다른 Setup 파일이 동시에 활성화되지 않도록 합니다.

## 4. ESP32 펌웨어

메인 브랜치의 LCD 표정 펌웨어:

```text
robot_face/esp32_lcd/esp32_lcd_face.ino
```

ESP32는 USB Serial에서 한 줄 단위 문자열을 받아 표정을 변경합니다.

```text
NEUTRAL
SMILE
HAPPY
QUESTION
ERROR
```

통신 조건:

```text
baud rate: 115200
encoding: ASCII/UTF-8 영문 명령
terminator: newline, \n
```

ESP32 펌웨어가 실행되면 기본 표정은 `NEUTRAL`이며, 새 명령이 들어오기 전까지 마지막 표정을 유지합니다.

## 5. Jetson 제어 코드

Jetson 제어 코드는 실제 장비 시험을 마친 뒤 PR #61로 메인 브랜치에 병합했습니다.

```text
robot_face/jetson/face_controller.py
robot_face/jetson/README.md
robot_face/jetson/requirements.txt
```

지원 기능:

- ESP32 후보 USB Serial 포트 자동 탐지
- CH340/CH341, CP210x 등 주요 USB-UART 식별
- `NEUTRAL`, `SMILE`, `HAPPY`, `QUESTION`, `ERROR` 전송
- 단일 표정 출력, 전체 데모, 대화형 시험
- USB 연결이 끊긴 경우 1회 재연결 시도
- ROS2 `face_display_node`가 `/robot_action`의 표정 값을 받아 `FaceController`로 전달

평소 실행:

```bash
cd ~/pumpkin_public
git switch main
git pull
source .venv/bin/activate
python3 robot_face/jetson/face_controller.py --demo
```

표정 하나 출력:

```bash
python3 robot_face/jetson/face_controller.py --face HAPPY
```

## 6. Jetson CH340 드라이버와 권한

시험 환경:

```text
Jetson Linux R36.5.0
kernel 5.15.185-tegra
LOLIN D32 CH340 USB ID 1a86:7523
```

해당 NVIDIA 커널에는 아래 설정이 비활성화되어 있었습니다.

```text
# CONFIG_USB_SERIAL_CH341 is not set
```

동일한 R36.5.0 커널 소스와 현재 커널 헤더로 `ch341.ko`를 빌드해 다음 경로에 설치했습니다.

```text
/lib/modules/5.15.185-tegra/extra/ch341.ko
```

부팅 시 자동 로드 설정:

```text
/etc/modules-load.d/ch341.conf
```

또한 `brltty` 서비스가 CH340을 가로채 `/dev/ttyUSB0`을 끊는 문제가 있어 서비스를 중지·비활성화했고, `pumpkin` 사용자를 `dialout` 그룹에 추가했습니다.

설치·복구·커널 업데이트 절차는 다음 문서를 기준으로 합니다.

```text
hardware/JETSON_ESP32_LCD_SETUP.md
```

> [!WARNING]
> 현재 `ch341.ko`는 `5.15.185-tegra` 전용입니다. Jetson 커널을 업데이트한 뒤 `uname -r`과 `modinfo ch341 | grep vermagic`가 다르면 새 커널용 모듈을 다시 빌드해야 합니다. 다른 커널 버전의 모듈을 강제로 로드하지 않습니다.

## 7. 실제 시험 결과

2026-08-06 기준 확인 결과입니다.

- [x] LOLIN D32 Arduino 업로드 성공
- [x] TFT_eSPI에서 ILI9488 드라이버 인식
- [x] 해상도 320 × 480 인식
- [x] SPI 핀 MOSI 23, SCK 18, CS 15, DC 2, RST 4 적용
- [x] 5 MHz SPI에서 단색 화면 출력
- [x] 가로 방향 480 × 320 출력
- [x] `NEUTRAL`, `SMILE`, `HAPPY`, `QUESTION`, `ERROR` 표정 출력
- [x] PC USB Serial 명령으로 표정 전환
- [x] Jetson Orin Nano에서 CH340 `/dev/ttyUSB0` 인식
- [x] Jetson Python → ESP32 → LCD 전체 표정 데모
- [x] Jetson 표정 제어 코드를 메인 브랜치에 병합
- [x] ROS2 `/robot_action` → `face_display_node` → `FaceController` 표정 출력 연동 코드 구현
- [ ] 최종 커넥터 및 배선 고정
- [ ] 장시간 출력 및 발열 시험

## 8. 현재 알려진 문제

### LCD를 움직이면 백라이트만 남는 현상

암-암 듀퐁 점퍼선을 사용한 임시 배선에서는 LCD를 들어 올리거나 선을 움직일 때 접촉이 끊기는 현상이 확인되었습니다.

```text
LED 핀 접촉 유지       → 백라이트는 계속 켜짐
VCC 또는 SPI 접촉 끊김 → 화면 데이터는 표시되지 않음
```

백라이트가 켜져 있다는 사실만으로 LCD 본체 전원과 SPI 통신이 정상이라고 판단하지 않습니다.

최종 조립 전 조치:

- 점퍼선 양쪽을 완전히 삽입
- LCD와 ESP32를 함께 고정하여 선에 장력이 걸리지 않게 구성
- 커넥터 또는 납땜 배선으로 교체
- 케이블 타이·열수축 튜브·접착식 고정구로 당김 방지
- 이동 후 화면이 사라지면 USB 전원 차단 후 배선 재결합

### `/dev/ttyUSB0`이 보이지 않는 현상

```bash
lsusb | grep -Ei '1a86|ch340|ch341'
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
sudo dmesg | grep -Ei 'ch341|ttyUSB|brltty' | tail -n 30
```

- `lsusb`에도 CH340이 없으면 케이블·USB 포트·ESP32 전원을 확인합니다.
- `lsusb`에는 있지만 장치 파일이 없으면 CH341 모듈과 `brltty` 상태를 확인합니다.
- `Permission denied`이면 현재 사용자의 `dialout` 그룹 포함 여부를 확인합니다.

## 9. 시험 절차

1. LCD와 ESP32의 USB 전원을 끕니다.
2. 최종 8가닥 배선을 확인합니다.
3. LCD와 ESP32를 움직이지 않도록 평평하게 놓습니다.
4. LOLIN D32를 Jetson USB에 연결합니다.
5. `ls -l /dev/ttyUSB0`으로 포트를 확인합니다.
6. ESP32가 부팅되면 기본 `NEUTRAL` 표정이 나오는지 확인합니다.
7. `python3 robot_face/jetson/face_controller.py --demo`를 실행합니다.
8. 출력이 사라지면 코드 재실행보다 먼저 점퍼선 접촉을 확인합니다.

## 10. 주의 사항

- 배선 변경은 반드시 USB 전원을 뺀 상태에서 진행합니다.
- Arduino IDE Serial Monitor와 Jetson 제어 프로그램을 동시에 같은 포트에 연결하지 않습니다.
- TFT_eSPI 라이브러리를 업데이트하면 사용자 설정 파일이 덮어써질 수 있으므로 저장소 문서와 대조합니다.
- 최종 장착 전에는 점퍼선 임시 연결을 그대로 사용하지 않습니다.
- CH341 커널 모듈 파일은 Jetson 커널 버전에 종속되므로 저장소에 `.ko` 바이너리를 커밋하지 않습니다.
