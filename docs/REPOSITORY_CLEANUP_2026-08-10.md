# Pumpkin 저장소 대청소 기록 — 2026-08-10

이 문서는 Pumpkin 저장소를 정리하는 과정에서 팀원들이 **현재 유지할 것, 앞으로 다시 만들 것, 정리 후보**를 같은 기준으로 이해하기 위한 기록이다.

## 1. 정리 원칙

이번 정리는 기능을 무작정 삭제하는 작업이 아니다.

1. 현재 동작하는 코드와 과거 구현은 우선 보존한다.
2. 새 구조가 검증되기 전에는 경로를 대규모로 이동하지 않는다.
3. 오래된 코드는 즉시 삭제하지 않고 `legacy/archive` 후보로 먼저 분류한다.
4. README와 설계 문서가 실제 코드와 다르면 최신 구현 및 공식 정책 문서를 기준으로 정리한다.
5. 실행 스크립트, import 경로, ROS2 package 경로가 연결된 파일은 의존성을 확인한 뒤 이동한다.

## 2. 관리자 웹 재구축 결정

### 상태: 기존 구현 보존 / 신규 관리자 웹 재구축 예정

현재 `web/` 폴더의 관리자 웹은 **기존 구현을 보존하기 위한 Legacy / Reference 구현**으로 취급한다.

- 기존 `web/` 코드는 삭제하지 않는다.
- 현재 ROS2/FastAPI 연동 방식과 기존 기능을 확인하기 위한 참고 자료로 유지한다.
- 앞으로 관리자 웹 UI와 프런트엔드 구조는 새로 설계하여 다시 구현한다.
- 새 관리자 웹이 기존 필수 기능을 대체하기 전까지 기존 구현을 제거하지 않는다.
- 재구축 기간에는 기존 `web/`에 신규 UI 기능을 계속 덧붙이기보다 치명적 오류 수정과 연동 확인만 수행한다.
- FastAPI/API/ROS Bridge 등 백엔드 코드는 프런트엔드와 분리하여 재사용 가능성을 검토한다.

새 UI에서도 잃지 말아야 할 기존 기능 계약은 다음과 같다.

- 주문 목록 및 주문 상태 확인
- 로봇/ROS2 상태 확인
- 고객·단골 정보 확인
- 메뉴 관리
- STT/NLU/Decision/Action 결과 모니터링 또는 디버깅
- FastAPI 및 주문 API 연동

## 3. 저장소 구조 감사 결과

### A. 루트 디렉터리 분류 기준 혼재

현재 루트에는 실행 서비스(`api/`, `apps/`, `web/`), AI/인식(`nlu/`), 로봇 통합(`ros2_ws/`, `robot_face/`), 펌웨어/하드웨어(`arduino/`, `hardware/`), 데이터/실험(`data/`, `notebooks/`, `experiments/`), 개발 지원(`scripts/`, `tests/`, `tools/`, `config/`)이 같은 레벨에 섞여 있다.

장기적으로 아래와 같은 논리적 분류를 검토하되, 실행 경로가 얽힌 영역은 의존성 확인 후 이동한다.

```text
apps/          사용자/관리자 애플리케이션
services/      API 등 서비스 계층 (장기 검토)
robot/         ROS2 및 로봇 런타임 (장기 검토)
firmware/      ESP32/Arduino 코드 (장기 검토)
ai/            독립 AI 추론 모듈 (장기 검토)
data/          현재 사용 데이터
data/archive/  과거 데이터
experiments/   비교 실험, 이전 모델, legacy 코드
hardware/      부품/전원/배선/기구
scripts/       실행 및 개발 도구
docs/          문서
```

### B. `experience/` 정리 완료

기존 `experience/data_legacy_20260808/`는 이름과 실제 역할이 맞지 않았고, 내용도 실험 코드가 아니라 과거 데이터 산출물이었다.

2026-08-10에 다음과 같이 정리했다.

```text
experience/data_legacy_20260808/
→ data/archive/2026-08-08/
```

정리 원칙:

- 기존 데이터 내용은 변경하지 않고 보존했다.
- `experience/` 경로를 직접 참조하는 코드/문서가 없는 것을 확인한 뒤 이동했다.
- 과거 데이터는 `data/archive/` 아래 날짜 단위로 보관한다.
- `experiments/`는 모델 비교 실험, 이전 모델, 실험 코드 보관 위치로 유지한다.
- archive 데이터는 현재 서비스 런타임의 기준 데이터로 사용하지 않는다.
- `data/archive/2026-08-08/README.md`에 보관 목적과 파일 목록을 기록했다.

이 정리로 목적이 모호했던 루트 `experience/` 디렉터리는 제거되었다.

### C. 고객 앱에 현재 코드와 시제품 코드가 혼재

`apps/customer-mobile/README.md`가 설명하는 현재 실행 흐름은 다음과 같다.

```text
index.ts -> App.tsx -> src/CustomerMobileApp.tsx
```

동시에 다음 항목들이 함께 존재한다.

