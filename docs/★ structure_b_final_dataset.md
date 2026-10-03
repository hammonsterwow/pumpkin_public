# Structure B 최종 통합 데이터셋

> **최종 기준일: 2026-08-09**  
> 이 문서는 현재 `main` 브랜치에서 사용하는 **Structure B 최종 학습/테스트 데이터셋의 기준 문서**이다.
>
> 이전 문서인 `docs/structure_b_v3_dataset_summary.md`는 과거 데이터 생성·정리 이력을 확인하기 위한 참고 자료이며, **현재 학습 파일 기준은 이 문서를 따른다.**

---

## 1. 최종 사용 파일

현재 NLU 학습 및 평가에 사용할 canonical 데이터셋은 아래 두 파일이다.

```text
data/
├── structure_b_train_valid.jsonl
└── structure_b_test.jsonl
```

- 학습/검증용: `data/structure_b_train_valid.jsonl`
- 최종 테스트용: `data/structure_b_test.jsonl`

기존 데이터셋은 삭제하지 않고 아래 경로에 보관했다.

```text
experiments/nlu/data_archive/
├── structure_b_train_valid.jsonl
└── structure_b_test.jsonl
```

따라서 **새 모델 학습에는 `data/`의 파일을 사용하고**, 이전 버전 비교가 필요한 경우에만 `experiments/nlu/data_archive/`를 사용한다.

---

## 2. 최종 데이터 규모

| 구분 | 기존 main 데이터 | 새 비-ORDER 데이터 추가 | 최종 데이터 |
|---|---:|---:|---:|
| Train/Valid | 20,000 | 2,512 | **22,512** |
| Test | 880 | 627 | **1,507** |
| 합계 | 20,880 | 3,139 | **24,019** |

최종 통합 과정에서는 작업 당시 `main`에 존재하던 최신 ORDER 데이터를 그대로 보존하고, 새로 만든 비-ORDER 데이터를 추가했다.

즉 이전 버전의 ORDER 데이터를 덮어쓰거나 줄이지 않고 다음과 같이 확장했다.

```text
Train/Valid: 20,000 → 22,512
Test:          880 → 1,507
```

최종 통합 commit:

```text
a31744333ae52e447d6f104837cd1f08e9f3940d
```

commit message:

```text
data(nlu): promote integrated Structure B datasets

train: 20000 -> 22512; test: 880 -> 1507
```

---

## 3. Intent 분포

현재 최종 데이터셋의 intent 분포는 다음과 같다.

| Intent | Train/Valid | Test | 전체 |
|---|---:|---:|---:|
| `ORDER` | 20,000 | 880 | **20,880** |
| `AFFIRM` | 320 | 80 | **400** |
| `DENY` | 256 | 64 | **320** |
| `MODIFY` | 784 | 196 | **980** |
| `CANCEL` | 320 | 80 | **400** |
| `GUIDE` | 192 | 48 | **240** |
| `UNKNOWN` | 640 | 159 | **799** |
| `PAYMENT` | 0 | 0 | **0** |
| **합계** | **22,512** | **1,507** | **24,019** |

### 현재 intent별 역할

- `ORDER`: 신규 주문 및 주문 슬롯을 포함한 주문 관련 발화
- `AFFIRM`: 긍정/확인 응답
- `DENY`: 부정 응답
- `MODIFY`: 이미 입력된 주문의 메뉴·온도·수량 수정
- `CANCEL`: 주문 취소 요청
- `GUIDE`: 매장 이용 또는 위치 안내 관련 요청
- `UNKNOWN`: 지원 범위 밖이거나 의미가 불명확한 발화
- `PAYMENT`: 모델 라벨 체계에는 정의되어 있으나 **현재 최종 데이터셋에는 학습 샘플이 없음**

`PAYMENT` 기능을 NLU에서 직접 분류하도록 학습하려면 PAYMENT 데이터를 별도로 추가해야 한다.

---

## 4. 이번 통합에서 추가된 비-ORDER 데이터

