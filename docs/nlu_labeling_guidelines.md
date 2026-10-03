# Pumpkin NLU 데이터 라벨링 규칙

이 문서는 Pumpkin 무인매장 로봇의 NLU 학습 데이터를 사람이 일관되게 작성·검수하기 위한 기준이다.

핵심 원칙은 다음과 같다.

1. **이번 발화에서 사용자가 실제로 말한 의미만 라벨링한다.**
2. 문장에 없는 메뉴·온도·수량을 추측해서 넣지 않는다.
3. 기존 주문 내용이나 직전 로봇 질문은 NLU 라벨에 복사하지 않는다. 대화 문맥 연결은 FSM이 담당한다.
4. 문장이 애매하면 임의로 확정하지 말고 `review_required=true`로 표시한다.
5. 자연스럽지 않은 문장은 라벨만 고치지 말고 데이터에서 제외하거나 문장 자체를 다시 작성한다.

---

## 1. 최종 Intent 라벨

| Intent | 의미 | 대표 예시 |
|---|---|---|
| `ORDER` | 신규 주문 또는 주문 슬롯에 대한 답변 | `아이스 아메리카노 한 잔 주세요`, `두 잔이요` |
| `MODIFY` | 이미 존재하는 주문의 메뉴·온도·수량을 변경 | `두 잔 말고 한 잔이요`, `라떼로 바꿔주세요` |
| `CANCEL` | 전체 주문 또는 특정 주문 항목 제거 | `방금 주문 취소할게요`, `라떼는 빼주세요` |
| `AFFIRM` | 긍정·확인 응답 | `네`, `맞아요`, `그대로 해주세요` |
| `DENY` | 부정·거절 응답 | `아니요`, `그건 아니에요` |
| `INQUIRY` | 결제·가격·위치·매장 이용·메뉴 안내 문의 | `카드 결제돼요?`, `화장실 어디예요?` |
| `UNKNOWN` | 지원 범위 밖이거나 의미가 불명확한 발화 | `오늘 기분이 이상해요`, `음... 모르겠어요` |

### 1.1 ORDER와 MODIFY 구분

- 현재 주문을 새로 구성하는 발화는 `ORDER`이다.
- 이미 생성된 주문을 바꾸려는 의미가 명시되면 `MODIFY`이다.
- `말고`, `대신`, `바꿔`, `변경`, `수정`, `아니고` 등이 대표적인 수정 표현이다.

| 발화 | Intent | 이유 |
|---|---|---|
| `라떼 한 잔 주세요` | `ORDER` | 신규 주문 |
| `아메리카노 말고 라떼로 주세요` | `MODIFY` | 기존 선택 변경 |
| `두 잔 말고 한 잔이요` | `MODIFY` | 기존 수량 변경 |
| `주문 수정할게요` | `MODIFY` | 수정 의사만 표현 |
| `한 잔이요` | `ORDER` | 수정 표현이 없는 슬롯 답변 |

대화 문맥이 없으면 신규 주문인지 수정인지 확정하기 어려운 문장은 `review_required=true`로 보낸다.

### 1.2 MODIFY와 CANCEL 구분

- 새 값으로 교체하면 `MODIFY`이다.
- 항목을 제거하거나 주문 자체를 없애면 `CANCEL`이다.

| 발화 | Intent |
|---|---|
| `라떼 말고 아메리카노로요` | `MODIFY` |
| `라떼는 빼주세요` | `CANCEL` |
| `방금 거 전부 취소할게요` | `CANCEL` |

### 1.3 AFFIRM과 DENY

`네`, `아니요`의 실제 후속 행동은 현재 FSM 상태가 결정한다. NLU는 긍정과 부정만 분류한다.

| 발화 | Intent |
|---|---|
| `네` | `AFFIRM` |
| `네 맞아요` | `AFFIRM` |
| `그대로 해주세요` | `AFFIRM` |
| `아니요` | `DENY` |
| `그건 아니에요` | `DENY` |
| `네, 그런데 두 잔으로 바꿔주세요` | `MODIFY` |

긍정·부정과 수정 내용이 함께 있으면 실제 행동을 더 구체적으로 나타내는 `MODIFY`를 우선한다.

### 1.4 INQUIRY 세부 유형

`INQUIRY`는 필요하면 다음 보조 필드로 세분화한다.

```text
inquiry_type:
NONE / PAYMENT / PRICE / LOCATION / STORE_INFO / MENU_INFO / OTHER
```

| 발화 | Intent | inquiry_type |
|---|---|---|
| `카드 결제돼요?` | `INQUIRY` | `PAYMENT` |
| `아메리카노 얼마예요?` | `INQUIRY` | `PRICE` |
| `화장실 어디예요?` | `INQUIRY` | `LOCATION` |
| `몇 시까지 해요?` | `INQUIRY` | `STORE_INFO` |
| `메뉴 뭐 있어요?` | `INQUIRY` | `MENU_INFO` |

