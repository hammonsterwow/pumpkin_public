# Pumpkin NLU

Pumpkin 로봇의 ROS2 대화 파이프라인에서 사용하는 한국어 주문 NLU 패키지입니다.

현재 운영 모델은 **`structure_b_item_query_decoder`** 하나이며 다음 노트북으로 학습합니다.

```text
notebooks/koelectra_structure_b_item_query_decoder.ipynb
```

NLU 모델은 ROS2의 `nlu_node`에서 한 번만 로딩합니다. 관리자 웹과 FastAPI는 모델을 직접 불러오지 않고 ROS Topic에서 발생한 NLU·판단·행동 결과를 표시합니다.

## 전체 실행 흐름

```text
사용자 음성
→ stt_node
→ /voice_text
→ nlu_node
→ /intent_result
→ decision_node
→ /decision_result
→ action_node
→ /robot_action
→ TTS · LCD · 고개 · 팔 동작
```

관리자 웹은 `api/ros_bridge.py`를 통해 다음 Topic을 관찰합니다.

```text
/stt/status
/voice_text
/intent_result
/decision_result
/robot_action
/fsm/state
/face/recognition
```

웹의 텍스트 테스트 기능은 브라우저에서 별도 NLU를 수행하지 않습니다. 입력 문장을 `/voice_text`에 발행하여 실제 `nlu_node → decision_node → action_node` 흐름을 그대로 실행합니다.

## 폴더 구성

```text
nlu/
├── README.md
├── __init__.py
├── config.py
├── model.py
├── predictor.py
├── schema.py
├── cli.py
├── requirements-jetson-inference.txt
└── saved_models/
    └── structure_b_item_query_decoder/
        ├── best_model.pt
        ├── tokenizer/
        └── encoder_config/       # 선택 사항
```

| 파일 | 역할 |
|---|---|
| `config.py` | 모델명, 저장 경로, device, confidence threshold 설정 |
| `model.py` | koELECTRA와 Item Query Decoder 신경망 구조 |
| `predictor.py` | 모델 로딩, 추론, 라벨 디코딩, confidence 및 누락 슬롯 계산 |
| `schema.py` | NLU 최종 출력 타입 정의 |
| `cli.py` | ROS 없이 모델 자체를 점검하는 명령줄 도구 |
| `saved_models/` | Jetson에서 사용하는 모델 가중치와 tokenizer |

사용자에게 말할 문장, FSM 상태 전환, TTS 및 로봇 동작은 `nlu/`에 구현하지 않습니다.

## 모델 구조

```text
사용자 문장
    ↓
koELECTRA-base Encoder
    ├── [CLS] → Intent Head
    ├── [CLS] → Order Status Head
    └── Token Memory
             ↑
     3개의 Learned Item Query
             ↓
     Transformer Decoder 2 layers
             ├── Item Active Head
             ├── Menu Head
             ├── Temperature Head
             └── Quantity Head
```

- Encoder: `monologg/koelectra-base-v3-discriminator`
- 최대 입력 길이: 96 tokens
- 최대 주문 항목: 3개
- 기본 confidence threshold: `0.5`
- 학습 최적 모델 선택 기준: validation `frame_accuracy`

각 Item Query는 하나의 주문 항목을 담당합니다. 따라서 다음과 같은 복합 주문을 메뉴별로 분리할 수 있습니다.

```text
아이스 아메리카노 두 잔하고 따뜻한 카페라떼 한 잔 주세요.
```

```text
Item 0: 아메리카노 / ICE / 2
Item 1: 카페라떼 / HOT / 1
```

## 학습 데이터

기준 데이터셋은 `merged_structure_b_v3.jsonl`이며 총 30,036개 문장으로 구성됩니다.

- 단일 주문 및 최대 3개 복합 주문
- 메뉴·온도·수량 누락 주문
- 지원하지 않는 옵션 요청
- 구어체와 메뉴 별칭
- 기존 train/valid/test 출처 유지