기존 데이터는 ORDER 중심이었기 때문에 실제 대화 FSM에서 필요한 사용자 응답을 분류할 수 있도록 비-ORDER intent 데이터를 추가했다.

### Train/Valid 추가분

| Intent | 추가 수 |
|---|---:|
| `AFFIRM` | 320 |
| `DENY` | 256 |
| `MODIFY` | 784 |
| `CANCEL` | 320 |
| `GUIDE` | 192 |
| `UNKNOWN` | 640 |
| **합계** | **2,512** |

### Test 추가분

| Intent | 추가 수 |
|---|---:|
| `AFFIRM` | 80 |
| `DENY` | 64 |
| `MODIFY` | 196 |
| `CANCEL` | 80 |
| `GUIDE` | 48 |
| `UNKNOWN` | 159 |
| **합계** | **627** |

대표적으로 다음과 같은 대화 상황을 학습 대상으로 본다.

```text
AFFIRM
- 네
- 맞아요
- 그대로 주세요

DENY
- 아니요
- 그거 아니에요
- 틀렸어요

MODIFY
- 두 잔 말고 세 잔으로 바꿔주세요
- 아이스 말고 핫으로요
- 아메리카노 말고 카페라떼로 바꿀게요

CANCEL
- 주문 취소할게요
- 전부 취소해주세요
- 그냥 안 할게요

UNKNOWN
- 잠깐만요
- 메뉴 좀 볼게요
- 너 뭐 먹을래?
- 아메리카노 맛있어요?
```

위 예시는 intent 의미를 설명하기 위한 대표 형태이며, 실제 학습 파일에는 다양한 표현이 포함되어 있다.

---

## 5. 데이터 JSONL 구조

각 줄은 하나의 JSON object로 구성한다.

기본 필드는 다음과 같다.

```json
{
  "text": "아이스 아메리카노 두 잔 주세요",
  "intent": "ORDER",
  "items": [
    {
      "item_id": 0,
      "menu": "아메리카노",
      "temperature": "ICE",
      "quantity": 2,
      "missing_slots": [],
      "validation_errors": []
    }
  ],
  "source": {},
  "order_status": "VALID",
  "validation_errors": []
}
```

주요 필드 의미:

| 필드 | 의미 |
|---|---|
| `text` | 사용자의 실제 발화 텍스트 |
| `intent` | 문장 전체의 의도 |
| `items` | 주문 항목 목록 |
| `item_id` | 문장 안 주문 항목의 순서 |
| `menu` | 메뉴 슬롯 |
| `temperature` | `ICE`, `HOT` 또는 누락 |
| `quantity` | 1~20 또는 누락 |
| `missing_slots` | 해당 item에서 누락된 슬롯 |
| `source` | 데이터 생성/분할 출처 정보 |
| `order_status` | 주문 구조의 상태 |
| `validation_errors` | 정책 또는 구조 검증 오류 |

---

## 6. 모델에서 사용하는 슬롯 범위

### Menu

현재 지원 메뉴는 5개이다.

```text
아메리카노
카페라떼
바닐라라떼
레몬에이드
딸기스무디
```

### Temperature

```text
NONE
ICE
HOT
```

정책상:

- 아메리카노: ICE / HOT
- 카페라떼: ICE / HOT
- 바닐라라떼: ICE / HOT
- 레몬에이드: ICE only
- 딸기스무디: ICE only

따라서 레몬에이드 또는 딸기스무디에 HOT을 요청하는 문장은 정상 주문으로 임의 보정하지 않고 정책 위반으로 처리해야 한다.

### Quantity

```text
NONE, 1, 2, ..., 20
```

### 최대 주문 item 수

현재 Structure B Item Query Decoder는 최대 **3개 주문 item**을 대상으로 한다.

---

## 7. Order Status

현재 사용하는 Order Status는 다음과 같다.

