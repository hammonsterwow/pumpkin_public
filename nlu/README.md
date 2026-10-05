# Pumpkin NLU

Pumpkin 로봇의 ROS2 대화 파이프라인에서 사용하는 **한국어 주문 NLU 추론 패키지**입니다.

현재 production runtime의 모델 이름은 `structure_b_item_query_decoder`이며, 기본 encoder는 **`monologg/koelectra-small-v3-discriminator`** 입니다. 코드에는 과거 Structure B 체크포인트 복원을 위해 koELECTRA-base 설정도 호환용으로 남아 있지만, 현재 기본 설정은 koELECTRA-small입니다.

> 서비스 메뉴의 최종 기준은 `config/menu_catalog.json`입니다. NLU는 자연어를 메뉴·온도·수량 등의 구조화된 라벨로 변환하고, 서비스 계층이 이 결과를 공식 메뉴 카탈로그와 연결합니다.

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

NLU 모델은 ROS2의 `nlu_node`에서 한 번 로딩합니다. 관리자 웹과 FastAPI는 별도 NLU 모델을 중복 로딩하지 않고 ROS Topic에서 발생한 NLU·Decision·Action 결과를 표시합니다.

관리자 웹이 관찰하는 주요 Topic:

```text
/stt/status
/voice_text
/intent_result
/decision_result
/robot_action
/fsm/state
/face/recognition
```

웹의 텍스트 테스트도 별도 mock NLU를 수행하지 않고 `/voice_text`에 입력을 발행하여 실제 `nlu_node → decision_node → action_node` 흐름을 실행합니다.

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
└── requirements-jetson-inference.txt
```

| 파일 | 역할 |
|---|---|
| `config.py` | 모델명, 모델 경로, 기본 encoder, device, confidence threshold 설정 |
| `model.py` | koELECTRA Encoder + Item Query Transformer Decoder 신경망 구조 |
| `predictor.py` | 체크포인트/토크나이저 로딩, 추론, 라벨 디코딩, confidence 및 missing slot 계산 |
| `schema.py` | NLU 최종 출력 TypedDict 스키마 |
| `cli.py` | ROS 없이 NLU 모델만 점검하는 명령줄 도구 |
| `requirements-jetson-inference.txt` | Jetson 추론에 필요한 Python 의존성 |

모델 가중치는 저장소 용량 때문에 Git에서 제외할 수 있으며 기본 경로는 다음과 같습니다.

```text
nlu/saved_models/structure_b_item_query_decoder/
├── best_model.pt
├── tokenizer/
└── encoder_config/       # 선택 사항
```

`encoder_config/`가 없으면 현재 지원하는 koELECTRA-small/base의 내장 config를 사용합니다.

## 현재 모델 구조

```text
사용자 문장
    ↓
koELECTRA-small Encoder
    ├── [CLS] → Intent Head
    ├── [CLS] → Order Status Head
    └── Token Memory
             ↑
     최대 3개의 Learned Item Query
             ↓
     Transformer Decoder 2 layers
             ├── Item Active Head
             ├── Menu Head
             ├── Temperature Head
             └── Quantity Head