자세한 데이터셋 설명은 `docs/structure_b_v3_dataset_summary.md`를 참고합니다.

## 출력 라벨

### Intent

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

### Order Status

| 라벨 | 의미 |
|---|---|
| `NONE` | 주문 발화가 아님 |
| `VALID` | 필요한 주문 정보가 있고 정책상 유효함 |
| `INCOMPLETE` | 필요한 메뉴·온도·수량이 누락됨 |
| `CONFLICT` | 주문 조건이 서로 충돌함 |
| `OUT_OF_POLICY` | 지원하지 않는 메뉴 또는 옵션 요청 |
| `UNPARSABLE` | 주문 구조를 정상적으로 해석하지 못함 |

### Menu

| 라벨 | 허용 온도 |
|---|---|
| `NONE` | 슬롯 누락 또는 비활성 Item Query |
| `아메리카노` | `ICE`, `HOT` |
| `카페라떼` | `ICE`, `HOT` |
| `바닐라라떼` | `ICE`, `HOT` |
| `레몬에이드` | `ICE` |
| `딸기스무디` | `ICE` |

레몬에이드와 딸기스무디에 `HOT`을 요청하면 `OUT_OF_POLICY` 대상입니다.

### Temperature

```text
NONE, ICE, HOT
```

### Quantity

```text
NONE, 1, 2, 3, ... , 20
```

`NONE`은 추론 결과에서 `null`로 변환됩니다.

## NLU 패키지 출력 형식

`StructureBNLUPredictor.predict()`는 대화 문장을 만들지 않고 구조화된 의미 분석 결과만 반환합니다.

```json
{
  "schema_version": "1.0",
  "model_name": "structure_b_item_query_decoder",
  "text": "아이스 아메리카노 두 잔하고 따뜻한 카페라떼 한 잔 주세요",
  "intent": "ORDER",
  "intent_confidence": 0.9932,
  "order_status": "VALID",
  "order_status_confidence": 0.9871,
  "items": [
    {
      "item_id": 0,
      "menu": "아메리카노",
      "temperature": "ICE",
      "quantity": 2,
      "confidence": {
        "active": 0.9984,
        "menu": 0.9971,
        "temperature": 0.9962,
        "quantity": 0.9948
      },
      "missing_slots": []
    },
    {
      "item_id": 1,
      "menu": "카페라떼",
      "temperature": "HOT",
      "quantity": 1,
      "confidence": {
        "active": 0.9973,
        "menu": 0.9952,
        "temperature": 0.9938,
        "quantity": 0.9914
      },
      "missing_slots": []
    }
  ],
  "needs_reprompt": false,
  "device": "cuda",
  "latency_ms": 82.41
}
```

온도가 누락되면 값을 임의로 채우지 않습니다.

```json
{
  "order_status": "INCOMPLETE",
  "items": [
    {
      "item_id": 0,
      "menu": "아메리카노",
      "temperature": null,
      "quantity": 1,
      "missing_slots": ["temperature"]
    }
  ],
  "needs_reprompt": true
}
```

ROS `nlu_node`는 기존 `decision_node` 연결을 위해 `/intent_result`에 `confidence = intent_confidence` 호환 필드를 추가합니다. 모델 패키지 자체의 기준 필드는 `intent_confidence`입니다.

`robot_response`, `confirmation_text`, TTS 문장은 NLU 출력에 포함하지 않습니다.

## 역할 분리

| 구성 요소 | 책임 |
|---|---|
| `nlu/predictor.py` | 의도, 주문 상태, 메뉴, 온도, 수량 및 confidence 추론 |
| `nlu_node` | `/voice_text`를 받아 NLU 결과를 `/intent_result`로 발행 |
| `decision_node` | FSM 상태, 재질문, 주문 확인·수정·취소 및 발화 결정 |
| `action_node` | 발화를 TTS·LCD·표정·고개·팔 명령으로 변환 |
| `api/ros_bridge.py` | ROS Topic 결과를 관리자 웹에 전달 |
| 관리자 웹 | 실제 ROS 대화 흐름 표시 및 테스트 입력 제공 |