문의가 아닌 문장은 `inquiry_type=NONE`으로 둔다.

---

## 2. 주문 Item 라벨링

각 주문 Item은 다음 필드를 갖는다.

```json
{
  "item_id": 0,
  "menu": "아메리카노",
  "temperature": "ICE",
  "quantity": 1
}
```

최대 3개 Item을 허용한다. 문장에 등장한 순서대로 `item_id`를 부여한다.

### 2.1 Menu

| 정규화 라벨 | 허용 표현 예시 |
|---|---|
| `아메리카노` | 아메리카노, 아메, 아아, 뜨아 |
| `카페라떼` | 카페라떼, 카페라테, 라떼 |
| `바닐라라떼` | 바닐라라떼, 바닐라 라떼, 바닐라라테 |
| `레몬에이드` | 레몬에이드, 레모네이드, 레몬 에이드 |
| `딸기스무디` | 딸기스무디, 딸기 스무디 |

문장에 메뉴가 없으면 `menu=null`이다.

### 2.2 Temperature

선택 온도 메뉴:

```text
아메리카노 / 카페라떼 / 바닐라라떼
```

| 표현 | 라벨 |
|---|---|
| 아이스, 차갑게, 시원하게, 찬 걸로, 아아 | `ICE` |
| 핫, 따뜻하게, 뜨겁게, 뜨아 | `HOT` |
| 온도 표현 없음 | `null` |

예시:

| 발화 | temperature |
|---|---|
| `바닐라라떼 하나 주세요` | `null` |
| `아이스 바닐라라떼 하나요` | `ICE` |
| `따뜻한 라떼 주세요` | `HOT` |

`바닐라라떼`라는 메뉴명만 보고 ICE를 넣으면 안 된다.

고정 ICE 메뉴:

```text
레몬에이드 / 딸기스무디
```

- 온도를 말하지 않아도 서비스 정책상 `ICE`로 라벨링한다.
- 사용자가 명시적으로 HOT을 요청하면 발화 의미를 보존하여 `temperature=HOT`으로 기록하고 `order_status=OUT_OF_POLICY`로 처리한다.

예시:

| 발화 | temperature | order_status |
|---|---|---|
| `레몬에이드 하나 주세요` | `ICE` | `VALID` |
| `뜨거운 레몬에이드 하나 주세요` | `HOT` | `OUT_OF_POLICY` |

### 2.3 Quantity

| 표현 | 라벨 |
|---|---:|
| 한 잔, 하나, 한 개, 1잔 | 1 |
| 두 잔, 둘, 두 개, 2잔 | 2 |
| 세 잔, 셋, 세 개, 3잔 | 3 |
| 수량 표현 없음 | `null` |

메뉴가 단수처럼 들린다는 이유로 자동으로 1을 넣지 않는다.

| 발화 | quantity |
|---|---:|
| `아메리카노 주세요` | `null` |
| `아메리카노 하나 주세요` | 1 |
| `라떼 두 잔이요` | 2 |

---

## 3. Order Status

`ORDER`와 슬롯이 포함된 `MODIFY` 발화에 대해 주문 상태를 기록한다. 주문과 무관한 intent는 `order_status=null`로 둔다.

| Status | 기준 |
|---|---|
| `VALID` | 서비스에 필요한 메뉴·온도·수량이 모두 있고 정책상 허용됨 |
| `INCOMPLETE` | 필요한 슬롯이 하나 이상 누락됨 |
| `CONFLICT` | 한 문장 안에서 같은 Item의 정보가 서로 충돌함 |
| `OUT_OF_POLICY` | 지원하지 않는 메뉴·온도·수량 요청 |
| `UNPARSABLE` | 주문 의도는 있으나 Item 구조를 만들 수 없음 |

### 3.1 누락 슬롯

선택 온도 메뉴는 메뉴·온도·수량이 모두 있어야 `VALID`이다.

```json
{
  "text": "바닐라라떼 하나 주세요",
  "intent": "ORDER",
  "order_status": "INCOMPLETE",
  "items": [
    {
      "menu": "바닐라라떼",
      "temperature": null,
      "quantity": 1,
      "missing_slots": ["temperature"]
    }
  ]
}
```

고정 ICE 메뉴는 온도 미언급을 누락으로 보지 않는다.

```json
{
  "text": "레몬에이드 하나 주세요",
  "intent": "ORDER",
  "order_status": "VALID",
  "items": [
    {
      "menu": "레몬에이드",
      "temperature": "ICE",
      "quantity": 1,
      "missing_slots": []
    }
  ]
}
```

### 3.2 짧은 슬롯 답변

직전 질문의 메뉴를 데이터에 복사하지 않는다.

```json
{
  "text": "아이스로요",
  "intent": "ORDER",
  "order_status": "INCOMPLETE",
  "items": [
    {
      "menu": null,
      "temperature": "ICE",
      "quantity": null
    }
  ]
}
```