| Status | 의미 |
|---|---|
| `NONE` | 주문 발화가 아님 |
| `VALID` | 필요한 주문 정보가 있고 정책상 유효함 |
| `INCOMPLETE` | 필요한 주문 슬롯이 일부 누락됨 |
| `CONFLICT` | 한 주문 내 조건이 충돌함 |
| `OUT_OF_POLICY` | 지원하지 않는 메뉴 또는 옵션 요청 |
| `UNPARSABLE` | 주문 구조를 정상적으로 해석하지 못함 |

---

## 8. 슬롯 누락 발화 라벨링 원칙

대화 도중 로봇이 특정 슬롯을 다시 질문하는 상황에서는 사용자가 짧게 대답할 수 있다.

예:

```text
로봇: 몇 잔 주문하시겠어요?
사용자: 두 잔이요
```

```text
로봇: 아이스로 드릴까요, 핫으로 드릴까요?
사용자: 아이스로요
```

이때 NLU 데이터에는 **사용자가 실제로 말한 슬롯만 기록한다.**

예를 들어 `두 잔이요`에서 앞선 대화의 메뉴가 아메리카노였더라도 NLU 정답에 아메리카노를 임의로 넣지 않는다.

```text
두 잔이요
→ quantity = 2
→ menu = null
→ temperature = null
```

```text
아이스로요
→ temperature = ICE
→ menu = null
→ quantity = null
```

이전 대화의 메뉴/주문 item과 연결하는 역할은 NLU가 아니라 **Decision/FSM의 `waiting_for` 문맥 처리**가 담당한다.

즉:

```text
NLU = 지금 사용자가 실제로 말한 의미 추출
Decision/FSM = 이전 대화 문맥과 결합
```

이 원칙을 유지해야 NLU와 FSM의 역할이 꼬이지 않는다.

---

## 9. NLU Intent와 Decision 값 구분

다음 값들은 NLU intent가 아니다.

```text
CONTINUE_ORDER
NEXT_CUSTOMER_READY
REORDER_REQUEST
CONFIRM_ORDER
ORDER_CONFIRMED
ASK_MENU
ASK_QUANTITY
ASK_TEMPERATURE
```

이 값들은 `decision_node`가 대화 상태를 보고 출력하는 Decision이다.

예를 들어 사용자가 `아니요`라고 말하면 NLU는 항상 다음과 같이 의미만 분류한다.

```text
intent = DENY
```

그 뒤 현재 FSM state가 무엇인지에 따라 Decision의 의미가 달라진다.

예:

```text
ORDER_CONFIRM 상태에서 DENY
→ 주문 내용 수정 단계

WAIT_NEXT_CUSTOMER 상태에서 DENY
→ 주문을 더 받는 단계
```

따라서 FSM 동작을 표현하기 위해 `CONTINUE_ORDER`, `FINISH_ORDER` 같은 값을 NLU 학습 intent로 임의 추가하지 않는다.

---

## 10. 추가 주문 표현 처리

현재 NLU intent에는 `ADD_ORDER`가 없다.

예를 들어 한 문장 안에서 다음처럼 추가 메뉴를 함께 말하는 것은 일반 ORDER의 복합 주문으로 처리할 수 있다.

```text
아메리카노 한 잔 주세요. 아, 카페라떼도 한 잔 추가할게요.
```

반면 주문 확인 이후 사용자가 다음처럼 말하는 경우:

```text
하나 더 주문할게요
```

현재 시스템에서는 상태 의존적인 짧은 표현을 `dialogue_act_resolver`와 FSM이 보조 처리한다.

향후 `ADD_ORDER`를 별도 NLU intent로 도입하려면 데이터만 추가하는 것이 아니라 아래를 함께 변경해야 한다.

```text
label map
모델 intent head
학습 데이터
predictor
Decision/FSM
관련 테스트
```

따라서 현재 데이터셋에는 `ADD_ORDER`를 별도 intent로 추가하지 않는다.

---

## 11. 긍정/부정 제스처와 NLU 데이터 구분

사람의 고개 끄덕임/좌우 흔들기는 카메라 기반 Vision 입력이다.

```text
NOD   → 의미상 AFFIRM
SHAKE → 의미상 DENY
```

하지만 이것은 텍스트 NLU 학습 데이터에 넣지 않는다.