## 모델 파일 배치

```text
nlu/saved_models/structure_b_item_query_decoder/
├── best_model.pt
├── tokenizer/
└── encoder_config/       # 선택 사항
```

필수 항목은 `best_model.pt`와 `tokenizer/`입니다. `encoder_config/`가 없으면 코드에 내장된 koELECTRA-base 설정을 사용합니다.

모델 가중치는 저장소 용량을 고려해 Git에서 제외하고 Jetson에 별도로 복사할 수 있습니다.

## 환경 변수

```bash
export PUMPKIN_PROJECT_ROOT=~/pumpkin
export PUMPKIN_NLU_MODEL_DIR=~/pumpkin/nlu/saved_models/structure_b_item_query_decoder
export PUMPKIN_NLU_DEVICE=auto
export PUMPKIN_NLU_CONFIDENCE_THRESHOLD=0.5
```

`PUMPKIN_NLU_DEVICE=auto`는 CUDA가 사용 가능하면 GPU를 선택하고, 그렇지 않으면 CPU를 선택합니다.

## CLI 모델 점검

ROS 없이 모델 파일과 추론 코드만 확인할 때 사용합니다.

```bash
python3 -m nlu.cli \
  "아이스 아메리카노 두 잔 주세요"
```

```bash
python3 -m nlu.cli \
  "아이스 아메리카노 두 잔 주세요" \
  --device cuda \
  --confidence-threshold 0.5
```

Jetson 환경 전체 점검:

```bash
bash scripts/check_jetson_nlu.sh
```

## Python 사용 예

```python
from nlu import StructureBNLUPredictor

predictor = StructureBNLUPredictor(
    model_dir="nlu/saved_models/structure_b_item_query_decoder",
    device="auto",
)

result = predictor.predict("아이스 아메리카노 두 잔 주세요")
print(result)
```

운영 서비스에서는 Python에서 직접 여러 번 생성하지 않고 ROS `nlu_node`가 모델 하나를 소유합니다.

## 관리자 웹 테스트

관리자 웹의 테스트 입력은 다음 API를 사용합니다.

```http
POST /api/orders/analyze-step3
```

```json
{
  "text": "아이스 아메리카노 두 잔 주세요"
}
```

FastAPI는 입력을 직접 분석하지 않고 `/voice_text`에 발행합니다. 응답은 실제 ROS 흐름에서 수집한 다음 값을 포함합니다.

- NLU `/intent_result`
- Decision `/decision_result`
- Action `/robot_action`
- 최종 TTS 문장

브라우저의 mock NLU 분석은 사용하지 않습니다. 테스트하려면 ROS 핵심 노드가 실행 중이어야 합니다.

## 과거 모델

독립 Intent 모델과 Hierarchical Gated Multi-Task 모델의 코드 및 문서는 다음 경로에 보관합니다.

```text
experiments/nlu/
```

현재 운영 코드에서는 과거 모델을 자동 선택하거나 fallback하지 않습니다.

## 새 메뉴 추가 예시: 초코라떼

초코라떼처럼 새로운 메뉴 라벨을 추가하면 Menu Head의 출력 클래스 수가 바뀝니다. 따라서 정책 파일만 수정하거나 기존 `best_model.pt`를 그대로 사용하는 방식으로는 추가할 수 없습니다.

다음 항목은 반드시 같은 배포 단위로 변경합니다.

```text
공유 메뉴 정책
→ 학습 데이터
→ NLU 모델 재학습
→ 새 체크포인트 배치
→ 테스트
→ 관리자 웹·고객 앱 메뉴 목록
```

`nlu_node`는 시작할 때 체크포인트의 `menu`, `temperature`, `quantity` label map을 공유 정책과 비교합니다. 정책과 모델 중 하나만 변경하면 NLU READY 이전에 오류가 발생하는 것이 정상입니다.