```

현재 코드 기준:

- 기본 Encoder: `monologg/koelectra-small-v3-discriminator`
- 호환 Encoder: `monologg/koelectra-base-v3-discriminator`
- 최대 입력 길이: 체크포인트 값 사용, 기본 실험값 96 tokens
- 최대 주문 항목: 체크포인트 값 사용, 현재 Structure B 실험 기준 3개
- Item Query Decoder: 2 layers
- 기본 confidence threshold: `0.5`

예시:

```text
아이스 아메리카노 두 잔하고 따뜻한 카페라떼 한 잔 주세요.
```

```text
Item 0: 아메리카노 / ICE / 2
Item 1: 카페라떼 / HOT / 1
```

## 현재 canonical 학습 데이터

현재 `main`에서 NLU 학습·평가의 기준 데이터는 다음 두 파일입니다.

```text
data/structure_b_train_valid.jsonl   # 22,512개
data/structure_b_test.jsonl          # 1,507개
```

총 **24,019개**이며, 자세한 기준은 [`docs/★ structure_b_final_dataset.md`](../docs/%E2%98%85%20structure_b_final_dataset.md)를 따릅니다.

Intent 분포의 중요한 점:

- `ORDER`: 신규 주문
- `AFFIRM`: 긍정/확인
- `DENY`: 부정
- `MODIFY`: 주문 수정
- `CANCEL`: 주문 취소
- `GUIDE`: 매장 이용/위치 안내
- `UNKNOWN`: 지원 범위 밖 또는 불명확 발화
- `PAYMENT`: 라벨은 정의되어 있지만 **현재 canonical 데이터셋에는 학습 샘플이 없음**

## KIPS 2026 비교 실험

현재 공개 저장소에서 Item Query Decoder의 비교 실험과 재현 코드는 아래에 있습니다.

[`experiments/nlu/kips_2026_item_query/`](../experiments/nlu/kips_2026_item_query/)

공통 실험 조건:

- Encoder: koELECTRA-small
- 데이터: `data/structure_b_train_valid.jsonl`, `data/structure_b_test.jsonl`
- max length: 96
- max item queries: 3
- seeds: 42, 43, 44

비교 모델:

| ID | 구성 | 목적 |
|---|---|---|
| M0 | KoELECTRA-small + Independent Item Heads | 구조 baseline |
| M1 | KoELECTRA-small + Item Query Decoder | Item Query 구조 자체 효과 비교 |
| M2 | M1 + improved training | differential LR, multi-order oversampling, weighted loss 적용 |

실험 상세와 결과 파일 구조는 [KIPS 실험 README](../experiments/nlu/kips_2026_item_query/README.md)를 참고합니다.

## 출력 라벨

### Intent

```text
ORDER, MODIFY, CANCEL, AFFIRM, DENY, GUIDE, PAYMENT, UNKNOWN
```

### Order Status

```text
NONE, VALID, INCOMPLETE, CONFLICT, OUT_OF_POLICY, UNPARSABLE
```

### Menu

현재 서비스 메뉴 카탈로그 기준 메뉴는 5개입니다.

| 메뉴 | 허용 온도 |
|---|---|
| 아메리카노 | ICE, HOT |
| 카페라떼 | ICE, HOT |
| 바닐라라떼 | ICE, HOT |
| 레몬에이드 | ICE |
| 딸기스무디 | ICE |

서비스 메뉴의 가격·별칭·판매 가능 온도는 **[`config/menu_catalog.json`](../config/menu_catalog.json)** 을 기준으로 합니다.

### Temperature

```text
NONE, ICE, HOT
```

### Quantity

```text
NONE, 1, 2, 3, ... , 20
```

`NONE`은 최종 추론 결과에서 `null`로 변환됩니다.

## NLU 출력 형식

`StructureBNLUPredictor.predict()`는 사용자에게 말할 문장을 생성하지 않고 구조화된 의미 분석 결과만 반환합니다.

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
    }
  ],
  "needs_reprompt": false,
  "device": "cuda",
  "latency_ms": 82.41
}
```

온도나 수량 등이 누락되면 임의로 채우지 않고 `missing_slots`와 `needs_reprompt`를 통해 상위 FSM이 재질문할 수 있도록 전달합니다.

## 역할 분리

| 구성 요소 | 책임 |
|---|---|
| `nlu/predictor.py` | intent, order status, menu, temperature, quantity 및 confidence 추론 |
| `nlu_node` | `/voice_text`를 받아 NLU 결과를 `/intent_result`로 발행 |
| `decision_node` | FSM 상태, 재질문, 주문 확인·수정·취소 및 발화 결정 |
| `action_node` | Decision 결과를 TTS·LCD·고개·팔 명령으로 변환 |
| `api/ros_bridge.py` | ROS Topic 결과를 관리자 웹에 전달 |
| 관리자 웹 | 실제 ROS 대화 흐름 표시 및 테스트 입력 제공 |

사용자에게 말할 문장, FSM 상태 전환, TTS 및 로봇 동작은 `nlu/`의 책임이 아닙니다.

## 환경 변수

```bash
export PUMPKIN_PROJECT_ROOT=~/pumpkin
export PUMPKIN_NLU_MODEL_DIR=~/pumpkin/nlu/saved_models/structure_b_item_query_decoder
export PUMPKIN_NLU_DEVICE=auto
export PUMPKIN_NLU_CONFIDENCE_THRESHOLD=0.5
```

`PUMPKIN_NLU_DEVICE=auto`는 CUDA가 사용 가능하면 GPU를 선택하고, 그렇지 않으면 CPU를 선택합니다.

## CLI 모델 점검

```bash
python3 -m nlu.cli "아이스 아메리카노 두 잔 주세요"
```

운영 서비스에서는 Python 코드에서 Predictor를 여러 번 만들지 않고 ROS2 `nlu_node`가 모델 하나를 소유합니다.

## 메뉴 변경 시 주의

새 메뉴를 추가하면 NLU의 Menu Head 출력 클래스가 바뀔 수 있으므로 **카탈로그만 수정하고 기존 체크포인트를 그대로 사용하는 방식은 안전하지 않습니다.**

변경 시 최소한 아래를 같은 배포 단위로 확인해야 합니다.

```text
config/menu_catalog.json
→ 학습 데이터
→ NLU label map / 모델 재학습
→ 새 체크포인트
→ ROS2 주문 검증 정책
→ STT 메뉴 보정
→ 고객 앱 / 관리자 POS
→ 관련 테스트
```

현재 서비스 메뉴의 Single Source of Truth는 `config/menu_catalog.json`이며, NLU 데이터는 모델 학습 라벨의 기준입니다.
