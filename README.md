# 🎃 디지털 소외계층을 위한 Physical AI 무인매장 응대 로봇

 
> 복잡한 키오스크 조작 대신 **음성·비언어 표현·얼굴 인식**을 활용해 자연스럽게 주문하고 안내받을 수 있는 ROS2 기반 Physical AI 카페 응대 로봇입니다.

---

## **🔎 평가용 저장소 빠른 안내**

- **통합 시연 실행**: [`scripts/run_robot_with_monitor.sh`](scripts/run_robot_with_monitor.sh)
- **ROS2 인식–판단–행동 파이프라인**: [`ros2_ws/src/robot_controller/`](ros2_ws/src/robot_controller/)
- **현재 NLU 추론 코드**: [`nlu/`](nlu/)
- **KIPS Item Query 비교 실험**: [`experiments/nlu/kips_2026_item_query/`](experiments/nlu/kips_2026_item_query/)
- **TOD SLM 학습·평가 코드**: [`experiments/tod_slm/`](experiments/tod_slm/)
- **고객 앱**: [`apps/customer-mobile/`](apps/customer-mobile/)
- **주문·고객·얼굴 API**: [`api/`](api/)
- **서비스 메뉴 기준**: [`config/menu_catalog.json`](config/menu_catalog.json)

---

## **💡1. 프로젝트 개요**

### **1-1. 프로젝트 소개**

- **프로젝트 명** : 디지털 소외계층을 위한 Physical AI 무인매장 응대 로봇
- **프로젝트 정의** : 사용자의 음성, 고개 움직임, 손 제스처, 얼굴 정보를 인식하고 현재 대화 상태를 판단하여 주문·안내·개인화 서비스를 제공하는 Physical AI 기반 무인매장 응대 시스템
- **핵심 목표** : 무인 매장이 가지는 운영 효율성은 유지하면서, 사람의 친근함과 융통성을 함께 제공
<img width="1639" height="1229" alt="로봇 전신사진" src="https://github.com/user-attachments/assets/19146d49-7645-4f32-a00c-673136acb061" />

### **1-2. 개발 배경 및 필요성**

1) **개발 배경**
- 무인매장은 언택트 구매에 대한 니즈, 최저임금 및 임대료 상승의 매장 운영 비용 부담 등 다양한 원인으로 점차 증가하고 있다.
- 키오스크를 활용한 무인 주문 방식은 인력 부담을 줄이고 매장 운영 효율성을 높일 수 있어 무인매장의 주요 주문 방식으로 사용되고 있다.

2) **제작 동기 및 문제점**
- 디지털 소외 문제: 키오스크는 정보격차 심화로 인해 장애인 및 고연령층 등의 디지털 소외 계층의 무인매장 이용에 불편을 야기한다.
- 획일화된 무인매장 응대: 키오스크 중심의 무인매장은 모든 고객에게 동일한 방식으로 서비스를 제공하기 때문에 매장의 차별성을 만들기에 한계가 있다.
- 이에 무인매장이 가지는 가격 경쟁력과 운영 효율성을 유지하면서, 사람 직원이 제공하는 친근함과 융통성을 함께 제공하고자 한다.

3) **제작 목적**
- 디지털 소외 문제 해결: 고객이 대화를 통해 주문할 수 있도록 함으로써 누구나 보다 쉽게 주문할 수 있는 환경을 구현하고자 한다.
- 획일적인 무인매장 응대를 보완: 얼굴 인식을 활용하여 등록된 단골 고객을 식별하고 해당 , 고객의 선호 메뉴를 기억하여 개인화된 응대를 제공한다.


### **1-3. 프로젝트 특장점**

- **비언어적 표현 기반 자연스러운 응대** : 음성 응답과 함께 얼굴 표정, 고개 움직임, 팔 제스처를 출력해 주문 상태와 로봇의 반응을 직관적으로 전달
- **얼굴 인식 기반 단골 고객 개인화** : 등록된 얼굴 특징 벡터로 고객을 식별하고, 선호 메뉴와 주문 정보를 활용해 개인화된 인사와 메뉴 추천 제공
- **인식–판단–행동이 연결된 Physical AI** : 음성·얼굴·고개 움직임을 인식하고 NLU와 현재 주문 상태를 바탕으로 판단한 뒤, 음성·표정·물리 동작으로 반응
- **자체 NLU 기반 Edge AI** : 외부 생성형 AI API에 의존하지 않고 자체 학습한 NLU 모델을 Jetson Orin Nano에서 직접 추론하여 API 비용과 인터넷 의존도 절감

### **1-4. 주요 기능**

- **일반 음성 주문** : Faster-Whisper STT와 NLU를 이용해 자연어 주문 인식
- **복수 주문 구조화** : 한 문장 안의 여러 메뉴를 각각의 메뉴·온도·수량으로 분리
- **누락 정보 재질문** : 메뉴, 온도, 수량 중 필요한 정보가 빠진 경우 해당 항목만 다시 질문
- **주문 확인·수정·취소** : FSM을 이용해 주문 확인, 수정, 추가 주문, 취소 흐름 관리
- **비언어 입력** : 주문 확인 단계의 NOD/SHAKE, 수량 질문 단계의 손가락 제스처를 실제 입력으로 사용
- **공간 안내** : 화장실·픽업대 등 위치를 음성과 고개·팔 동작으로 함께 안내
- **단골 고객 개인화** : 얼굴 임베딩 기반 고객 식별 후 선호 주문 제안
- **사전주문 픽업** : 앱 사전주문 상태를 조회하고 준비 완료 주문의 픽업 위치 안내
- **관리자 POS 연동** : `RECEIVED → PREPARING → READY → PICKED_UP` 주문 상태 관리

### **1-5. 기대 효과 및 활용 분야**

- **기대 효과**
  - 디지털 기기 사용에 익숙하지 않은 사용자의 무인매장 접근성 향상
  - 음성과 비언어 표현을 함께 활용한 자연스러운 주문 경험 제공
  - 반복적인 주문·안내 업무를 자동화하여 매장 운영 부담 완화
  - 고객 앱과 얼굴 인식을 연계한 개인화 서비스 제공

- **활용 분야**
  - 무인 카페 및 프랜차이즈 매장
  - 베이커리·편의점 등 반복적인 고객 응대가 필요한 리테일 매장
  - 도서관·병원·주민센터·터미널 등 공공시설 안내 서비스

### **1-6. 기술 스택**

| 구분 | 기술 |
|---|---|
| **Edge / Robot** | NVIDIA Jetson Orin Nano, ROS2 Humble, Python |
| **STT / TTS** | Faster-Whisper, VAD, eSpeak-NG |
| **NLU** | koELECTRA-small, PyTorch, Item Query Transformer Decoder |
| **Vision** | OpenCV, MediaPipe, InsightFace `buffalo_l` |
| **Robot UI / Control** | ESP32 LCD, Head Motion, Arm Gesture, ROS2 Topic |
| **Customer App** | React Native, Expo, TypeScript |
| **POS Web** | React, Vite, Express |
| **Backend / Cloud** | FastAPI, Google Cloud Run, Firebase Authentication, Firestore, Firebase Storage |
| **Data / Service** | Menu Catalog, Order API, Cloud Relay |

---

## **💡2. 팀원 소개(이름 기재 X)**

> 개인정보를 기재하지 않고 프로젝트의 주요 역할 영역을 중심으로 정리했습니다.

| 역할 영역 | 주요 담당 |
|---|---|
| **AI / NLU** | 주문 데이터 구축·전처리, koELECTRA 학습, Item Query Decoder, 주문 슬롯 검증 |
| **Robot / ROS2** | Decision FSM, Action Node, TTS/LCD/고개·팔 동작 통합, 실물 로봇 시연 |
| **Vision / Personalization** | 사람·고개·손 제스처 인식, 얼굴 임베딩 등록·식별, 개인화 응대 |
| **App / Cloud / POS** | 고객용 사전주문 앱, Firebase·Cloud Run 연동, 관리자 POS 및 주문 상태 관리 |
| **Mentoring** | 시스템 설계 및 기술 자문 |

---

## **💡3. 시스템 구성도**

### **3-1. 서비스 전체 구성**

```mermaid
flowchart LR
    U[고객] -->|음성| STT[Faster-Whisper STT]
    U -->|고개·손·얼굴| VISION[Vision]

    STT --> NLU[koELECTRA + Item Query Decoder]
    NLU --> FSM[Decision FSM]
    VISION --> FSM

    FSM --> RESPONSE[Response / Action]
    RESPONSE --> TTS[TTS]
    RESPONSE --> LCD[LCD 표정]
    RESPONSE --> HEAD[고개 동작]
    RESPONSE --> ARM[팔 제스처]

    APP[고객 앱] --> CLOUD[Cloud Run / Firebase]
    CLOUD --> FSM
    FSM --> RELAY[Order API / Cloud Relay]
    RELAY --> POS[관리자 POS]
    POS --> RELAY
```

### **3-2. 주문 처리 흐름**

```mermaid
flowchart TD
    A[고객 감지] --> W[주문할게요 wake phrase 감지]
    W --> B[인사 및 주문 입력]
    B --> C[STT 음성 인식]
    C --> D[NLU 주문 구조화]
    D --> E{필수 정보가 모두 있는가?}
    E -- 아니오 --> F[누락된 메뉴·온도·수량 재질문]
    F --> D
    E -- 예 --> G[주문 확인]
    G --> H[음성 또는 NOD/SHAKE 응답]
    H --> I{주문 확정?}
    I -- 수정/추가 --> B
    I -- 확정 --> J[주문 서버 및 POS 반영]
    J --> K{고객이 계속 앞에 있는가?}
    K -- 예 --> L[다시 주문할게요 wake phrase 대기]
    K -- 아니오 --> M[퇴장 감지 후 다음 고객 세션 대기]
```

### **3-3. 얼굴 등록 및 개인화 흐름**

```mermaid
flowchart LR
    A[고객 앱 5방향 얼굴 촬영] --> B[Firebase Storage 임시 업로드]
    B --> C[Cloud Run Face Backend]
    C --> D[InsightFace 512차원 Embedding]
    D --> E[5개 Embedding 평균 Centroid]
    E --> F[Firestore users/uid]
    F --> G[Jetson 실시간 얼굴 식별]
    G --> H[선호 메뉴·사전주문 개인화 응대]
```

---

## **💡4. 작품 소개영상**