```text
음성/텍스트 → NLU
고개 제스처 → Vision
```

Decision 단계에서 두 입력을 같은 확인 의미로 사용할 수 있지만, 데이터 수집과 모델 학습은 분리한다.

---

## 12. 학습 시 주의 사항

### 1) 반드시 현재 `data/` 파일 사용

```text
O  data/structure_b_train_valid.jsonl
O  data/structure_b_test.jsonl
```

아래 파일은 이전 버전 보관용이다.

```text
X  experiments/nlu/data_archive/structure_b_train_valid.jsonl
X  experiments/nlu/data_archive/structure_b_test.jsonl
```

### 2) 이전 v3 문서의 30,036개 수치와 혼동하지 않기

`docs/structure_b_v3_dataset_summary.md`의 `merged_structure_b_v3.jsonl` 30,036개 데이터는 이전 데이터 구성 단계의 기록이다.

현재 운영 학습 기준은 본 문서의 **22,512 train/valid + 1,507 test**이다.

### 3) Test 문장을 Train에 그대로 복사하지 않기

비슷한 표현을 추가하더라도 test의 exact sentence를 train에 복사하면 평가 데이터 누수가 발생한다.

### 4) 문맥을 NLU 정답에 임의 주입하지 않기

짧은 후속 답변에는 실제 발화에 포함된 슬롯만 라벨링하고, 이전 문맥 복원은 FSM에서 처리한다.

### 5) 새 intent 추가 시 코드까지 같이 변경

데이터에 새로운 intent 문자열만 추가하면 현재 label map과 모델 출력 차원이 맞지 않을 수 있다.

새 intent를 도입할 때는 모델/label map/Decision까지 함께 변경해야 한다.

### 6) PAYMENT는 현재 데이터 없음

코드의 intent schema에는 `PAYMENT`가 정의되어 있지만 현재 최종 데이터셋에는 PAYMENT 샘플이 없다.

PAYMENT 분류를 실제 모델 기능으로 사용할 시 별도 데이터 보강이 필요하다.

---

## 13. 현재 모델과의 관계

현재 운영 NLU 모델 구조:

```text
structure_b_item_query_decoder
```

학습 notebook:

```text
notebooks/koelectra_structure_b_item_query_decoder.ipynb
```

모델 구조 요약:

```text
사용자 문장
    ↓
koELECTRA-base Encoder
    ├── Intent Head
    ├── Order Status Head
    └── Token Memory
             ↑
        3 Item Queries
             ↓
     Transformer Decoder
        ├── Item Active
        ├── Menu
        ├── Temperature
        └── Quantity
```

현재 최대 주문 항목 수는 3개이며, NLU는 대화 응답 문장이나 FSM 상태 전환을 직접 생성하지 않는다.

---

## 14. 팀 공유용 요약

팀원에게는 아래 내용만 우선 공유하면 된다.

```text
[Pumpkin NLU 최종 데이터셋]

학습/검증:
data/structure_b_train_valid.jsonl
22,512개

테스트:
data/structure_b_test.jsonl
1,507개

총 24,019개

Intent:
ORDER / AFFIRM / DENY / MODIFY / CANCEL / GUIDE / UNKNOWN

PAYMENT는 코드 라벨에는 있지만 현재 데이터는 0개.

기존 데이터는 삭제하지 않고
experiments/nlu/data_archive/
에 보관함.

학습할 때는 반드시 data/의 두 파일을 사용.
```

---

## 15. 최종 기준

앞으로 Structure B 데이터 관련 수치나 파일 경로가 다른 문서와 충돌할 경우 **이 문서와 현재 `main/data/`의 canonical JSONL 파일을 최종 기준으로 본다.**

데이터를 추가하거나 재분할하면 이 문서의 다음 항목을 함께 갱신한다.

1. 최종 파일 경로
2. Train/Test 전체 행 수
3. Intent별 분포
4. 지원 슬롯/정책 변경 사항
5. 추가/삭제된 intent
6. 관련 commit SHA