```json
{
  "text": "두 잔이요",
  "intent": "ORDER",
  "order_status": "INCOMPLETE",
  "items": [
    {
      "menu": null,
      "temperature": null,
      "quantity": 2
    }
  ]
}
```

---

## 4. 복합 주문

### 4.1 메뉴별 정보가 명확한 경우

```text
아메리카노는 뜨겁게 한 잔, 라떼는 아이스로 두 잔 주세요
```

```json
{
  "items": [
    {"item_id": 0, "menu": "아메리카노", "temperature": "HOT", "quantity": 1},
    {"item_id": 1, "menu": "카페라떼", "temperature": "ICE", "quantity": 2}
  ]
}
```

### 4.2 공통 표현

`하나씩`, `둘 다`, `전부`, `각각`처럼 적용 범위가 명확하면 모든 관련 Item에 반영한다.

```text
아메리카노랑 라떼 둘 다 아이스로 하나씩 주세요
```

```json
{
  "items": [
    {"item_id": 0, "menu": "아메리카노", "temperature": "ICE", "quantity": 1},
    {"item_id": 1, "menu": "카페라떼", "temperature": "ICE", "quantity": 1}
  ]
}
```

### 4.3 연결 범위가 불명확한 경우

```text
아메리카노랑 라떼 아이스로 한 잔 주세요
```

이 문장은 수량 1이 각 메뉴에 적용되는지, 전체 한 잔을 뜻하는지 애매할 수 있다. 임의로 라벨링하지 말고 `review_required=true`로 표시한다.

---

## 5. 자연스러운 문장 품질 기준

다음과 같은 문장은 데이터에서 제외하거나 자연스럽게 다시 작성한다.

```text
저 천천히 네 수량 맞아요
가능하면 전체 취소 주세요
저 한번 지금은 모르겠어요
```

허용 가능한 군더더기는 실제 발화에서 자연스럽게 쓰이는 범위로 제한한다.

```text
어, 음, 저기요, 아 저, 그럼, 잠시만요
```

군더더기를 넣더라도 핵심 의미와 라벨을 바꾸면 안 된다.

| 원문 | 허용 변형 |
|---|---|
| `아메리카노 하나 주세요` | `어, 아메리카노 하나 주세요` |
| `라떼 두 잔이요` | `저기요, 라떼 두 잔이요` |

---

## 6. 검수 보류 기준

다음 중 하나라도 해당하면 자동 확정하지 않고 `review_required=true`로 둔다.

- 한 문장에 HOT과 ICE 표현이 같은 Item에 동시에 등장
- 복합 주문에서 온도·수량의 적용 범위가 불명확
- `말고`, `취소`, `추가`가 함께 있어 Intent 경계가 애매함
- 지원 메뉴인지 단순 문의인지 구분하기 어려움
- 문장이 비문이라 의미를 안정적으로 해석할 수 없음
- 작성자와 검수자의 판단이 다름

검수 메모에는 보류 이유를 간단히 기록한다.

```json
{
  "review_required": true,
  "review_note": "수량 1이 각 메뉴에 적용되는지 전체 주문에 적용되는지 불명확"
}
```

---

## 7. 작성·검수 절차

1. 작성자가 자연스러운 발화를 작성한다.
2. 라벨러가 이 문서에 따라 Intent와 슬롯을 입력한다.
3. 규칙 기반 감사 스크립트로 문장-라벨 불일치를 검사한다.
4. 다른 팀원이 교차 검수한다.
5. 판단이 다른 문장은 팀 회의에서 기준을 확정하고 이 문서에 사례를 추가한다.
6. `valid_gold`, `test_gold`는 전수 검수하며 자동 생성 문장을 사용하지 않는다.

작성자와 최종 검수자는 동일인이 아니어야 한다.

---

## 8. 권장 데이터 필드

```json
{
  "id": "gold-000001",
  "text": "바닐라라떼 하나 주세요",
  "intent": "ORDER",
  "inquiry_type": "NONE",
  "order_status": "INCOMPLETE",
  "items": [
    {
      "item_id": 0,
      "menu": "바닐라라떼",
      "temperature": null,
      "quantity": 1,
      "missing_slots": ["temperature"]
    }
  ],
  "author": "",
  "reviewer": "",
  "review_status": "PENDING",
  "review_required": false,
  "review_note": ""
}
```

`review_status` 권장 값:

```text
PENDING / APPROVED / NEEDS_FIX / HOLD
```

---

## 9. 라벨링 시작 전 시험

본격 작업 전에 100개를 세 팀원이 일부 중복 라벨링한다.

- 단일 주문 30개
- 누락 슬롯 20개
- 복합 주문 20개
- AFFIRM/DENY 10개
- MODIFY/CANCEL 10개
- INQUIRY/UNKNOWN 10개

판단이 갈린 사례를 먼저 정리한 뒤 대규모 라벨링을 시작한다.