- 현재 진입점에서 사용하지 않는다고 문서화된 `NativeApp.tsx`, `NativeAppCare.tsx`
- `src/app/` 아래 별도 App/components 구조
- `src/app/src/`처럼 중첩된 `src` 구조
- `src/app/components/`와 `src/screens/`의 유사 역할 파일
- 대량의 범용 UI 컴포넌트

다음 단계에서는 실제 import graph를 기준으로 **현재 사용 / 시제품 / 미사용 후보**를 나눈다. 단골 고객 기능이 별도 브랜치에서 진행 중이므로 지금 즉시 이동·삭제하지 않는다.

### D. STT / Vision / Face 역할 조사

2026-08-10에 실제 실행 스크립트, import, 테스트, Git 이력까지 다시 확인했다.

#### Vision — 정리 완료

루트 `vision/`에는 `.gitkeep`만 존재했고 실제 비전 코드는 없었다. 현재 실제 비전 runtime은 다음 ROS2 노드다.

```text
ros2_ws/src/robot_controller/robot_controller/vision_node.py
```

따라서 빈 루트 `vision/` placeholder를 제거했다.

#### Voice/STT — archive 이동 완료

기존 `voice/STT/`는 고정 길이 녹음과 Faster-Whisper, NLU를 직접 연결하던 초기 standalone 구현이었다. 현재 production runtime에서 이 경로를 import하거나 실행하지 않는 것을 확인했다.

현재 production STT는 다음 상속 구조를 사용한다.

```text
stt_node.py
  ↑
stt_node_safe.py
  ↑
stt_node_unbiased.py  ← production entry
```

실제 런처 `scripts/run_ros_voice_nodes.sh`도 `robot_controller.stt_node_unbiased`를 실행한다.

따라서 기존 standalone 코드는 삭제하지 않고 다음 위치로 이동했다.

```text
voice/STT/
→ experiments/voice/legacy_stt/
```

`experiments/voice/legacy_stt/README.md`에 현재 production 코드가 아니라 과거 실험 재현용임을 기록했다. 과거 `voice/STT/main.py` 경로를 사용하던 NLU 배포 문서들도 archive 경로와 현재 production 실행법을 구분하도록 수정했다.

#### Robot Face — 현재 사용 코드 유지

현재 production 얼굴 출력 경로는 다음과 같다.

```text
/robot_action.face
→ robot_controller.face_display_node
→ robot_face.jetson.FaceController
→ USB Serial
→ ESP32 LCD firmware
```

따라서 `robot_face/`와 `face_display_node.py`는 현재 사용 코드로 유지한다.

#### `face_controller_node.py` — 삭제 보류

`ros2_ws/src/robot_controller/robot_controller/face_controller_node.py`는 `face_display_node.py`와 역할이 중복되어 보이고 현재 production 런처에서는 실행되지 않는다.

하지만 Git 이력을 확인한 결과:

- PR #62에서 현재 `face_display_node -> robot_face.jetson.FaceController` 구조가 병합됨
- 이후 PR #63에서 숫자 Serial 명령 방식의 `face_controller_node.py`가 별도 하드웨어 통합 작업으로 병합됨
- PR #63에는 Jetson USB Serial → ESP32 → LCD 실물 검증 기록이 존재함

현재 저장소의 공식 ESP32 firmware는 `NEUTRAL`, `SMILE`, `HAPPY`, `QUESTION`, `ERROR` 문자열 명령을 사용하므로 소프트웨어 기준으로는 `face_display_node` 경로가 현재 구조와 일치한다. 다만 실제 로봇 ESP32에 어떤 firmware가 올라가 있는지 GitHub만으로 확정할 수 없으므로 `face_controller_node.py`와 해당 `setup.py` entry point는 **실물 firmware 확인 전까지 삭제하지 않는다.**

### E. `scripts/` 과밀

현재 `scripts/`에는 로봇 전체 실행, ROS2 실행, Jetson 테스트, 데이터 생성·증강, PCA9685 하드웨어 테스트, 터미널 디버깅, 웹/API 실행 스크립트가 함께 있다.

경로를 먼저 옮기면 호출부가 깨질 수 있으므로, 우선 `scripts/README.md`에서 분류를 명확히 한 뒤 하위 폴더화를 검토한다.

### F. 원시 데이터가 ROS2 package 내부에 존재

`ros2_ws/src/robot_controller/gesture_data/raw/`에 큰 CSV 원시 데이터가 있다. 장기적으로 실행 코드와 데이터 원본을 분리해 `data/gesture/` 같은 위치로 옮기는 편이 명확하다. 참조 경로 조사 전에는 이동하지 않는다.

### G. 안전한 삭제 후보

이미 내용이 있는 폴더에도 `.gitkeep`이 남아 있다.

- `docs/.gitkeep`
- `hardware/.gitkeep`
- `ros2_ws/.gitkeep`
- `web/.gitkeep`

`vision/.gitkeep`과 `voice/.gitkeep`은 해당 루트 placeholder/legacy 경로 정리 과정에서 제거했다.

### H. 파일명 규칙 혼재

