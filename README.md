# Pumpkin

디지털 소외계층의 무인매장 접근성을 높이기 위한 **ROS2 기반 Physical AI 카페 응대 로봇** 프로젝트입니다.

사용자는 복잡한 키오스크 조작 없이 음성으로 주문할 수 있으며, 로봇은 STT, 한국어 NLU, 대화 상태 판단, TTS, LCD 표정, 고개·팔 동작을 연결해 주문을 확인하고 필요한 정보를 다시 질문합니다.

> **서비스 메뉴의 기준 원본(Single Source of Truth)은 `config/menu_catalog.json`입니다.** NLU 데이터셋은 자연어 학습 라벨과 모델 출력 구조의 기준이며, NLU가 출력한 메뉴 문자열은 서비스 계층에서 카탈로그의 `name`/`aliases`와 매칭하여 공식 `menu_id`로 변환합니다. 자세한 규칙은 `docs/menu_catalog_policy.md`를 참고하세요.

## Repository Maintenance Status — 2026-08-10

현재 저장소는 기능 개발 과정에서 현재 구현, 시제품, 실험 코드, legacy 데이터와 문서가 함께 누적되어 있어 구조 정리를 진행 중입니다.

- 기존 관리자 웹 `web/`은 **삭제하지 않고 Legacy / Reference 구현으로 보존**합니다.
- 관리자 웹 UI와 프런트엔드 구조는 앞으로 새로 설계하여 재구축합니다.
- 과거 데이터 보관용 `experience/`는 제거하고 `data/archive/2026-08-08/`로 정리했습니다.
- 루트의 빈 `vision/` placeholder는 제거했습니다. 실제 비전 runtime은 ROS2의 `robot_controller.vision_node`입니다.
- 과거 standalone `voice/STT/` 코드는 `experiments/voice/legacy_stt/`로 이동했습니다. 현재 production STT는 `robot_controller.stt_node_unbiased`입니다.
- 대규모 파일 이동·삭제는 import, 스크립트, ROS2 경로 의존성을 확인한 뒤 진행합니다.
- 새 기능의 메뉴는 `config/menu_catalog.json`과 공식 `menu_id`를 사용합니다.
- 정리 현황과 후보 목록: `docs/REPOSITORY_CLEANUP_2026-08-10.md`

## Project Goal

- 음성 중심 주문으로 디지털 취약 사용자의 접근성 개선
- 한국어 구어체 주문에서 의도와 주문 항목을 구조화
- 누락 정보와 정책 위반을 감지해 잘못된 주문 확정 방지
- ROS2를 이용해 인식–판단–행동 모듈 통합
- Jetson Orin Nano에서 AI 추론과 로봇 제어 수행

## Main Features

- Faster-Whisper 기반 한국어 STT
- koELECTRA Encoder 기반 사용자 의도 분류
- Item Query Decoder 기반 복수 주문 항목 추출
- 메뉴·온도·수량 누락 감지 및 재질문
- FSM 기반 주문 확인·수정·취소 흐름
- eSpeak-NG 기반 TTS 안내
- LCD 표정과 고개·팔 제스처 출력
- 얼굴 인식 기반 단골 고객 개인화
- 고객용 사전 주문 앱
- 관리자 웹 및 주문 API 연동
- ROS2 Topic 기반 모듈 통합

## Menu Catalog

서비스에서 사용하는 공식 메뉴는 `config/menu_catalog.json`에서 관리합니다.

| menu_id | 메뉴 | 허용 온도 | 가격 |
|---:|---|---|---:|
| 1 | 아메리카노 | `ICE`, `HOT` | 3,000원 |
| 2 | 카페라떼 | `ICE`, `HOT` | 4,000원 |
| 3 | 바닐라라떼 | `ICE`, `HOT` | 4,500원 |
| 4 | 레몬에이드 | `ICE` | 4,500원 |
| 5 | 딸기스무디 | `ICE` | 5,000원 |

새 기능은 메뉴명, 가격, 온도, 판매 여부를 각 코드에 따로 하드코딩하지 않고 카탈로그 또는 이를 제공하는 공용 API/서비스를 사용합니다.

## NLU Dataset

NLU 데이터셋은 서비스 가격표가 아니라 **자연어 주문을 학습하기 위한 Intent/slot/order-status 기준**입니다.

현재 Structure B 계열 데이터는 다음을 학습합니다.

### Intent Labels

| 라벨 | 의미 |
|---|---|
| `ORDER` | 신규 주문 |
| `MODIFY` | 주문 수정 |
| `CANCEL` | 주문 취소 |
| `AFFIRM` | 긍정 응답 |
| `DENY` | 부정 응답 |
| `GUIDE` | 매장 이용 및 위치 안내 |
| `PAYMENT` | 결제 관련 문의 |
| `UNKNOWN` | 지원 범위 밖이거나 불명확한 발화 |

### Order Slots and Options