### 1. 공유 메뉴 정책에 초코라떼 추가

다음 파일을 수정합니다.

```text
ros2_ws/src/robot_controller/robot_controller/menu_policy.py
```

초코라떼가 ICE와 HOT을 모두 지원한다고 가정하면 다음 세 항목에 추가합니다.

```python
SUPPORTED_MENUS = (
    "아메리카노",
    "카페라떼",
    "바닐라라떼",
    "레몬에이드",
    "딸기스무디",
    "초코라떼",
)

MENU_ALIASES = {
    # 기존 메뉴 생략
    "초코라떼": ("초코라떼", "초코라테", "초코 라떼"),
}

MENU_TEMPERATURE_POLICY = {
    # 기존 메뉴 생략
    "초코라떼": frozenset({"ICE", "HOT"}),
}
```

초코라떼를 아이스로만 판매한다면 허용 온도를 다음처럼 지정합니다.

```python
"초코라떼": frozenset({"ICE"})
```

허용 온도가 `ICE` 하나뿐이면 주문 스키마에서 온도 누락 시 `ICE`를 기본값으로 적용합니다.

### 2. 학습 데이터 생성 규칙 수정

현재 학습 데이터 증강 스크립트에도 학습용 메뉴 목록과 표면형이 있습니다.

```text
scripts/merge_and_augment_structure_b.py
```

ICE와 HOT을 모두 허용하는 초코라떼는 다음처럼 추가합니다.

```python
CHOICE_TEMP_MENUS = {
    "아메리카노",
    "카페라떼",
    "바닐라라떼",
    "초코라떼",
}

MENU_SURFACE = {
    # 기존 메뉴 생략
    "초코라떼": ["초코라떼", "초코 라떼", "초코라테"],
}
```

아이스 전용 메뉴라면 `CHOICE_TEMP_MENUS`가 아니라 `FIXED_ICE_MENUS`에 추가합니다.

### 3. 새 데이터셋 버전 생성

기존 `merged_structure_b_v3.jsonl`을 덮어쓰지 말고 새 버전으로 생성합니다.

```bash
python3 scripts/merge_and_augment_structure_b.py \
  --train <기존_train.jsonl> \
  --valid <기존_valid.jsonl> \
  --test <기존_test.jsonl> \
  --output data/merged_structure_b_v4.jsonl
```

초코라떼 데이터에는 최소한 다음 유형을 포함합니다.

- ICE·HOT 완전 주문
- 메뉴만 있고 온도 또는 수량이 누락된 주문
- `초코 라떼`, `초코라테` 등 별칭 주문
- 아메리카노·라떼 등 기존 메뉴와 섞인 복합 주문
- 수량 1~20 주문
- 주문 수정 발화

기존 train·valid·test의 출처 구분을 유지하고, 같은 원문이나 변형 문장이 서로 다른 split에 들어가지 않도록 확인합니다.

### 4. Structure B 모델 재학습

다음 노트북의 데이터 경로를 새 데이터셋으로 변경합니다.

```text
notebooks/koelectra_structure_b_item_query_decoder.ipynb
```

```text
기존: merged_structure_b_v3.jsonl
변경: merged_structure_b_v4.jsonl
```

초코라떼 추가로 Menu Head 클래스 수가 달라지므로 기존 가중치에 새 클래스만 끼워 넣지 말고 모델을 다시 학습합니다. validation `frame_accuracy`가 가장 높은 epoch를 새 `best_model.pt`로 저장합니다.

### 5. 새 체크포인트의 menu label 확인

학습이 끝난 후 운영 모델을 교체하기 전에 label map을 확인합니다.

```bash
cd ~/pumpkin

.venv-nlu/bin/python - <<'PY'
import torch

path = "nlu/saved_models/structure_b_item_query_decoder/best_model.pt"
checkpoint = torch.load(path, map_location="cpu", weights_only=False)
labels = checkpoint["label_maps"]["menu"]["id2label"]
print(labels)
PY
```