[![Pumpkin 작품 소개영상](https://img.youtube.com/vi/Mvfm7oixeZE/hqdefault.jpg)](https://youtu.be/Mvfm7oixeZE?si=AmzJ6K4wyu5zOT1B)

---

## **💡5. 핵심 소스코드**

### **5-1. FSM 기반 비언어 응답 처리**

- **소스 위치** : [`ros2_ws/src/robot_controller/robot_controller/decision_node_order_handoff.py`](ros2_ws/src/robot_controller/robot_controller/decision_node_order_handoff.py)
- **설명** : 사용자의 NOD/SHAKE를 항상 주문 입력으로 사용하는 것이 아니라, 주문 확인과 같은 **확인 상태에서만** 각각 `AFFIRM` / `DENY` 입력으로 변환합니다. 이를 통해 자연스러운 몸동작이 주문 흐름을 잘못 변경하는 것을 방지합니다.

```python
def make_user_gesture_decision(self, gesture: str):
    normalized = str(gesture or "").strip().upper()

    if normalized not in self.USER_GESTURES:
        return None
    if self.state not in self.CONFIRMATION_STATES:
        return None

    synthetic_input = {
        "intent": "AFFIRM" if normalized == "NOD" else "DENY",
        "input_modality": "VISION_GESTURE",
        "user_gesture": normalized,
        "confidence": 1.0,
    }

    if normalized == "NOD":
        return self.handle_affirm_intent(synthetic_input)
    return self.handle_deny_intent(synthetic_input)
```

### **5-2. 주문 NLU 모델**

- **비교 실험 및 재현 코드** : [`experiments/nlu/kips_2026_item_query/`](experiments/nlu/kips_2026_item_query/)
- **현재 추론 코드** : [`nlu/`](nlu/)
- **설명** : koELECTRA Encoder가 문장의 문맥 특징을 추출하고, 학습 가능한 Item Query를 Transformer Decoder에 입력하여 복수 주문의 **메뉴·온도·수량을 항목별로 예측**합니다.

### **5-3. 얼굴 등록 및 실시간 식별**

- **고객 앱** : [`apps/customer-mobile/`](apps/customer-mobile/)
- **Face Backend** : [`face_backend/`](face_backend/)
- **Jetson 실시간 인식** : [`ros2_ws/src/robot_controller/robot_controller/realtime_face_recognition.py`](ros2_ws/src/robot_controller/robot_controller/realtime_face_recognition.py)
- **설명** : 앱에서 촬영한 5방향 얼굴을 Cloud Run에서 512차원 임베딩으로 변환하고 평균 centroid를 Firestore에 저장합니다. Jetson은 실시간 얼굴 임베딩과 등록 정보를 비교하여 고객을 식별합니다.

---

## **📁 주요 디렉터리**

```text
pumpkin_public/
├── api/             # FastAPI 주문·고객·얼굴 API
├── apps/
│   ├── customer-mobile/  # 고객 앱
│   ├── pos-web/          # 관리자 POS
│   └── monitor-web/      # 로봇 5인치 고객 화면
├── cloud_relay/     # Cloud Run 주문 Relay
├── config/          # 메뉴 카탈로그 및 공통 설정
├── data/            # 제출본에 필요한 학습·테스트 데이터
├── experiments/     # KIPS NLU 비교 실험 및 TOD SLM 학습·평가
├── face_backend/    # 얼굴 임베딩 Cloud Run Backend
├── nlu/             # 현재 NLU 추론 코드
├── robot_face/      # ESP32 LCD 및 얼굴 표시 제어
├── ros2_ws/         # ROS2 기반 로봇 통합 Runtime
└── scripts/         # 실행·테스트·시연 스크립트
```

---

## **🔎 프로젝트 핵심 흐름 요약**

```text
고객 음성 / 비언어 입력
→ STT / Vision
→ NLU
→ FSM 기반 대화 상태 판단
→ TTS + LCD + 고개·팔 동작
→ 주문 서버 / POS

고객 앱 얼굴 등록 / 사전주문
→ Firebase / Cloud Run
→ Jetson 얼굴 인식 및 고객 식별
→ 개인화 주문 제안 / 사전주문 픽업 안내
```


---

## **🚀 실물 로봇 시연 실행**

Jetson Orin Nano에서 5인치 고객 화면과 ROS2 로봇 파이프라인을 함께 실행하는 최종 시연 진입점입니다.

```bash
cd ~/pumpkin
bash scripts/run_robot_with_monitor.sh
```

현재 production runtime은 STT, Vision, NLU, Decision FSM, TTS, LCD 표정, 고개·팔 제어를 ROS2로 통합합니다.

---

## **📚 전체 파일 가이드**

현재 `cleanup-hanium-submission` 브랜치에서 Git이 추적하는 **479개 파일 전체**를 폴더별로 정리했습니다. 파일명을 누르면 실제 소스로 이동합니다.

<details>
<summary><strong>최상위(root)/</strong> — 저장소 전체 설정·실행 환경·최상위 문서 (13개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`.dockerignore`](.dockerignore) |  프로젝트 소스·설정·데이터 파일입니다. | 97 B |
| [`.gitignore`](.gitignore) |  프로젝트 소스·설정·데이터 파일입니다. | 1.2 KB |
| [`Dockerfile`](Dockerfile) | Dockerfile 프로젝트 소스·설정·데이터 파일입니다. | 325 B |
| [`Dockerfile.face`](Dockerfile.face) | Dockerfile 프로젝트 소스·설정·데이터 파일입니다. | 946 B |
| [`firebase.json`](firebase.json) | firebase 설정 또는 구조화 데이터 파일입니다. | 56 B |
| [`firestore.rules`](firestore.rules) | firestore 프로젝트 소스·설정·데이터 파일입니다. | 547 B |
| [`JETSON_RUNTIME_README.md`](JETSON_RUNTIME_README.md) | JETSON RUNTIME README 관련 프로젝트 문서입니다. | 3.1 KB |
| [`pixi.lock`](pixi.lock) | pixi 프로젝트 소스·설정·데이터 파일입니다. | 514.6 KB |
| [`pixi.toml`](pixi.toml) | pixi 프로젝트 소스·설정·데이터 파일입니다. | 1.6 KB |
| [`README.md`](README.md) | 한이음 제출용 프로젝트 소개, 실행 흐름, 주요 코드와 전체 파일 가이드입니다. | 125.6 KB |
| [`requirements-face-recognition.txt`](requirements-face-recognition.txt) | requirements face recognition 프로젝트 소스·설정·데이터 파일입니다. | 279 B |
| [`requirements.txt`](requirements.txt) | requirements 프로젝트 소스·설정·데이터 파일입니다. | 205 B |
| [`run_customer_mobile_windows.cmd`](run_customer_mobile_windows.cmd) | run customer mobile windows 프로젝트 소스·설정·데이터 파일입니다. | 339 B |

</details>

<details>
<summary><strong>.github/</strong> — GitHub Actions 자동 검증/CI (4개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`.github/workflows/customer-mobile-check.yml`](.github/workflows/customer-mobile-check.yml) | customer mobile check 자동 검증을 수행하는 GitHub Actions workflow입니다. | 808 B |
| [`.github/workflows/demo-web-check.yml`](.github/workflows/demo-web-check.yml) | demo web check 자동 검증을 수행하는 GitHub Actions workflow입니다. | 1.2 KB |
| [`.github/workflows/face-backend-check.yml`](.github/workflows/face-backend-check.yml) | face backend check 자동 검증을 수행하는 GitHub Actions workflow입니다. | 781 B |
| [`.github/workflows/validate_tod_training.yml`](.github/workflows/validate_tod_training.yml) | validate tod training 자동 검증을 수행하는 GitHub Actions workflow입니다. | 1.8 KB |

</details>

<details>
<summary><strong>api/</strong> — FastAPI 주문·고객·얼굴 백엔드 API (22개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`api/__init__.py`](api/__init__.py) | Python 패키지 초기화 파일입니다. | 55 B |
| [`api/customer_store.py`](api/customer_store.py) | customer store 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 5.3 KB |
| [`api/face_embedding_service.py`](api/face_embedding_service.py) | face embedding service 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 11.9 KB |
| [`api/face_enrollment_store.py`](api/face_enrollment_store.py) | face enrollment store 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 8.5 KB |
| [`api/face_pipeline.py`](api/face_pipeline.py) | face pipeline 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 2.3 KB |
| [`api/firebase_face_backend.py`](api/firebase_face_backend.py) | firebase face backend 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 5.5 KB |
| [`api/main.py`](api/main.py) | main 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 10.8 KB |
| [`api/repositories/__init__.py`](api/repositories/__init__.py) | Python 패키지 초기화 파일입니다. | 0 B |
| [`api/repositories/base.py`](api/repositories/base.py) | base 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 581 B |
| [`api/repositories/sqlite_order_repository.py`](api/repositories/sqlite_order_repository.py) | sqlite order repository 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 7.5 KB |
| [`api/requirements.txt`](api/requirements.txt) | requirements 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 155 B |
| [`api/ros_bridge.py`](api/ros_bridge.py) | ros bridge 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 11.7 KB |
| [`api/ros_process_manager.py`](api/ros_process_manager.py) | ros process manager 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 3.3 KB |
| [`api/routers/__init__.py`](api/routers/__init__.py) | Python 패키지 초기화 파일입니다. | 0 B |
| [`api/routers/face_embeddings.py`](api/routers/face_embeddings.py) | face embeddings 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 1.8 KB |
| [`api/routers/faces.py`](api/routers/faces.py) | faces 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 1020 B |
| [`api/routers/orders.py`](api/routers/orders.py) | orders 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 2.0 KB |
| [`api/schemas/__init__.py`](api/schemas/__init__.py) | Python 패키지 초기화 파일입니다. | 0 B |
| [`api/schemas/order.py`](api/schemas/order.py) | order 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 1.8 KB |
| [`api/services/__init__.py`](api/services/__init__.py) | Python 패키지 초기화 파일입니다. | 0 B |
| [`api/services/order_service.py`](api/services/order_service.py) | order service 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 1.5 KB |
| [`api/web_main.py`](api/web_main.py) | web main 주문·고객·얼굴 관련 FastAPI 백엔드 파일입니다. | 2.2 KB |

</details>

<details>
<summary><strong>apps/</strong> — 고객 앱·POS·로봇 모니터 애플리케이션 (144개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`apps/customer-mobile/.env.example`](apps/customer-mobile/.env.example) | .env 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 896 B |
| [`apps/customer-mobile/.gitignore`](apps/customer-mobile/.gitignore) |  고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 8 B |
| [`apps/customer-mobile/app.json`](apps/customer-mobile/app.json) | Expo/React Native 앱 설정입니다. | 737 B |
| [`apps/customer-mobile/App.tsx`](apps/customer-mobile/App.tsx) | App 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 50 B |
| [`apps/customer-mobile/ATTRIBUTIONS.md`](apps/customer-mobile/ATTRIBUTIONS.md) | ATTRIBUTIONS 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 290 B |
| [`apps/customer-mobile/FaceEnrollmentDemoApp.tsx`](apps/customer-mobile/FaceEnrollmentDemoApp.tsx) | FaceEnrollmentDemoApp 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 9.5 KB |
| [`apps/customer-mobile/guidelines/Guidelines.md`](apps/customer-mobile/guidelines/Guidelines.md) | Guidelines 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.5 KB |
| [`apps/customer-mobile/index.html`](apps/customer-mobile/index.html) | index 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 701 B |
| [`apps/customer-mobile/index.ts`](apps/customer-mobile/index.ts) | index 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 487 B |
| [`apps/customer-mobile/package.json`](apps/customer-mobile/package.json) | 해당 앱의 npm 의존성과 실행 명령을 정의합니다. | 920 B |
| [`apps/customer-mobile/postcss.config.mjs`](apps/customer-mobile/postcss.config.mjs) | postcss.config 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 68 B |
| [`apps/customer-mobile/README.md`](apps/customer-mobile/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 4.4 KB |
| [`apps/customer-mobile/src/api/faceEnrollmentApi.ts`](apps/customer-mobile/src/api/faceEnrollmentApi.ts) | faceEnrollmentApi 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.0 KB |
| [`apps/customer-mobile/src/api/faceProfileApi.ts`](apps/customer-mobile/src/api/faceProfileApi.ts) | faceProfileApi 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.7 KB |
| [`apps/customer-mobile/src/api/orderApi.ts`](apps/customer-mobile/src/api/orderApi.ts) | orderApi 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.3 KB |
| [`apps/customer-mobile/src/app/App.tsx`](apps/customer-mobile/src/app/App.tsx) | App 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 275 B |
| [`apps/customer-mobile/src/app/Attributions.md`](apps/customer-mobile/src/app/Attributions.md) | Attributions 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 289 B |
| [`apps/customer-mobile/src/app/components/AboutUs.tsx`](apps/customer-mobile/src/app/components/AboutUs.tsx) | AboutUs 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 6.6 KB |
| [`apps/customer-mobile/src/app/components/AdvancedProductCatalog.tsx`](apps/customer-mobile/src/app/components/AdvancedProductCatalog.tsx) | AdvancedProductCatalog 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 22.4 KB |
| [`apps/customer-mobile/src/app/components/AuthScreen.tsx`](apps/customer-mobile/src/app/components/AuthScreen.tsx) | AuthScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 20.6 KB |
| [`apps/customer-mobile/src/app/components/BlogSection.tsx`](apps/customer-mobile/src/app/components/BlogSection.tsx) | BlogSection 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 14.1 KB |
| [`apps/customer-mobile/src/app/components/BottomNavigation.tsx`](apps/customer-mobile/src/app/components/BottomNavigation.tsx) | BottomNavigation 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.5 KB |
| [`apps/customer-mobile/src/app/components/Cart.tsx`](apps/customer-mobile/src/app/components/Cart.tsx) | Cart 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 5.0 KB |
| [`apps/customer-mobile/src/app/components/Checkout.tsx`](apps/customer-mobile/src/app/components/Checkout.tsx) | Checkout 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 7.2 KB |
| [`apps/customer-mobile/src/app/components/Contact.tsx`](apps/customer-mobile/src/app/components/Contact.tsx) | Contact 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 6.2 KB |
| [`apps/customer-mobile/src/app/components/EnhancedHomeScreen.tsx`](apps/customer-mobile/src/app/components/EnhancedHomeScreen.tsx) | EnhancedHomeScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 16.2 KB |
| [`apps/customer-mobile/src/app/components/EnhancedProductDetails.tsx`](apps/customer-mobile/src/app/components/EnhancedProductDetails.tsx) | EnhancedProductDetails 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 23.4 KB |
| [`apps/customer-mobile/src/app/components/figma/ImageWithFallback.tsx`](apps/customer-mobile/src/app/components/figma/ImageWithFallback.tsx) | ImageWithFallback 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.1 KB |
| [`apps/customer-mobile/src/app/components/Footer.tsx`](apps/customer-mobile/src/app/components/Footer.tsx) | Footer 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 21.8 KB |
| [`apps/customer-mobile/src/app/components/Header.tsx`](apps/customer-mobile/src/app/components/Header.tsx) | Header 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 14.5 KB |
| [`apps/customer-mobile/src/app/components/HomeScreen.tsx`](apps/customer-mobile/src/app/components/HomeScreen.tsx) | HomeScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 5.9 KB |
| [`apps/customer-mobile/src/app/components/LoyaltyProgram.tsx`](apps/customer-mobile/src/app/components/LoyaltyProgram.tsx) | LoyaltyProgram 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 6.5 KB |
| [`apps/customer-mobile/src/app/components/ProductCatalog.tsx`](apps/customer-mobile/src/app/components/ProductCatalog.tsx) | ProductCatalog 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 7.3 KB |
| [`apps/customer-mobile/src/app/components/ProductDetails.tsx`](apps/customer-mobile/src/app/components/ProductDetails.tsx) | ProductDetails 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 9.3 KB |
| [`apps/customer-mobile/src/app/components/ui/accordion.tsx`](apps/customer-mobile/src/app/components/ui/accordion.tsx) | accordion 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.0 KB |
| [`apps/customer-mobile/src/app/components/ui/alert-dialog.tsx`](apps/customer-mobile/src/app/components/ui/alert-dialog.tsx) | alert dialog 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.8 KB |
| [`apps/customer-mobile/src/app/components/ui/alert.tsx`](apps/customer-mobile/src/app/components/ui/alert.tsx) | alert 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.6 KB |
| [`apps/customer-mobile/src/app/components/ui/aspect-ratio.tsx`](apps/customer-mobile/src/app/components/ui/aspect-ratio.tsx) | aspect ratio 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 290 B |
| [`apps/customer-mobile/src/app/components/ui/avatar.tsx`](apps/customer-mobile/src/app/components/ui/avatar.tsx) | avatar 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.1 KB |
| [`apps/customer-mobile/src/app/components/ui/badge.tsx`](apps/customer-mobile/src/app/components/ui/badge.tsx) | badge 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.6 KB |
| [`apps/customer-mobile/src/app/components/ui/breadcrumb.tsx`](apps/customer-mobile/src/app/components/ui/breadcrumb.tsx) | breadcrumb 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.3 KB |
| [`apps/customer-mobile/src/app/components/ui/button.tsx`](apps/customer-mobile/src/app/components/ui/button.tsx) | button 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.2 KB |
| [`apps/customer-mobile/src/app/components/ui/calendar.tsx`](apps/customer-mobile/src/app/components/ui/calendar.tsx) | calendar 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.9 KB |
| [`apps/customer-mobile/src/app/components/ui/card.tsx`](apps/customer-mobile/src/app/components/ui/card.tsx) | card 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.9 KB |
| [`apps/customer-mobile/src/app/components/ui/carousel.tsx`](apps/customer-mobile/src/app/components/ui/carousel.tsx) | carousel 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 5.5 KB |
| [`apps/customer-mobile/src/app/components/ui/chart.tsx`](apps/customer-mobile/src/app/components/ui/chart.tsx) | chart 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 9.6 KB |
| [`apps/customer-mobile/src/app/components/ui/checkbox.tsx`](apps/customer-mobile/src/app/components/ui/checkbox.tsx) | checkbox 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.2 KB |
| [`apps/customer-mobile/src/app/components/ui/collapsible.tsx`](apps/customer-mobile/src/app/components/ui/collapsible.tsx) | collapsible 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 812 B |
| [`apps/customer-mobile/src/app/components/ui/command.tsx`](apps/customer-mobile/src/app/components/ui/command.tsx) | command 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 4.6 KB |
| [`apps/customer-mobile/src/app/components/ui/context-menu.tsx`](apps/customer-mobile/src/app/components/ui/context-menu.tsx) | context menu 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 8.1 KB |
| [`apps/customer-mobile/src/app/components/ui/dialog.tsx`](apps/customer-mobile/src/app/components/ui/dialog.tsx) | dialog 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.8 KB |
| [`apps/customer-mobile/src/app/components/ui/drawer.tsx`](apps/customer-mobile/src/app/components/ui/drawer.tsx) | drawer 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 4.0 KB |
| [`apps/customer-mobile/src/app/components/ui/dropdown-menu.tsx`](apps/customer-mobile/src/app/components/ui/dropdown-menu.tsx) | dropdown menu 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 8.1 KB |
| [`apps/customer-mobile/src/app/components/ui/form.tsx`](apps/customer-mobile/src/app/components/ui/form.tsx) | form 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.7 KB |
| [`apps/customer-mobile/src/app/components/ui/hover-card.tsx`](apps/customer-mobile/src/app/components/ui/hover-card.tsx) | hover card 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.5 KB |
| [`apps/customer-mobile/src/app/components/ui/input-otp.tsx`](apps/customer-mobile/src/app/components/ui/input-otp.tsx) | input otp 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.2 KB |
| [`apps/customer-mobile/src/app/components/ui/input.tsx`](apps/customer-mobile/src/app/components/ui/input.tsx) | input 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 963 B |
| [`apps/customer-mobile/src/app/components/ui/label.tsx`](apps/customer-mobile/src/app/components/ui/label.tsx) | label 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 620 B |
| [`apps/customer-mobile/src/app/components/ui/menubar.tsx`](apps/customer-mobile/src/app/components/ui/menubar.tsx) | menubar 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 8.2 KB |
| [`apps/customer-mobile/src/app/components/ui/navigation-menu.tsx`](apps/customer-mobile/src/app/components/ui/navigation-menu.tsx) | navigation menu 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 6.5 KB |
| [`apps/customer-mobile/src/app/components/ui/pagination.tsx`](apps/customer-mobile/src/app/components/ui/pagination.tsx) | pagination 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.7 KB |
| [`apps/customer-mobile/src/app/components/ui/popover.tsx`](apps/customer-mobile/src/app/components/ui/popover.tsx) | popover 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.6 KB |
| [`apps/customer-mobile/src/app/components/ui/progress.tsx`](apps/customer-mobile/src/app/components/ui/progress.tsx) | progress 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 749 B |
| [`apps/customer-mobile/src/app/components/ui/radio-group.tsx`](apps/customer-mobile/src/app/components/ui/radio-group.tsx) | radio group 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.5 KB |
| [`apps/customer-mobile/src/app/components/ui/resizable.tsx`](apps/customer-mobile/src/app/components/ui/resizable.tsx) | resizable 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.0 KB |
| [`apps/customer-mobile/src/app/components/ui/scroll-area.tsx`](apps/customer-mobile/src/app/components/ui/scroll-area.tsx) | scroll area 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.6 KB |
| [`apps/customer-mobile/src/app/components/ui/select.tsx`](apps/customer-mobile/src/app/components/ui/select.tsx) | select 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 6.1 KB |
| [`apps/customer-mobile/src/app/components/ui/separator.tsx`](apps/customer-mobile/src/app/components/ui/separator.tsx) | separator 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 713 B |
| [`apps/customer-mobile/src/app/components/ui/sheet.tsx`](apps/customer-mobile/src/app/components/ui/sheet.tsx) | sheet 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 4.0 KB |
| [`apps/customer-mobile/src/app/components/ui/sidebar.tsx`](apps/customer-mobile/src/app/components/ui/sidebar.tsx) | sidebar 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 21.2 KB |
| [`apps/customer-mobile/src/app/components/ui/skeleton.tsx`](apps/customer-mobile/src/app/components/ui/skeleton.tsx) | skeleton 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 275 B |
| [`apps/customer-mobile/src/app/components/ui/slider.tsx`](apps/customer-mobile/src/app/components/ui/slider.tsx) | slider 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.0 KB |
| [`apps/customer-mobile/src/app/components/ui/sonner.tsx`](apps/customer-mobile/src/app/components/ui/sonner.tsx) | sonner 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 583 B |
| [`apps/customer-mobile/src/app/components/ui/switch.tsx`](apps/customer-mobile/src/app/components/ui/switch.tsx) | switch 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.2 KB |
| [`apps/customer-mobile/src/app/components/ui/table.tsx`](apps/customer-mobile/src/app/components/ui/table.tsx) | table 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.4 KB |
| [`apps/customer-mobile/src/app/components/ui/tabs.tsx`](apps/customer-mobile/src/app/components/ui/tabs.tsx) | tabs 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.9 KB |
| [`apps/customer-mobile/src/app/components/ui/textarea.tsx`](apps/customer-mobile/src/app/components/ui/textarea.tsx) | textarea 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 767 B |
| [`apps/customer-mobile/src/app/components/ui/toggle-group.tsx`](apps/customer-mobile/src/app/components/ui/toggle-group.tsx) | toggle group 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.9 KB |
| [`apps/customer-mobile/src/app/components/ui/toggle.tsx`](apps/customer-mobile/src/app/components/ui/toggle.tsx) | toggle 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.5 KB |
| [`apps/customer-mobile/src/app/components/ui/tooltip.tsx`](apps/customer-mobile/src/app/components/ui/tooltip.tsx) | tooltip 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.9 KB |
| [`apps/customer-mobile/src/app/components/ui/use-mobile.ts`](apps/customer-mobile/src/app/components/ui/use-mobile.ts) | use mobile 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 585 B |
| [`apps/customer-mobile/src/app/components/ui/utils.ts`](apps/customer-mobile/src/app/components/ui/utils.ts) | utils 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 169 B |
| [`apps/customer-mobile/src/app/components/UserProfile.tsx`](apps/customer-mobile/src/app/components/UserProfile.tsx) | UserProfile 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 21.0 KB |
| [`apps/customer-mobile/src/app/src/context/CartContext.tsx`](apps/customer-mobile/src/app/src/context/CartContext.tsx) | CartContext 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.6 KB |
| [`apps/customer-mobile/src/app/src/data/menu.ts`](apps/customer-mobile/src/app/src/data/menu.ts) | menu 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.0 KB |
| [`apps/customer-mobile/src/app/src/layouts/MobileLayout.tsx`](apps/customer-mobile/src/app/src/layouts/MobileLayout.tsx) | MobileLayout 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.8 KB |
| [`apps/customer-mobile/src/app/src/pages/Cart.tsx`](apps/customer-mobile/src/app/src/pages/Cart.tsx) | Cart 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 7.0 KB |
| [`apps/customer-mobile/src/app/src/pages/Home.tsx`](apps/customer-mobile/src/app/src/pages/Home.tsx) | Home 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 5.2 KB |
| [`apps/customer-mobile/src/app/src/pages/Order.tsx`](apps/customer-mobile/src/app/src/pages/Order.tsx) | Order 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.2 KB |
| [`apps/customer-mobile/src/app/src/pages/ProductDetail.tsx`](apps/customer-mobile/src/app/src/pages/ProductDetail.tsx) | ProductDetail 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 7.5 KB |
| [`apps/customer-mobile/src/app/src/routes.tsx`](apps/customer-mobile/src/app/src/routes.tsx) | routes 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1020 B |
| [`apps/customer-mobile/src/assets/a036880becd196a5d2e97bf1f820e1310f4579dc.png`](apps/customer-mobile/src/assets/a036880becd196a5d2e97bf1f820e1310f4579dc.png) | a036880becd196a5d2e97bf1f820e1310f4579dc 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 7.8 KB |
| [`apps/customer-mobile/src/auth/AuthProvider.tsx`](apps/customer-mobile/src/auth/AuthProvider.tsx) | AuthProvider 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.7 KB |
| [`apps/customer-mobile/src/components/FaceCameraView.tsx`](apps/customer-mobile/src/components/FaceCameraView.tsx) | FaceCameraView 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 8.4 KB |
| [`apps/customer-mobile/src/components/FaceGuideOverlay.tsx`](apps/customer-mobile/src/components/FaceGuideOverlay.tsx) | FaceGuideOverlay 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.0 KB |
| [`apps/customer-mobile/src/components/RegistrationStatusBadge.tsx`](apps/customer-mobile/src/components/RegistrationStatusBadge.tsx) | RegistrationStatusBadge 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.4 KB |
| [`apps/customer-mobile/src/CustomerMobileApp.tsx`](apps/customer-mobile/src/CustomerMobileApp.tsx) | CustomerMobileApp 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 28.0 KB |
| [`apps/customer-mobile/src/firebase/config.ts`](apps/customer-mobile/src/firebase/config.ts) | config 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.2 KB |
| [`apps/customer-mobile/src/firebase/faceEmbeddingBackend.ts`](apps/customer-mobile/src/firebase/faceEmbeddingBackend.ts) | faceEmbeddingBackend 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.3 KB |
| [`apps/customer-mobile/src/firebase/faceEnrollment.ts`](apps/customer-mobile/src/firebase/faceEnrollment.ts) | faceEnrollment 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 5.2 KB |
| [`apps/customer-mobile/src/FirebaseAuthRoot.tsx`](apps/customer-mobile/src/FirebaseAuthRoot.tsx) | FirebaseAuthRoot 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.3 KB |
| [`apps/customer-mobile/src/main.tsx`](apps/customer-mobile/src/main.tsx) | main 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 183 B |
| [`apps/customer-mobile/src/native/CareScreen.tsx`](apps/customer-mobile/src/native/CareScreen.tsx) | CareScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 11.1 KB |
| [`apps/customer-mobile/src/native/menuData.ts`](apps/customer-mobile/src/native/menuData.ts) | menuData 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 1.6 KB |
| [`apps/customer-mobile/src/native/theme.ts`](apps/customer-mobile/src/native/theme.ts) | theme 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 325 B |
| [`apps/customer-mobile/src/native/types.ts`](apps/customer-mobile/src/native/types.ts) | types 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 741 B |
| [`apps/customer-mobile/src/screens/AuthScreen.tsx`](apps/customer-mobile/src/screens/AuthScreen.tsx) | AuthScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 5.1 KB |
| [`apps/customer-mobile/src/screens/FaceCaptureScreen.tsx`](apps/customer-mobile/src/screens/FaceCaptureScreen.tsx) | FaceCaptureScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 8.8 KB |
| [`apps/customer-mobile/src/screens/FaceConsentScreen.tsx`](apps/customer-mobile/src/screens/FaceConsentScreen.tsx) | FaceConsentScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 11.7 KB |
| [`apps/customer-mobile/src/screens/FaceRegistrationResultScreen.tsx`](apps/customer-mobile/src/screens/FaceRegistrationResultScreen.tsx) | FaceRegistrationResultScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 3.4 KB |
| [`apps/customer-mobile/src/screens/ProfileScreen.tsx`](apps/customer-mobile/src/screens/ProfileScreen.tsx) | ProfileScreen 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 10.5 KB |
| [`apps/customer-mobile/src/styles/default_theme.css`](apps/customer-mobile/src/styles/default_theme.css) | default theme 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 4.2 KB |
| [`apps/customer-mobile/src/styles/globals.css`](apps/customer-mobile/src/styles/globals.css) | globals 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 7.7 KB |
| [`apps/customer-mobile/src/styles/index.css`](apps/customer-mobile/src/styles/index.css) | index 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 156 B |
| [`apps/customer-mobile/src/types/faceProfile.ts`](apps/customer-mobile/src/types/faceProfile.ts) | faceProfile 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 2.1 KB |
| [`apps/customer-mobile/src/utils/imageValidation.ts`](apps/customer-mobile/src/utils/imageValidation.ts) | imageValidation 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 796 B |
| [`apps/customer-mobile/tsconfig.json`](apps/customer-mobile/tsconfig.json) | TypeScript 컴파일과 타입 검사 설정입니다. | 429 B |
| [`apps/customer-mobile/vite.config.ts`](apps/customer-mobile/vite.config.ts) | vite.config 고객 모바일 앱의 화면·상태·API·설정 파일입니다. | 764 B |
| [`apps/demo-web/app.js`](apps/demo-web/app.js) | app 프로젝트 소스·설정·데이터 파일입니다. | 11.4 KB |
| [`apps/demo-web/index.html`](apps/demo-web/index.html) | index 프로젝트 소스·설정·데이터 파일입니다. | 2.9 KB |
| [`apps/demo-web/README.md`](apps/demo-web/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 7.6 KB |
| [`apps/demo-web/server.py`](apps/demo-web/server.py) | server 기능을 구현하는 Python 소스입니다. | 21.2 KB |
| [`apps/demo-web/styles.css`](apps/demo-web/styles.css) | styles 프로젝트 소스·설정·데이터 파일입니다. | 9.6 KB |
| [`apps/monitor-web/app.js`](apps/monitor-web/app.js) | app 로봇 5인치 고객 화면의 표시·상태 파일입니다. | 8.7 KB |
| [`apps/monitor-web/index.html`](apps/monitor-web/index.html) | index 로봇 5인치 고객 화면의 표시·상태 파일입니다. | 3.1 KB |
| [`apps/monitor-web/monitor_state.py`](apps/monitor-web/monitor_state.py) | monitor state 로봇 5인치 고객 화면의 표시·상태 파일입니다. | 8.4 KB |
| [`apps/monitor-web/README.md`](apps/monitor-web/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 2.9 KB |
| [`apps/monitor-web/requirements.txt`](apps/monitor-web/requirements.txt) | requirements 로봇 5인치 고객 화면의 표시·상태 파일입니다. | 58 B |
| [`apps/monitor-web/server.py`](apps/monitor-web/server.py) | server 로봇 5인치 고객 화면의 표시·상태 파일입니다. | 5.4 KB |
| [`apps/monitor-web/styles.css`](apps/monitor-web/styles.css) | styles 로봇 5인치 고객 화면의 표시·상태 파일입니다. | 6.7 KB |
| [`apps/pos-web/.env.example`](apps/pos-web/.env.example) | .env 관리자 POS 웹의 화면·상태·설정 파일입니다. | 575 B |
| [`apps/pos-web/HANDOFF.md`](apps/pos-web/HANDOFF.md) | HANDOFF 관리자 POS 웹의 화면·상태·설정 파일입니다. | 7.6 KB |
| [`apps/pos-web/index.html`](apps/pos-web/index.html) | index 관리자 POS 웹의 화면·상태·설정 파일입니다. | 348 B |
| [`apps/pos-web/package-lock.json`](apps/pos-web/package-lock.json) | npm 의존성 버전과 무결성 정보를 고정합니다. | 163.7 KB |
| [`apps/pos-web/package.json`](apps/pos-web/package.json) | 해당 앱의 npm 의존성과 실행 명령을 정의합니다. | 757 B |
| [`apps/pos-web/README.md`](apps/pos-web/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 5.2 KB |
| [`apps/pos-web/server/index.mjs`](apps/pos-web/server/index.mjs) | index 관리자 POS 웹의 화면·상태·설정 파일입니다. | 11.4 KB |
| [`apps/pos-web/src/App.tsx`](apps/pos-web/src/App.tsx) | App 관리자 POS 웹의 화면·상태·설정 파일입니다. | 35.5 KB |
| [`apps/pos-web/src/main.tsx`](apps/pos-web/src/main.tsx) | main 관리자 POS 웹의 화면·상태·설정 파일입니다. | 267 B |
| [`apps/pos-web/src/manufacturing-board.css`](apps/pos-web/src/manufacturing-board.css) | manufacturing board 관리자 POS 웹의 화면·상태·설정 파일입니다. | 7.3 KB |
| [`apps/pos-web/src/passwordless.css`](apps/pos-web/src/passwordless.css) | passwordless 관리자 POS 웹의 화면·상태·설정 파일입니다. | 114 B |
| [`apps/pos-web/src/styles.css`](apps/pos-web/src/styles.css) | styles 관리자 POS 웹의 화면·상태·설정 파일입니다. | 18.5 KB |
| [`apps/pos-web/tsconfig.json`](apps/pos-web/tsconfig.json) | TypeScript 컴파일과 타입 검사 설정입니다. | 527 B |
| [`apps/pos-web/vite.config.ts`](apps/pos-web/vite.config.ts) | vite.config 관리자 POS 웹의 화면·상태·설정 파일입니다. | 228 B |

</details>

<details>
<summary><strong>cloud_relay/</strong> — 클라우드 주문 상태 중계 서비스 (3개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`cloud_relay/__init__.py`](cloud_relay/__init__.py) | Python 패키지 초기화 파일입니다. | 43 B |
| [`cloud_relay/main.py`](cloud_relay/main.py) | main 기능을 구현하는 Python 소스입니다. | 11.2 KB |
| [`cloud_relay/requirements.txt`](cloud_relay/requirements.txt) | requirements 프로젝트 소스·설정·데이터 파일입니다. | 77 B |

</details>

<details>
<summary><strong>config/</strong> — 서비스 공통 설정과 메뉴 카탈로그 (1개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`config/menu_catalog.json`](config/menu_catalog.json) | 서비스 메뉴명·가격·별칭·허용 온도의 Single Source of Truth입니다. | 2.1 KB |

</details>

<details>
<summary><strong>data/</strong> — NLU/TOD 학습·검증·테스트 데이터 (12개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`data/single_menu_quantity_1_20_augmented.csv`](data/single_menu_quantity_1_20_augmented.csv) | single menu quantity 1 20 augmented 학습 데이터 또는 실험 결과 CSV입니다. | 2.3 MB |
| [`data/structure_b_test.jsonl`](data/structure_b_test.jsonl) | structure b test 학습·검증·평가에 사용하는 JSON Lines 데이터입니다. | 552.3 KB |
| [`data/structure_b_train_valid.jsonl`](data/structure_b_train_valid.jsonl) | structure b train valid 학습·검증·평가에 사용하는 JSON Lines 데이터입니다. | 7.5 MB |
| [`data/tod/pumpkin_tod_v1_multiturn_stats.json`](data/tod/pumpkin_tod_v1_multiturn_stats.json) | pumpkin tod v1 multiturn stats 데이터셋 통계·설정·요약 JSON입니다. | 2.5 KB |
| [`data/tod/pumpkin_tod_v1_review_results.jsonl`](data/tod/pumpkin_tod_v1_review_results.jsonl) | pumpkin tod v1 review results 학습·검증·평가에 사용하는 JSON Lines 데이터입니다. | 72.4 KB |
| [`data/tod/pumpkin_tod_v1_review_sample.jsonl`](data/tod/pumpkin_tod_v1_review_sample.jsonl) | pumpkin tod v1 review sample 학습·검증·평가에 사용하는 JSON Lines 데이터입니다. | 280.3 KB |
| [`data/tod/pumpkin_tod_v1_review_stats.json`](data/tod/pumpkin_tod_v1_review_stats.json) | pumpkin tod v1 review stats 데이터셋 통계·설정·요약 JSON입니다. | 1.3 KB |
| [`data/tod/pumpkin_tod_v1_stats.json`](data/tod/pumpkin_tod_v1_stats.json) | pumpkin tod v1 stats 데이터셋 통계·설정·요약 JSON입니다. | 22.3 KB |
| [`data/tod/qwen/pumpkin_tod_v1_qwen_stats.json`](data/tod/qwen/pumpkin_tod_v1_qwen_stats.json) | pumpkin tod v1 qwen stats 데이터셋 통계·설정·요약 JSON입니다. | 8.3 KB |
| [`data/tod/qwen/pumpkin_tod_v1_qwen_test.jsonl`](data/tod/qwen/pumpkin_tod_v1_qwen_test.jsonl) | pumpkin tod v1 qwen test 학습·검증·평가에 사용하는 JSON Lines 데이터입니다. | 2.4 MB |
| [`data/tod/qwen/pumpkin_tod_v1_qwen_train.jsonl`](data/tod/qwen/pumpkin_tod_v1_qwen_train.jsonl) | pumpkin tod v1 qwen train 학습·검증·평가에 사용하는 JSON Lines 데이터입니다. | 40.1 MB |
| [`data/tod/qwen/pumpkin_tod_v1_qwen_validation.jsonl`](data/tod/qwen/pumpkin_tod_v1_qwen_validation.jsonl) | pumpkin tod v1 qwen validation 학습·검증·평가에 사용하는 JSON Lines 데이터입니다. | 4.5 MB |

</details>

<details>
<summary><strong>docs/</strong> — 설계·정책·실행법·시연/디버깅 문서 (41개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`docs/★ order_interaction_flow.md`](docs/%E2%98%85%20order_interaction_flow.md) | ★ order interaction flow 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 18.8 KB |
| [`docs/★ service_scenario_catalog.md`](docs/%E2%98%85%20service_scenario_catalog.md) | ★ service scenario catalog 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 26.2 KB |
| [`docs/★ structure_b_final_dataset.md`](docs/%E2%98%85%20structure_b_final_dataset.md) | ★ structure b final dataset 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 12.9 KB |
| [`docs/2026-08-10_robot_interaction_troubleshooting_log.md`](docs/2026-08-10_robot_interaction_troubleshooting_log.md) | 2026 08 10 robot interaction troubleshooting log 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 20.7 KB |
| [`docs/2026-08-10_stt_respeaker_debug_log.md`](docs/2026-08-10_stt_respeaker_debug_log.md) | 2026 08 10 stt respeaker debug log 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 10.3 KB |
| [`docs/2026-09-05_qwen3_multiturn_repeat_issue.md`](docs/2026-09-05_qwen3_multiturn_repeat_issue.md) | 2026 09 05 qwen3 multiturn repeat issue 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 6.1 KB |
| [`docs/2026-09-05_qwen3_smalltalk_standalone_log.md`](docs/2026-09-05_qwen3_smalltalk_standalone_log.md) | 2026 09 05 qwen3 smalltalk standalone log 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 12.1 KB |
| [`docs/ARM_GESTURE_INTEGRATION.md`](docs/ARM_GESTURE_INTEGRATION.md) | ARM GESTURE INTEGRATION 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 3.6 KB |
| [`docs/cloud_run_relay.md`](docs/cloud_run_relay.md) | cloud run relay 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 3.4 KB |
| [`docs/current_order_flow_issues_and_action_plan.md`](docs/current_order_flow_issues_and_action_plan.md) | current order flow issues and action plan 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 29.0 KB |
| [`docs/data_collection_flow.md`](docs/data_collection_flow.md) | data collection flow 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 7.1 KB |
| [`docs/DEMO_TEST_SCENARIOS.md`](docs/DEMO_TEST_SCENARIOS.md) | DEMO TEST SCENARIOS 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 7.3 KB |
| [`docs/diagrams/01_service_system_architecture.drawio`](docs/diagrams/01_service_system_architecture.drawio) | 01 service system architecture 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 10.8 KB |
| [`docs/diagrams/02_ros2_node_topic_architecture.drawio`](docs/diagrams/02_ros2_node_topic_architecture.drawio) | 02 ros2 node topic architecture 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 23.7 KB |
| [`docs/diagrams/03_nlu_item_query_architecture.drawio`](docs/diagrams/03_nlu_item_query_architecture.drawio) | 03 nlu item query architecture 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 17.0 KB |
| [`docs/diagrams/09_2_entity_relationship_diagram.drawio`](docs/diagrams/09_2_entity_relationship_diagram.drawio) | 09 2 entity relationship diagram 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 9.3 KB |
| [`docs/diagrams/data_collection_processing_flow.drawio`](docs/diagrams/data_collection_processing_flow.drawio) | data collection processing flow 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 19.1 KB |
| [`docs/diagrams/pumpkin_network_architecture_simple.drawio`](docs/diagrams/pumpkin_network_architecture_simple.drawio) | pumpkin network architecture simple 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 10.3 KB |
| [`docs/face_enrollment_api.md`](docs/face_enrollment_api.md) | face enrollment api 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 2.6 KB |
| [`docs/firebase_auth_setup.md`](docs/firebase_auth_setup.md) | firebase auth setup 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 2.2 KB |
| [`docs/HAND_GESTURE_QUANTITY.md`](docs/HAND_GESTURE_QUANTITY.md) | HAND GESTURE QUANTITY 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 5.8 KB |
| [`docs/images/data_collection_simple_ppt.svg`](docs/images/data_collection_simple_ppt.svg) | data collection simple ppt 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 8.1 KB |
| [`docs/JETSON_ENVIRONMENT_STATUS.md`](docs/JETSON_ENVIRONMENT_STATUS.md) | JETSON ENVIRONMENT STATUS 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 7.9 KB |
| [`docs/jetson_expo_order_manual.md`](docs/jetson_expo_order_manual.md) | jetson expo order manual 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 13.5 KB |
| [`docs/jetson_realtime_face_recognition.md`](docs/jetson_realtime_face_recognition.md) | jetson realtime face recognition 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 2.7 KB |
| [`docs/macos_local_run.md`](docs/macos_local_run.md) | macos local run 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 3.6 KB |
| [`docs/menu_catalog_policy.md`](docs/menu_catalog_policy.md) | menu catalog policy 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 2.3 KB |
| [`docs/motor_controller.md`](docs/motor_controller.md) | motor controller 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 2.5 KB |
| [`docs/nlu_labeling_guidelines.md`](docs/nlu_labeling_guidelines.md) | nlu labeling guidelines 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 11.5 KB |
| [`docs/nlu_training_data_gap_guide.md`](docs/nlu_training_data_gap_guide.md) | nlu training data gap guide 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 15.4 KB |
| [`docs/order_dialogue_rules.md`](docs/order_dialogue_rules.md) | order dialogue rules 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 10.2 KB |
| [`docs/order_validation_rules.md`](docs/order_validation_rules.md) | order validation rules 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 6.9 KB |
| [`docs/preorder_face_pickup_contract.md`](docs/preorder_face_pickup_contract.md) | preorder face pickup contract 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 11.1 KB |
| [`docs/README.md`](docs/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 5.0 KB |
| [`docs/response_manager.md`](docs/response_manager.md) | response manager 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 4.9 KB |
| [`docs/scenario-flows/usecase-flows.md`](docs/scenario-flows/usecase-flows.md) | usecase flows 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 4.9 KB |
| [`docs/service_customer_and_display_policy.md`](docs/service_customer_and_display_policy.md) | service customer and display policy 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 13.4 KB |
| [`docs/single_menu_quantity_dataset_summary.md`](docs/single_menu_quantity_dataset_summary.md) | single menu quantity dataset summary 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 5.1 KB |
| [`docs/table_definition.md`](docs/table_definition.md) | table definition 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 8.6 KB |
| [`docs/unified_order_api.md`](docs/unified_order_api.md) | unified order api 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 2.8 KB |
| [`docs/web_team_setup.md`](docs/web_team_setup.md) | web team setup 프로젝트 설계·정책·실행·검증 문서/자료입니다. | 5.7 KB |

</details>

<details>
<summary><strong>experiments/</strong> — KIPS NLU 및 TOD SLM 실험 코드/결과 (101개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`experiments/nlu/kips_2026_item_query/__init__.py`](experiments/nlu/kips_2026_item_query/__init__.py) | Python 패키지 초기화 파일입니다. | 50 B |
| [`experiments/nlu/kips_2026_item_query/01_M0_independent_heads.ipynb`](experiments/nlu/kips_2026_item_query/01_M0_independent_heads.ipynb) | 01 M0 independent heads KIPS Item Query NLU 실험 재현 노트북입니다. | 5.0 KB |
| [`experiments/nlu/kips_2026_item_query/02_M1_item_query.ipynb`](experiments/nlu/kips_2026_item_query/02_M1_item_query.ipynb) | 02 M1 item query KIPS Item Query NLU 실험 재현 노트북입니다. | 4.9 KB |
| [`experiments/nlu/kips_2026_item_query/03_M2_improved_item_query.ipynb`](experiments/nlu/kips_2026_item_query/03_M2_improved_item_query.ipynb) | 03 M2 improved item query KIPS Item Query NLU 실험 재현 노트북입니다. | 5.0 KB |
| [`experiments/nlu/kips_2026_item_query/04_ablation.ipynb`](experiments/nlu/kips_2026_item_query/04_ablation.ipynb) | 04 ablation KIPS Item Query NLU 실험 재현 노트북입니다. | 7.2 KB |
| [`experiments/nlu/kips_2026_item_query/COLAB_RUN.md`](experiments/nlu/kips_2026_item_query/COLAB_RUN.md) | COLAB RUN KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 5.9 KB |
| [`experiments/nlu/kips_2026_item_query/config.py`](experiments/nlu/kips_2026_item_query/config.py) | config KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 1.8 KB |
| [`experiments/nlu/kips_2026_item_query/data_utils.py`](experiments/nlu/kips_2026_item_query/data_utils.py) | data utils KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 9.0 KB |
| [`experiments/nlu/kips_2026_item_query/kips_item_query_experiments_colab.ipynb`](experiments/nlu/kips_2026_item_query/kips_item_query_experiments_colab.ipynb) | kips item query experiments colab KIPS Item Query NLU 실험 재현 노트북입니다. | 5.4 KB |
| [`experiments/nlu/kips_2026_item_query/models.py`](experiments/nlu/kips_2026_item_query/models.py) | models KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 4.5 KB |
| [`experiments/nlu/kips_2026_item_query/README.md`](experiments/nlu/kips_2026_item_query/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 6.0 KB |
| [`experiments/nlu/kips_2026_item_query/requirements-colab.txt`](experiments/nlu/kips_2026_item_query/requirements-colab.txt) | requirements colab KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 85 B |
| [`experiments/nlu/kips_2026_item_query/results/ablation/ablation_runs_seed42.csv`](experiments/nlu/kips_2026_item_query/results/ablation/ablation_runs_seed42.csv) | ablation runs seed42 KIPS NLU 비교 실험 결과 산출물입니다. | 1.5 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/ablation_summary_seed42.csv`](experiments/nlu/kips_2026_item_query/results/ablation/ablation_summary_seed42.csv) | ablation summary seed42 KIPS NLU 비교 실험 결과 산출물입니다. | 1.3 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/experiment_manifest.json`](experiments/nlu/kips_2026_item_query/results/ablation/experiment_manifest.json) | experiment manifest KIPS NLU 비교 실험 결과 산출물입니다. | 1.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/history.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 2.7 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/result.json`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 788 B |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 207.3 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A1_plus_diff_lr_seed42/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 416.6 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/history.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 4.0 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/result.json`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 795 B |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 199.4 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/A2_plus_oversampling_seed42/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 415.0 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/history.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 3.4 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/result.json`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 787 B |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 224.8 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M1_item_query_seed42/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 413.2 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/history.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 2.4 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/result.json`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 792 B |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 196.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/ablation/runs/M2_improved_item_query_seed42/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 415.1 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/experiment_manifest.json`](experiments/nlu/kips_2026_item_query/results/M0/experiment_manifest.json) | experiment manifest KIPS NLU 비교 실험 결과 산출물입니다. | 1.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/M0_paper_table.csv`](experiments/nlu/kips_2026_item_query/results/M0/M0_paper_table.csv) | M0 paper table KIPS NLU 비교 실험 결과 산출물입니다. | 169 B |
| [`experiments/nlu/kips_2026_item_query/results/M0/M0_runs.csv`](experiments/nlu/kips_2026_item_query/results/M0/M0_runs.csv) | M0 runs KIPS NLU 비교 실험 결과 산출물입니다. | 1.2 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/M0_summary.csv`](experiments/nlu/kips_2026_item_query/results/M0/M0_summary.csv) | M0 summary KIPS NLU 비교 실험 결과 산출물입니다. | 905 B |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/history.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 4.8 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/result.json`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 797 B |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 239.5 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed42/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 407.5 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/history.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 5.0 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/result.json`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 789 B |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 227.4 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed43/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 406.1 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/history.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 4.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/result.json`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 789 B |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 236.0 KB |
| [`experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M0/runs/M0_independent_heads_seed44/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 407.2 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/experiment_manifest.json`](experiments/nlu/kips_2026_item_query/results/M1/experiment_manifest.json) | experiment manifest KIPS NLU 비교 실험 결과 산출물입니다. | 1.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/M1_paper_table.csv`](experiments/nlu/kips_2026_item_query/results/M1/M1_paper_table.csv) | M1 paper table KIPS NLU 비교 실험 결과 산출물입니다. | 164 B |
| [`experiments/nlu/kips_2026_item_query/results/M1/M1_runs.csv`](experiments/nlu/kips_2026_item_query/results/M1/M1_runs.csv) | M1 runs KIPS NLU 비교 실험 결과 산출물입니다. | 1.2 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/M1_summary.csv`](experiments/nlu/kips_2026_item_query/results/M1/M1_summary.csv) | M1 summary KIPS NLU 비교 실험 결과 산출물입니다. | 920 B |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/history.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 3.4 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/result.json`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 787 B |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 224.8 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed42/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 413.2 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/history.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 4.1 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/result.json`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 785 B |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 203.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed43/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 403.1 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/history.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 3.7 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/result.json`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 776 B |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 211.8 KB |
| [`experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M1/runs/M1_item_query_seed44/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 415.4 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/experiment_manifest.json`](experiments/nlu/kips_2026_item_query/results/M2/experiment_manifest.json) | experiment manifest KIPS NLU 비교 실험 결과 산출물입니다. | 1.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/M2_paper_table.csv`](experiments/nlu/kips_2026_item_query/results/M2/M2_paper_table.csv) | M2 paper table KIPS NLU 비교 실험 결과 산출물입니다. | 173 B |
| [`experiments/nlu/kips_2026_item_query/results/M2/M2_runs.csv`](experiments/nlu/kips_2026_item_query/results/M2/M2_runs.csv) | M2 runs KIPS NLU 비교 실험 결과 산출물입니다. | 1.3 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/M2_summary.csv`](experiments/nlu/kips_2026_item_query/results/M2/M2_summary.csv) | M2 summary KIPS NLU 비교 실험 결과 산출물입니다. | 915 B |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/history.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 2.4 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/result.json`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 792 B |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 196.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed42/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 415.1 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/history.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 3.6 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/result.json`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 813 B |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 193.6 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed43/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 408.9 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/history.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/history.csv) | history KIPS NLU 비교 실험 결과 산출물입니다. | 3.1 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/result.json`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/result.json) | result KIPS NLU 비교 실험 결과 산출물입니다. | 812 B |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/test_errors.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/test_errors.csv) | test errors KIPS NLU 비교 실험 결과 산출물입니다. | 209.8 KB |
| [`experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/test_predictions.csv`](experiments/nlu/kips_2026_item_query/results/M2/runs/M2_improved_item_query_seed44/test_predictions.csv) | test predictions KIPS NLU 비교 실험 결과 산출물입니다. | 415.2 KB |
| [`experiments/nlu/kips_2026_item_query/run_all.py`](experiments/nlu/kips_2026_item_query/run_all.py) | run all KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 7.1 KB |
| [`experiments/nlu/kips_2026_item_query/TEAM_SPLIT.md`](experiments/nlu/kips_2026_item_query/TEAM_SPLIT.md) | TEAM SPLIT KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 2.4 KB |
| [`experiments/nlu/kips_2026_item_query/train_eval.py`](experiments/nlu/kips_2026_item_query/train_eval.py) | train eval KIPS Item Query NLU 비교 실험 구성/재현 파일입니다. | 16.9 KB |
| [`experiments/nlu/README.md`](experiments/nlu/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 997 B |
| [`experiments/tod_slm/data_generation/build_multiturn_scenarios.py`](experiments/tod_slm/data_generation/build_multiturn_scenarios.py) | build multiturn scenarios TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 36.2 KB |
| [`experiments/tod_slm/data_generation/build_review_samples.py`](experiments/tod_slm/data_generation/build_review_samples.py) | build review samples TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 9.4 KB |
| [`experiments/tod_slm/data_generation/generate_rule_labels.py`](experiments/tod_slm/data_generation/generate_rule_labels.py) | generate rule labels TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 28.4 KB |
| [`experiments/tod_slm/data_generation/prepare_qwen_sft.py`](experiments/tod_slm/data_generation/prepare_qwen_sft.py) | prepare qwen sft TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 18.9 KB |
| [`experiments/tod_slm/data_generation/QWEN_SFT_PREP.md`](experiments/tod_slm/data_generation/QWEN_SFT_PREP.md) | QWEN SFT PREP TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 7.5 KB |
| [`experiments/tod_slm/data_generation/README.md`](experiments/tod_slm/data_generation/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 9.4 KB |
| [`experiments/tod_slm/review/app.py`](experiments/tod_slm/review/app.py) | app TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 13.3 KB |
| [`experiments/tod_slm/review/index.html`](experiments/tod_slm/review/index.html) | index TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 21.8 KB |
| [`experiments/tod_slm/review/README.md`](experiments/tod_slm/review/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 3.9 KB |
| [`experiments/tod_slm/training/analyze_test_errors.py`](experiments/tod_slm/training/analyze_test_errors.py) | TOD SLM의 고정 test set 예측 오류를 분석하는 실험 분석 도구이며 unit test 파일이 아닙니다. | 15.9 KB |
| [`experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml`](experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml) | qwen3 0.6b lora v1 TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 1.5 KB |
| [`experiments/tod_slm/training/evaluate.py`](experiments/tod_slm/training/evaluate.py) | evaluate TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 13.6 KB |
| [`experiments/tod_slm/training/inspect_token_lengths.py`](experiments/tod_slm/training/inspect_token_lengths.py) | inspect token lengths TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 6.0 KB |
| [`experiments/tod_slm/training/merge_lora.py`](experiments/tod_slm/training/merge_lora.py) | merge lora TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 2.4 KB |
| [`experiments/tod_slm/training/README.md`](experiments/tod_slm/training/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 9.3 KB |
| [`experiments/tod_slm/training/requirements.txt`](experiments/tod_slm/training/requirements.txt) | requirements TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 295 B |
| [`experiments/tod_slm/training/STUDENT_V1_RESULTS_AND_V2_PLAN.md`](experiments/tod_slm/training/STUDENT_V1_RESULTS_AND_V2_PLAN.md) | STUDENT V1 RESULTS AND V2 PLAN TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 6.5 KB |
| [`experiments/tod_slm/training/train_lora.py`](experiments/tod_slm/training/train_lora.py) | train lora TOD SLM 데이터 생성·학습·평가·분석 파일입니다. | 14.0 KB |

</details>

<details>
<summary><strong>face_backend/</strong> — 얼굴 임베딩 Cloud Run 백엔드 (6개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`face_backend/cloudbuild.yaml`](face_backend/cloudbuild.yaml) | cloudbuild 얼굴 임베딩 Cloud Run 백엔드 파일입니다. | 233 B |
| [`face_backend/deploy.ps1`](face_backend/deploy.ps1) | deploy 얼굴 임베딩 Cloud Run 백엔드 파일입니다. | 5.0 KB |
| [`face_backend/Dockerfile`](face_backend/Dockerfile) | Dockerfile 얼굴 임베딩 Cloud Run 백엔드 파일입니다. | 1.1 KB |
| [`face_backend/main.py`](face_backend/main.py) | main 얼굴 임베딩 Cloud Run 백엔드 파일입니다. | 8.9 KB |
| [`face_backend/README.md`](face_backend/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 2.0 KB |
| [`face_backend/requirements.txt`](face_backend/requirements.txt) | requirements 얼굴 임베딩 Cloud Run 백엔드 파일입니다. | 211 B |

</details>

<details>
<summary><strong>hardware/</strong> — 부품·전원·배선·제작 자료 (29개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`hardware/components.yaml`](hardware/components.yaml) | components 하드웨어 부품·전원·배선·제작 자료입니다. | 21.8 KB |
| [`hardware/components/ATO_ATC_FUSE_BLOCK_6WAY.md`](hardware/components/ATO_ATC_FUSE_BLOCK_6WAY.md) | ATO ATC FUSE BLOCK 6WAY 하드웨어 부품·전원·배선·제작 자료입니다. | 7.2 KB |
| [`hardware/components/ESP32_LCD.md`](hardware/components/ESP32_LCD.md) | ESP32 LCD 하드웨어 부품·전원·배선·제작 자료입니다. | 9.6 KB |
| [`hardware/components/INALWAYS_0717-2SCQ.md`](hardware/components/INALWAYS_0717-2SCQ.md) | INALWAYS 0717 2SCQ 하드웨어 부품·전원·배선·제작 자료입니다. | 6.5 KB |
| [`hardware/components/MAIN_DISPLAY_5INCH.md`](hardware/components/MAIN_DISPLAY_5INCH.md) | MAIN DISPLAY 5INCH 하드웨어 부품·전원·배선·제작 자료입니다. | 3.4 KB |
| [`hardware/components/MEAN_WELL_LRS-150F-5.md`](hardware/components/MEAN_WELL_LRS-150F-5.md) | MEAN WELL LRS 150F 5 하드웨어 부품·전원·배선·제작 자료입니다. | 8.5 KB |
| [`hardware/components/MG90S.md`](hardware/components/MG90S.md) | MG90S 하드웨어 부품·전원·배선·제작 자료입니다. | 3.1 KB |
| [`hardware/components/README.md`](hardware/components/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 3.8 KB |
| [`hardware/components/SMG_TYE-TB003.md`](hardware/components/SMG_TYE-TB003.md) | SMG TYE TB003 하드웨어 부품·전원·배선·제작 자료입니다. | 9.4 KB |
| [`hardware/components/USB_CAMERA.md`](hardware/components/USB_CAMERA.md) | USB CAMERA 하드웨어 부품·전원·배선·제작 자료입니다. | 1.6 KB |
| [`hardware/CONTRIBUTING.md`](hardware/CONTRIBUTING.md) | CONTRIBUTING 하드웨어 부품·전원·배선·제작 자료입니다. | 6.4 KB |
| [`hardware/diagrams/01_power_architecture.drawio`](hardware/diagrams/01_power_architecture.drawio) | 01 power architecture 하드웨어 부품·전원·배선·제작 자료입니다. | 10.6 KB |
| [`hardware/diagrams/02_servo_power_distribution.drawio`](hardware/diagrams/02_servo_power_distribution.drawio) | 02 servo power distribution 하드웨어 부품·전원·배선·제작 자료입니다. | 9.2 KB |
| [`hardware/diagrams/03_control_wiring.drawio`](hardware/diagrams/03_control_wiring.drawio) | 03 control wiring 하드웨어 부품·전원·배선·제작 자료입니다. | 7.9 KB |
| [`hardware/diagrams/06_3_SENSOR_ACTUATOR_CONFIGURATION.drawio`](hardware/diagrams/06_3_SENSOR_ACTUATOR_CONFIGURATION.drawio) | 06 3 SENSOR ACTUATOR CONFIGURATION 하드웨어 부품·전원·배선·제작 자료입니다. | 10.1 KB |
| [`hardware/JETSON_ESP32_LCD_SETUP.md`](hardware/JETSON_ESP32_LCD_SETUP.md) | JETSON ESP32 LCD SETUP 하드웨어 부품·전원·배선·제작 자료입니다. | 7.2 KB |
| [`hardware/LRS-150F-5_CONNECTION_GUIDE.md`](hardware/LRS-150F-5_CONNECTION_GUIDE.md) | LRS 150F 5 CONNECTION GUIDE 하드웨어 부품·전원·배선·제작 자료입니다. | 15.4 KB |
| [`hardware/LRS-150F-5_CONNECTION_PLAN_FROM_CHAT.md`](hardware/LRS-150F-5_CONNECTION_PLAN_FROM_CHAT.md) | LRS 150F 5 CONNECTION PLAN FROM CHAT 하드웨어 부품·전원·배선·제작 자료입니다. | 11.0 KB |
| [`hardware/MOTORS.md`](hardware/MOTORS.md) | MOTORS 하드웨어 부품·전원·배선·제작 자료입니다. | 10.8 KB |
| [`hardware/PARTS.md`](hardware/PARTS.md) | PARTS 하드웨어 부품·전원·배선·제작 자료입니다. | 11.8 KB |
| [`hardware/power-budget.md`](hardware/power-budget.md) | power budget 하드웨어 부품·전원·배선·제작 자료입니다. | 8.8 KB |
| [`hardware/README.md`](hardware/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 11.0 KB |
| [`hardware/robot_arm/ARM_MOTIONS.md`](hardware/robot_arm/ARM_MOTIONS.md) | ARM MOTIONS 하드웨어 부품·전원·배선·제작 자료입니다. | 4.6 KB |
| [`hardware/robot_arm/README.md`](hardware/robot_arm/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 11.3 KB |
| [`hardware/SERVO_POWER_ON_OFF_MANUAL.md`](hardware/SERVO_POWER_ON_OFF_MANUAL.md) | SERVO POWER ON OFF MANUAL 하드웨어 부품·전원·배선·제작 자료입니다. | 11.0 KB |
| [`hardware/SERVO_POWER_WAGO_MAP.md`](hardware/SERVO_POWER_WAGO_MAP.md) | SERVO POWER WAGO MAP 하드웨어 부품·전원·배선·제작 자료입니다. | 8.0 KB |
| [`hardware/TERMINAL_PURCHASE_GUIDE.md`](hardware/TERMINAL_PURCHASE_GUIDE.md) | TERMINAL PURCHASE GUIDE 하드웨어 부품·전원·배선·제작 자료입니다. | 5.0 KB |
| [`hardware/TODO.md`](hardware/TODO.md) | TODO 하드웨어 부품·전원·배선·제작 자료입니다. | 7.6 KB |
| [`hardware/wiring.md`](hardware/wiring.md) | wiring 하드웨어 부품·전원·배선·제작 자료입니다. | 10.1 KB |

</details>

<details>
<summary><strong>nlu/</strong> — 현재 서비스용 NLU 추론 모듈 (8개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`nlu/__init__.py`](nlu/__init__.py) | Python 패키지 초기화 파일입니다. | 223 B |
| [`nlu/cli.py`](nlu/cli.py) | cli 현재 서비스용 NLU 추론 모듈/설정입니다. | 1.2 KB |
| [`nlu/config.py`](nlu/config.py) | production NLU의 기본 koELECTRA-small encoder, 모델 경로, device, threshold를 정의합니다. | 1004 B |
| [`nlu/model.py`](nlu/model.py) | koELECTRA Encoder와 2-layer Item Query Transformer Decoder 구조를 정의합니다. | 4.8 KB |
| [`nlu/predictor.py`](nlu/predictor.py) | NLU 모델 로딩과 실제 구조화 추론을 수행합니다. | 9.1 KB |
| [`nlu/README.md`](nlu/README.md) | 현재 production NLU 구조·데이터·실험·실행 방법을 설명합니다. | 8.9 KB |
| [`nlu/requirements-jetson-inference.txt`](nlu/requirements-jetson-inference.txt) | requirements jetson inference 현재 서비스용 NLU 추론 모듈/설정입니다. | 187 B |
| [`nlu/schema.py`](nlu/schema.py) | schema 현재 서비스용 NLU 추론 모듈/설정입니다. | 704 B |

</details>

<details>
<summary><strong>robot_face/</strong> — ESP32 LCD 표정 및 Jetson 얼굴 제어 (5개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`robot_face/esp32_lcd/esp32_lcd_face.ino`](robot_face/esp32_lcd/esp32_lcd_face.ino) | esp32 lcd face LCD 얼굴 표현과 Jetson-ESP32 제어 파일입니다. | 5.7 KB |
| [`robot_face/jetson/__init__.py`](robot_face/jetson/__init__.py) | Python 패키지 초기화 파일입니다. | 194 B |
| [`robot_face/jetson/face_controller.py`](robot_face/jetson/face_controller.py) | face controller LCD 얼굴 표현과 Jetson-ESP32 제어 파일입니다. | 11.8 KB |
| [`robot_face/jetson/README.md`](robot_face/jetson/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 5.7 KB |
| [`robot_face/jetson/requirements.txt`](robot_face/jetson/requirements.txt) | requirements LCD 얼굴 표현과 Jetson-ESP32 제어 파일입니다. | 17 B |

</details>

<details>
<summary><strong>ros2_ws/</strong> — ROS2 실물 로봇 통합 runtime (52개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`ros2_ws/src/robot_controller/gesture_data/raw/head_gesture_samples_p01_20260715_105828.csv`](ros2_ws/src/robot_controller/gesture_data/raw/head_gesture_samples_p01_20260715_105828.csv) | head gesture samples p01 20260715 105828 표 형식 데이터/결과 파일입니다. | 2.5 MB |
| [`ros2_ws/src/robot_controller/gesture_data/raw/head_gesture_samples_p02_20260715_110637.csv`](ros2_ws/src/robot_controller/gesture_data/raw/head_gesture_samples_p02_20260715_110637.csv) | head gesture samples p02 20260715 110637 표 형식 데이터/결과 파일입니다. | 877.5 KB |
| [`ros2_ws/src/robot_controller/gesture_data/raw/head_gesture_samples_p03_20260715_111935.csv`](ros2_ws/src/robot_controller/gesture_data/raw/head_gesture_samples_p03_20260715_111935.csv) | head gesture samples p03 20260715 111935 표 형식 데이터/결과 파일입니다. | 1.2 MB |
| [`ros2_ws/src/robot_controller/package.xml`](ros2_ws/src/robot_controller/package.xml) | package 패키지 빌드·설치·메타데이터 설정 파일입니다. | 673 B |
| [`ros2_ws/src/robot_controller/README.md`](ros2_ws/src/robot_controller/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 17.0 KB |
| [`ros2_ws/src/robot_controller/requirements-head-gesture.txt`](ros2_ws/src/robot_controller/requirements-head-gesture.txt) | requirements head gesture 프로젝트 소스·설정·데이터 파일입니다. | 62 B |
| [`ros2_ws/src/robot_controller/resource/robot_controller`](ros2_ws/src/robot_controller/resource/robot_controller) | robot controller 프로젝트 소스·설정·데이터 파일입니다. | 0 B |
| [`ros2_ws/src/robot_controller/robot_controller/__init__.py`](ros2_ws/src/robot_controller/robot_controller/__init__.py) | Python 패키지 초기화 파일입니다. | 0 B |
| [`ros2_ws/src/robot_controller/robot_controller/action_node_order_handoff.py`](ros2_ws/src/robot_controller/robot_controller/action_node_order_handoff.py) | action node order handoff 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 9.8 KB |
| [`ros2_ws/src/robot_controller/robot_controller/action_node.py`](ros2_ws/src/robot_controller/robot_controller/action_node.py) | Decision 결과를 TTS·LCD·고개·팔 행동으로 변환하는 ROS2 Action 노드입니다. | 15.2 KB |
| [`ros2_ws/src/robot_controller/robot_controller/arm_motion.py`](ros2_ws/src/robot_controller/robot_controller/arm_motion.py) | arm motion 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 4.7 KB |
| [`ros2_ws/src/robot_controller/robot_controller/controller_node.py`](ros2_ws/src/robot_controller/robot_controller/controller_node.py) | controller node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 641 B |
| [`ros2_ws/src/robot_controller/robot_controller/decision_node_additional_order.py`](ros2_ws/src/robot_controller/robot_controller/decision_node_additional_order.py) | decision node additional order 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 17.5 KB |
| [`ros2_ws/src/robot_controller/robot_controller/decision_node_hand_quantity.py`](ros2_ws/src/robot_controller/robot_controller/decision_node_hand_quantity.py) | 사람 존재·wake phrase·손가락 수량 입력을 처리하는 production Decision 노드입니다. | 11.6 KB |
| [`ros2_ws/src/robot_controller/robot_controller/decision_node_order_handoff.py`](ros2_ws/src/robot_controller/robot_controller/decision_node_order_handoff.py) | decision node order handoff 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 21.6 KB |
| [`ros2_ws/src/robot_controller/robot_controller/decision_node.py`](ros2_ws/src/robot_controller/robot_controller/decision_node.py) | decision node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 35.1 KB |
| [`ros2_ws/src/robot_controller/robot_controller/dialogue_act_resolver.py`](ros2_ws/src/robot_controller/robot_controller/dialogue_act_resolver.py) | dialogue act resolver 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 9.9 KB |
| [`ros2_ws/src/robot_controller/robot_controller/dialogue_slots.py`](ros2_ws/src/robot_controller/robot_controller/dialogue_slots.py) | dialogue slots 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 17.9 KB |
| [`ros2_ws/src/robot_controller/robot_controller/face_controller_node.py`](ros2_ws/src/robot_controller/robot_controller/face_controller_node.py) | face controller node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 2.3 KB |
| [`ros2_ws/src/robot_controller/robot_controller/face_display_node.py`](ros2_ws/src/robot_controller/robot_controller/face_display_node.py) | face display node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 7.5 KB |
| [`ros2_ws/src/robot_controller/robot_controller/face_identity.py`](ros2_ws/src/robot_controller/robot_controller/face_identity.py) | face identity 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 3.1 KB |
| [`ros2_ws/src/robot_controller/robot_controller/face_personalization_node.py`](ros2_ws/src/robot_controller/robot_controller/face_personalization_node.py) | face personalization node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 5.8 KB |
| [`ros2_ws/src/robot_controller/robot_controller/hand_quantity_gesture.py`](ros2_ws/src/robot_controller/robot_controller/hand_quantity_gesture.py) | hand quantity gesture 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 7.4 KB |
| [`ros2_ws/src/robot_controller/robot_controller/head_gesture_frame_estimator.py`](ros2_ws/src/robot_controller/robot_controller/head_gesture_frame_estimator.py) | head gesture frame estimator 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 8.4 KB |
| [`ros2_ws/src/robot_controller/robot_controller/head_gesture_recognizer.py`](ros2_ws/src/robot_controller/robot_controller/head_gesture_recognizer.py) | head gesture recognizer 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 14.0 KB |
| [`ros2_ws/src/robot_controller/robot_controller/head_motion_node.py`](ros2_ws/src/robot_controller/robot_controller/head_motion_node.py) | head motion node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 3.5 KB |
| [`ros2_ws/src/robot_controller/robot_controller/menu_policy.py`](ros2_ws/src/robot_controller/robot_controller/menu_policy.py) | menu policy 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 5.7 KB |
| [`ros2_ws/src/robot_controller/robot_controller/motor_controller_node.py`](ros2_ws/src/robot_controller/robot_controller/motor_controller_node.py) | motor controller node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 12.8 KB |
| [`ros2_ws/src/robot_controller/robot_controller/motor_driver.py`](ros2_ws/src/robot_controller/robot_controller/motor_driver.py) | motor driver 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 4.7 KB |
| [`ros2_ws/src/robot_controller/robot_controller/multi_item_span_grounding.py`](ros2_ws/src/robot_controller/robot_controller/multi_item_span_grounding.py) | multi item span grounding 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 6.2 KB |
| [`ros2_ws/src/robot_controller/robot_controller/nlu_node.py`](ros2_ws/src/robot_controller/robot_controller/nlu_node.py) | nlu node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 10.8 KB |
| [`ros2_ws/src/robot_controller/robot_controller/nlu_postprocess.py`](ros2_ws/src/robot_controller/robot_controller/nlu_postprocess.py) | nlu postprocess 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 17.4 KB |
| [`ros2_ws/src/robot_controller/robot_controller/order_api_client.py`](ros2_ws/src/robot_controller/robot_controller/order_api_client.py) | order api client 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 3.3 KB |
| [`ros2_ws/src/robot_controller/robot_controller/order_dialogue_manager.py`](ros2_ws/src/robot_controller/robot_controller/order_dialogue_manager.py) | order dialogue manager 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 10.5 KB |
| [`ros2_ws/src/robot_controller/robot_controller/order_exception_policy.py`](ros2_ws/src/robot_controller/robot_controller/order_exception_policy.py) | order exception policy 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 9.0 KB |
| [`ros2_ws/src/robot_controller/robot_controller/order_schema.py`](ros2_ws/src/robot_controller/robot_controller/order_schema.py) | order schema 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 4.7 KB |
| [`ros2_ws/src/robot_controller/robot_controller/order_submission_node.py`](ros2_ws/src/robot_controller/robot_controller/order_submission_node.py) | order submission node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 8.1 KB |
| [`ros2_ws/src/robot_controller/robot_controller/preorder.py`](ros2_ws/src/robot_controller/robot_controller/preorder.py) | preorder 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 3.9 KB |
| [`ros2_ws/src/robot_controller/robot_controller/realtime_face_recognition.py`](ros2_ws/src/robot_controller/robot_controller/realtime_face_recognition.py) | 등록 얼굴 임베딩과 실시간 얼굴을 비교해 고객을 식별합니다. | 8.2 KB |
| [`ros2_ws/src/robot_controller/robot_controller/response_manager_node.py`](ros2_ws/src/robot_controller/robot_controller/response_manager_node.py) | response manager node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 2.9 KB |
| [`ros2_ws/src/robot_controller/robot_controller/response_manager_order_exception.py`](ros2_ws/src/robot_controller/robot_controller/response_manager_order_exception.py) | response manager order exception 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 1.5 KB |
| [`ros2_ws/src/robot_controller/robot_controller/response_manager_pickup.py`](ros2_ws/src/robot_controller/robot_controller/response_manager_pickup.py) | response manager pickup 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 10.4 KB |
| [`ros2_ws/src/robot_controller/robot_controller/response_manager.py`](ros2_ws/src/robot_controller/robot_controller/response_manager.py) | response manager 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 20.6 KB |
| [`ros2_ws/src/robot_controller/robot_controller/response_payload_builder.py`](ros2_ws/src/robot_controller/robot_controller/response_payload_builder.py) | response payload builder 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 1.9 KB |
| [`ros2_ws/src/robot_controller/robot_controller/stt_node_safe.py`](ros2_ws/src/robot_controller/robot_controller/stt_node_safe.py) | stt node safe 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 20.5 KB |
| [`ros2_ws/src/robot_controller/robot_controller/stt_node_unbiased.py`](ros2_ws/src/robot_controller/robot_controller/stt_node_unbiased.py) | Faster-Whisper와 VAD 기반 production STT 노드입니다. | 4.3 KB |
| [`ros2_ws/src/robot_controller/robot_controller/stt_node.py`](ros2_ws/src/robot_controller/robot_controller/stt_node.py) | stt node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 26.9 KB |
| [`ros2_ws/src/robot_controller/robot_controller/tts_node.py`](ros2_ws/src/robot_controller/robot_controller/tts_node.py) | tts node 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 15.1 KB |
| [`ros2_ws/src/robot_controller/robot_controller/vision_node_hand_quantity.py`](ros2_ws/src/robot_controller/robot_controller/vision_node_hand_quantity.py) | vision node hand quantity 실물 로봇 인식·판단·행동 pipeline의 ROS2 Python 모듈입니다. | 22.8 KB |
| [`ros2_ws/src/robot_controller/robot_controller/vision_node.py`](ros2_ws/src/robot_controller/robot_controller/vision_node.py) | 카메라에서 사람·얼굴·고개·손 제스처 정보를 처리하는 ROS2 Vision 노드입니다. | 23.7 KB |
| [`ros2_ws/src/robot_controller/setup.cfg`](ros2_ws/src/robot_controller/setup.cfg) | setup 패키지 빌드·설치·메타데이터 설정 파일입니다. | 101 B |
| [`ros2_ws/src/robot_controller/setup.py`](ros2_ws/src/robot_controller/setup.py) | setup 패키지 빌드·설치·메타데이터 설정 파일입니다. | 2.0 KB |

</details>

<details>
<summary><strong>scripts/</strong> — 실행·시연·데이터 생성·하드웨어 보조 스크립트 (40개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`scripts/apply_firebase_identity_patch.py`](scripts/apply_firebase_identity_patch.py) | apply firebase identity patch 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 3.4 KB |
| [`scripts/check_jetson_nlu.sh`](scripts/check_jetson_nlu.sh) | check jetson nlu 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 1.5 KB |
| [`scripts/deploy-firestore-rules.ps1`](scripts/deploy-firestore-rules.ps1) | deploy firestore rules 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 2.8 KB |
| [`scripts/eval_tod_qwen.sh`](scripts/eval_tod_qwen.sh) | eval tod qwen 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 610 B |
| [`scripts/generate_single_menu_quantity_dataset.py`](scripts/generate_single_menu_quantity_dataset.py) | generate single menu quantity dataset 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 11.7 KB |
| [`scripts/generate_structure_b_followup_responses.py`](scripts/generate_structure_b_followup_responses.py) | generate structure b followup responses 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 13.9 KB |
| [`scripts/merge_and_augment_structure_b.py`](scripts/merge_and_augment_structure_b.py) | merge and augment structure b 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 8.2 KB |
| [`scripts/merge_tod_qwen_lora.sh`](scripts/merge_tod_qwen_lora.sh) | merge tod qwen lora 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 304 B |
| [`scripts/pca9685/arm_pose_demo.py`](scripts/pca9685/arm_pose_demo.py) | arm pose demo 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 4.8 KB |
| [`scripts/pca9685/servo_power_sequence.py`](scripts/pca9685/servo_power_sequence.py) | servo power sequence 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 7.6 KB |
| [`scripts/README.md`](scripts/README.md) | 해당 폴더의 역할, 구조와 사용 방법을 설명합니다. | 5.7 KB |
| [`scripts/resolve_camera_device.py`](scripts/resolve_camera_device.py) | resolve camera device 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 5.7 KB |
| [`scripts/robot_interaction_debug_terminal.py`](scripts/robot_interaction_debug_terminal.py) | robot interaction debug terminal 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 10.3 KB |
| [`scripts/robot_interaction_simple_terminal.py`](scripts/robot_interaction_simple_terminal.py) | robot interaction simple terminal 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 11.5 KB |
| [`scripts/robot_interaction_terminal.py`](scripts/robot_interaction_terminal.py) | robot interaction terminal 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 18.2 KB |
| [`scripts/run_customer_mobile.ps1`](scripts/run_customer_mobile.ps1) | run customer mobile 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 3.7 KB |
| [`scripts/run_demo_web.sh`](scripts/run_demo_web.sh) | run demo web 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 2.1 KB |
| [`scripts/run_jetson_missing_slot_test.sh`](scripts/run_jetson_missing_slot_test.sh) | run jetson missing slot test 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 2.7 KB |
| [`scripts/run_jetson_nlu_missing_slot_test.sh`](scripts/run_jetson_nlu_missing_slot_test.sh) | run jetson nlu missing slot test 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 3.8 KB |
| [`scripts/run_nlu_node_cuda.sh`](scripts/run_nlu_node_cuda.sh) | run nlu node cuda 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 1.1 KB |
| [`scripts/run_robot_debug.sh`](scripts/run_robot_debug.sh) | run robot debug 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 2.0 KB |
| [`scripts/run_robot_interaction_demo.sh`](scripts/run_robot_interaction_demo.sh) | run robot interaction demo 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 11.1 KB |
| [`scripts/run_robot_interaction_logs.sh`](scripts/run_robot_interaction_logs.sh) | run robot interaction logs 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 1.5 KB |
| [`scripts/run_robot_interaction_test.sh`](scripts/run_robot_interaction_test.sh) | run robot interaction test 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 4.8 KB |
| [`scripts/run_robot_interaction_view.sh`](scripts/run_robot_interaction_view.sh) | run robot interaction view 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 689 B |
| [`scripts/run_robot_with_monitor.sh`](scripts/run_robot_with_monitor.sh) | 5인치 고객 화면과 전체 ROS2 robot pipeline을 시작하는 최종 시연 런처입니다. | 7.7 KB |
| [`scripts/run_ros_voice_nodes_macos.sh`](scripts/run_ros_voice_nodes_macos.sh) | run ros voice nodes macos 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 5.5 KB |
| [`scripts/run_ros_voice_nodes_pc.sh`](scripts/run_ros_voice_nodes_pc.sh) | run ros voice nodes pc 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 6.8 KB |
| [`scripts/run_ros_voice_nodes.sh`](scripts/run_ros_voice_nodes.sh) | run ros voice nodes 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 17.0 KB |
| [`scripts/run_tod_review_web.sh`](scripts/run_tod_review_web.sh) | run tod review web 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 170 B |
| [`scripts/run_web_api.sh`](scripts/run_web_api.sh) | run web api 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 485 B |
| [`scripts/servo_power_off.sh`](scripts/servo_power_off.sh) | servo power off 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 322 B |
| [`scripts/servo_power_on.sh`](scripts/servo_power_on.sh) | servo power on 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 321 B |
| [`scripts/stop_robot_interaction_nodes.sh`](scripts/stop_robot_interaction_nodes.sh) | stop robot interaction nodes 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 1.5 KB |
| [`scripts/terminal_chat.py`](scripts/terminal_chat.py) | terminal chat 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 10.5 KB |
| [`scripts/test_hand_quantity.sh`](scripts/test_hand_quantity.sh) | test hand quantity 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 763 B |
| [`scripts/test_robot_controller.sh`](scripts/test_robot_controller.sh) | test robot controller 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 1.7 KB |
| [`scripts/train_tod_qwen_lora.sh`](scripts/train_tod_qwen_lora.sh) | train tod qwen lora 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 1.1 KB |
| [`scripts/voice_terminal_chat.py`](scripts/voice_terminal_chat.py) | voice terminal chat 실행·데이터 처리·하드웨어 점검을 지원하는 스크립트입니다. | 11.7 KB |

</details>

<details>
<summary><strong>tools/</strong> — 개발 보조 도구 (1개)</summary>

| 파일 | 역할 | 크기 |
|---|---|---:|
| [`tools/stt-button/server.py`](tools/stt-button/server.py) | server 기능을 구현하는 Python 소스입니다. | 9.7 KB |

</details>