각 `ORDER` 샘플은 `items` 배열로 주문을 표현합니다.

| 필드 | 값 |
|---|---|
| `item_id` | 주문 항목 순서, 0부터 시작 |
| `menu` | NLU가 예측하는 표준 메뉴 문자열 |
| `temperature` | `ICE`, `HOT`, `null` |
| `quantity` | 1~20의 정수 또는 `null` |
| `missing_slots` | 누락된 `quantity`, `temperature` 목록 |
| `validation_errors` | 항목 단위 검증 오류 |

현재 NLU 학습 라벨에는 다음 정보가 포함되지 않습니다.

- 가격
- 사이즈
- 샷 추가
- 시럽
- 우유 종류
- 얼음 양
- 포장 여부

이 값들은 NLU 데이터셋만으로 예측하거나 임의로 채우지 않습니다.

## Order Status and Validation

`ORDER`의 주문 상태는 다음 세 가지를 사용합니다.

| 상태 | 의미 |
|---|---|
| `VALID` | 주문에 필요한 정보가 유효함 |
| `INCOMPLETE` | 수량 또는 온도가 누락됨 |
| `OUT_OF_POLICY` | 지원하지 않는 옵션이 요청됨 |

주요 검증 오류:

| 오류 | 의미 |
|---|---|
| `MISSING_QUANTITY` | 수량 누락 |
| `MISSING_TEMPERATURE` | ICE/HOT 선택형 메뉴의 온도 누락 |
| `TEMPERATURE_NOT_ALLOWED` | 제공하지 않는 온도 요청 |

수량 또는 온도가 누락되면 임의의 기본값으로 확정하지 않고 재질문합니다.

```text
사용자: 아메리카노 하나 주세요.
로봇: 아메리카노는 아이스로 드릴까요, 따뜻하게 드릴까요?
```

```text
사용자: 차가운 카페라떼 주세요.
로봇: 카페라떼는 몇 잔 주문하시겠어요?
```

지원하지 않는 온도 요청은 주문을 확정하지 않습니다.

```text
사용자: 따뜻한 레몬에이드 한 잔 주세요.
로봇: 레몬에이드는 아이스로만 주문할 수 있습니다.
```

## NLU Model

현재 주문 NLU는 다음 구조를 사용합니다.

1. 입력 주문 문장을 정규화합니다.
2. koELECTRA Encoder가 문장의 문맥 특징을 추출합니다.
3. CLS 표현을 이용해 Intent를 예측합니다.
4. 최대 3개의 학습 가능한 Item Query를 Transformer Decoder에 입력합니다.
5. 각 Query가 하나의 주문 항목을 담당하며 메뉴·온도·수량을 예측합니다.
6. 누락 슬롯과 정책 위반 여부를 검사해 주문 상태를 결정합니다.

이 구조는 한 문장에 여러 메뉴가 포함된 경우에도 각 메뉴에 대응하는 온도와 수량을 묶어 출력하기 위한 것입니다.

대표 학습 노트북:

```text
notebooks/koelectra_structure_b_item_query_decoder.ipynb
```

NLU/데이터 관련 최신 문서 인덱스:

```text
docs/README.md
```

## System Flow

```text
사용자 음성
→ Faster-Whisper STT
→ koELECTRA + Item Query Decoder
→ 주문 슬롯 및 오류 검증
→ FSM 기반 대화 상태 판단
→ 주문 확인 / 재질문 / 수정 / 취소
→ TTS + LCD 표정 + 로봇 동작
→ 주문 서버 및 관리자 화면
```

## Repository Structure

현재 저장소는 정리 중이므로 아래는 **현재 루트 디렉터리의 역할**을 설명합니다. 장기 구조 변경안은 `docs/REPOSITORY_CLEANUP_2026-08-10.md`에 기록합니다.

```text
pumpkin/
├── api/          # FastAPI, 주문/고객/얼굴 API, ROS-Web 연동
├── apps/         # 고객용 앱 등 사용자 애플리케이션
├── arduino/      # MCU/Arduino 펌웨어
├── config/       # 공통 서비스 설정과 메뉴 카탈로그
├── data/         # 현재 학습/테스트 데이터 + archive/ 과거 데이터 보관
├── docs/         # 정책, 설계, 실행법, 실험/디버깅 기록
├── experiments/  # NLU 비교 실험, 이전 모델/실험 코드, legacy standalone 코드
├── hardware/     # 부품, 전원, 배선, 기구 제작 기록
├── nlu/          # 현재 독립 NLU 추론 코드
├── notebooks/    # Google Colab 학습 노트북
├── robot_face/   # ESP32 LCD 펌웨어와 Jetson Serial face controller
├── ros2_ws/      # ROS2 노드와 통합 제어 runtime
├── scripts/      # 실행, 테스트, 데이터 생성, 디버깅 스크립트
├── tests/        # 저장소 루트 단위 테스트
├── tools/        # 개발 보조 도구
└── web/          # 기존 관리자 웹 Legacy / Reference 구현
```