menu label에는 최소한 다음 값이 모두 있어야 합니다.

```text
NONE
아메리카노
카페라떼
바닐라라떼
레몬에이드
딸기스무디
초코라떼
```

### 6. 정책과 새 모델을 함께 배치

새 체크포인트를 바로 덮어쓰기 전에 기존 모델을 백업합니다.

```bash
cd ~/pumpkin/nlu/saved_models/structure_b_item_query_decoder
cp best_model.pt best_model.pt.backup
```

그다음 새 학습 결과의 다음 항목을 운영 경로에 배치합니다.

```text
best_model.pt
tokenizer/
encoder_config/       # 생성된 경우
```

공유 정책에는 초코라떼가 있는데 체크포인트에는 없거나, 체크포인트에는 있는데 공유 정책에는 없으면 `nlu_node`가 시작되지 않습니다. 정책 코드와 모델 파일을 반드시 함께 배포합니다.

### 7. 정책·스키마 테스트 추가

다음 테스트 파일에 초코라떼 케이스를 추가합니다.

```text
ros2_ws/src/robot_controller/test/test_menu_policy.py
ros2_ws/src/robot_controller/test/test_order_schema.py
ros2_ws/src/robot_controller/test/test_dialogue_flow.py
```

최소 확인 항목은 다음과 같습니다.

```text
초코 라떼 → 초코라떼
초코라테 → 초코라떼
아이스 초코라떼 두 잔 → 초코라떼 / ICE / 2
따뜻한 초코라떼 한 잔 → 초코라떼 / HOT / 1
초코라떼 한 잔 → 온도 누락으로 재질문
기존 메뉴와 초코라떼의 복합 주문 분리
```

테스트와 ROS2 빌드를 실행합니다.

```bash
cd ~/pumpkin/ros2_ws

PYTHONPATH=src/robot_controller \
python3 -m pytest \
  src/robot_controller/test/test_menu_policy.py \
  src/robot_controller/test/test_order_schema.py \
  src/robot_controller/test/test_dialogue_flow.py \
  -q

colcon build \
  --packages-select robot_controller \
  --symlink-install
```

### 8. Jetson에서 NLU와 전체 흐름 확인

먼저 모델 자체를 확인합니다.

```bash
cd ~/pumpkin

PUMPKIN_NLU_DEVICE=cuda \
.venv-nlu/bin/python -m nlu.cli \
  "아이스 초코라떼 두 잔 주세요"
```

예상 핵심 결과는 다음과 같습니다.

```json
{
  "intent": "ORDER",
  "items": [
    {
      "menu": "초코라떼",
      "temperature": "ICE",
      "quantity": 2
    }
  ],
  "device": "cuda"
}
```

전체 ROS 흐름도 실행합니다.

```bash
bash scripts/check_jetson_nlu.sh

PUMPKIN_NLU_DEVICE=cuda \
bash scripts/run_pos_with_nlu.sh
```

실행 로그에 다음 메시지가 출력돼야 합니다.

```text
NLU label maps match the shared menu policy
NLU node ready
```

### 9. 관리자 웹과 고객 앱 메뉴 목록 갱신

NLU 라벨을 추가해도 관리자 웹과 고객 앱의 상품 목록은 자동으로 추가되지 않습니다. 저장소의 하드코딩된 메뉴 목록을 검색해 함께 수정합니다.

```bash
git grep -n "딸기스무디"
```

현재 확인 대상에는 다음 파일이 포함됩니다.

```text
web/src/App.tsx
apps/customer-mobile/src/native/menuData.ts
apps/customer-mobile/src/CustomerMobileApp.tsx
```

메뉴명뿐 아니라 가격, 설명, 이미지, 판매 가능 온도도 함께 등록한 후 웹과 앱에서 주문 등록까지 확인합니다.