문서에 날짜형, 대문자 상태 문서, `★` 기호가 포함된 파일명이 섞여 있다. 중요도를 파일명 기호로 표현하는 대신 `docs/README.md`의 문서 역할/상태로 구분하는 방향을 사용한다.

## 4. 메뉴 및 문서 기준 통일

### 서비스 메뉴 Single Source of Truth

서비스가 사용하는 공식 메뉴 정보의 기준은 `config/menu_catalog.json`이다.

- `menu_id`
- 표시 메뉴명
- 가격
- 제공 온도
- 판매 여부
- 설명 및 이미지 경로

### NLU 데이터셋의 역할

NLU 데이터셋은 **자연어 모델의 학습 라벨과 출력 구조 기준**이다.

- Intent
- 메뉴 문자열 라벨
- 온도/수량 slot
- order status 및 validation

NLU가 메뉴 문자열을 출력하면 서비스 계층에서 `config/menu_catalog.json`의 `name`/`aliases`와 매칭해 공식 `menu_id`로 변환한다.

따라서 과거 문서의 “데이터셋이 가격·운영 정보를 포함한 모든 메뉴 정보의 최종 출처”라는 표현은 새 개발 기준으로 사용하지 않는다. 세부 정책은 `docs/menu_catalog_policy.md`를 따른다.

### README 역할

- `/README.md`: 프로젝트 전체 개요, 실제 현재 구조, 핵심 기준
- `/docs/README.md`: 문서 인덱스와 문서 역할
- 각 기능 폴더 `README.md`: 해당 기능의 현재 실행 방법과 경계
- 날짜형 로그: 특정 시점의 실험/문제 해결 기록

## 5. 진행 현황

### P0 — 1차 문서 정리 완료

- [x] 관리자 웹 재구축 결정 기록
- [x] 기존 관리자 웹 보존 원칙 기록
- [x] `web/README.md`에 Legacy/Rebuild 예정 상태 표시
- [x] 메뉴 기준 원본 역할 정리
- [x] 루트 README의 오래된 메뉴 기준 표현 수정
- [x] 루트 README의 실제 저장소 구조 반영
- [x] `docs/README.md`에 대청소 문서 및 문서 역할 연결
- [x] `experience/` legacy 데이터를 `data/archive/2026-08-08/`로 이동
- [x] 빈 루트 `vision/` placeholder 제거
- [x] `voice/STT/` standalone 코드를 `experiments/voice/legacy_stt/`로 archive
- [x] 과거 STT 경로를 사용하던 NLU 배포 문서 수정

### P1 — 의존성 조사 후 정리

- [ ] 고객 앱 실제 사용 파일 import graph 확인
- [x] `voice/`, `vision/`, `robot_face/`와 ROS2 코드 역할 1차 구분
- [ ] 실제 ESP32 firmware 확인 후 `face_controller_node.py` 유지/삭제 최종 결정
- [ ] `scripts/` 실행/테스트/데이터/하드웨어 분류
- [x] `experience/` legacy 데이터 위치 재정의
- [ ] raw gesture data 위치 재정의
- [ ] `api/main.py`와 `api/web_main.py` 역할 명확화

### P2 — 사용 여부 확인 후 이동/삭제

- [ ] 이미 내용이 있는 폴더의 불필요한 `.gitkeep` 삭제
- [ ] 미사용 고객 앱 시제품 코드 archive 또는 삭제 여부 결정
- [ ] `★`가 포함된 문서 파일명 정규화
- [ ] `notebooks/ex2.ipynb` 목적 확인 후 명확한 이름으로 변경 또는 archive

## 6. 대청소 기간 협업 규칙

1. 기존 관리자 웹은 보존한다.
2. 기존 관리자 웹에 대규모 신규 UI 기능을 추가하지 않는다.
3. 진행 중인 팀원 브랜치가 있는 영역은 충돌하지 않도록 파일 이동을 보류한다.
4. 경로 변경은 해당 경로를 참조하는 코드·스크립트·문서를 함께 수정할 수 있을 때만 수행한다.
5. 새 기능에서 메뉴를 새로 하드코딩하지 않고 `config/menu_catalog.json` 기준으로 연결한다.
6. 현재 사양 문서와 과거 실험 로그를 구분한다.
7. 파일 삭제는 현재 사용 여부를 확인한 뒤 진행한다.
8. Git 이력에서 별도 하드웨어 검증 기록이 발견된 구현은 실물 상태 확인 전까지 삭제하지 않는다.

## 7. 결론

현재 저장소는 기능이 부족하다기보다 개발 과정에서 **현재 구현·시제품·실험·legacy·운영 문서가 함께 누적되면서 경계가 흐려진 상태**다.

안전한 정리 순서는 다음과 같다.

```text
문서 기준 통일
→ 현재/legacy 상태 표시
→ 실제 import·실행 경로 조사
→ 미사용 파일 분류
→ 경로 이동
→ 마지막에 삭제
```

현재까지 `experience/`, 빈 `vision/`, standalone `voice/STT/` 영역을 이 원칙에 따라 정리했다. 관리자 웹은 같은 원칙에 따라 **기존 구현을 보존한 채 새로 재구축**한다.