주요 archive 위치:

```text
data/archive/2026-08-08/          # 과거 데이터셋/산출물
experiments/voice/legacy_stt/    # 과거 standalone STT/NLU 통합 코드
```

archive 디렉터리는 현재 runtime 기준이 아니라 과거 구현과 실험 재현을 위한 보관 영역입니다.

### Current Runtime Boundaries

- STT: `ros2_ws/src/robot_controller/robot_controller/stt_node_unbiased.py`
- Vision: `ros2_ws/src/robot_controller/robot_controller/vision_node.py`
- Face hardware driver: `robot_face/jetson/face_controller.py`
- Face ROS adapter: `ros2_ws/src/robot_controller/robot_controller/face_display_node.py`

## Physical Robot Demo Startup

실물 로봇 시연 시에는 **5인치 HDMI 고객 화면까지 함께 실행하는 통합 런처**를 사용합니다.

### 권장 실행 명령

팔 동작을 비활성화한 상태에서 전체 시스템을 실행하려면:

```bash
cd ~/pumpkin

PUMPKIN_ENABLE_ARM=false \\
PUMPKIN_VISION_STARTUP_TIMEOUT=30 \\
bash scripts/run_robot_with_monitor.sh
```

팔을 차렷(HOME) 자세로 맞춘 뒤 실제 팔 동작까지 사용할 경우:

```bash
cd ~/pumpkin

PUMPKIN_ENABLE_ARM=true \\
PUMPKIN_VISION_STARTUP_TIMEOUT=30 \\
bash scripts/run_robot_with_monitor.sh
```

`run_robot_with_monitor.sh`는 다음 순서로 실행됩니다.

```text
5인치 HDMI 화면 설정 및 절전 해제
→ monitor-web 서버 실행 (http://127.0.0.1:8770)
→ 웹 서버 응답 확인
→ Chromium 800×480 kiosk 실행
→ 5인치 고객 화면 표시
→ run_robot_interaction_demo.sh 실행
→ ROS2 / Vision / STT / NLU / Decision / TTS / LCD / PCA9685 통합 로봇 시작
```

정상 기동 시 아래 로그를 확인합니다.

```text
[START] 5-inch monitor web server
[OK] monitor-web ready
[START] 5-inch Chromium kiosk
[OK] 5-inch kiosk ready
[START] 팔·목·카메라·음성·얼굴 LCD 통합 로봇 파이프라인
```

> **주의:** `scripts/run_robot_interaction_demo.sh`만 직접 실행하면 ROS2 대화 파이프라인과 로봇 하드웨어는 실행되지만, **5인치 HDMI monitor-web과 Chromium kiosk는 실행되지 않습니다.** 실물 시연의 최종 실행 명령은 `scripts/run_robot_with_monitor.sh`입니다.

### Vision 시작 타임아웃

`PUMPKIN_VISION_STARTUP_TIMEOUT=30`의 30초는 사람이 카메라 앞에 나타날 때까지 기다리는 시간이 아닙니다. Vision 모듈이 카메라를 열고 얼굴 인식·MediaPipe 등의 초기화를 마친 뒤 **첫 실제 카메라 프레임을 정상 처리할 때까지 기다리는 시작 제한 시간**입니다. 사람이 없어도 카메라 프레임이 정상 처리되면 Vision은 READY 상태가 됩니다.

## Development Environment

- Edge device: NVIDIA Jetson Orin Nano
- Robot framework: ROS2 Humble
- AI: PyTorch, Transformers, koELECTRA, Faster-Whisper
- Vision: OpenCV, MediaPipe, Face Embedding
- Backend: FastAPI
- Frontend: React, Vite, TypeScript / Expo React Native
- TTS: eSpeak-NG
- MCU: ESP32, PCA9685
- Language: Python, TypeScript, C/C++

공통 Python 환경은 Python 3.11을 권장합니다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Dataset–Service Consistency Rule

메뉴나 옵션을 변경할 때는 한 파일만 수정하지 않습니다.

1. `config/menu_catalog.json` — 서비스 메뉴 기준 원본
2. NLU 학습 데이터의 메뉴 라벨
3. NLU 모델의 출력 클래스와 설정
4. 주문 검증 정책
5. STT 보정용 메뉴 사전
6. 고객 앱 메뉴 표시/조회
7. 관리자 웹 메뉴 표시/관리
8. 주문 서버 및 데이터베이스
9. 관련 README/정책 문서

**운영 메뉴의 최종 출처는 `config/menu_catalog.json`이고, NLU 데이터셋은 모델 학습 라벨의 기준입니다.**

## Team

- Mentor: 서혁준, LG CNS RED
- Mentee: 유지성, 김수향, 박율리
- University: 이화여자대학교 전기전자공학전공
- Program: 2026 한이음 드림업
