# 주문 형식 오류 처리 설계

## 결론

메뉴 주문 형식이 잘못된 경우를 새로운 intent로 분리하지 않는다.

예를 들어 다음 문장들은 사용자의 의도 자체는 여전히 `ORDER`이다.

- `아메리카노 주세요`
- `아이스 따뜻한 아메리카노 주세요`
- `두 잔 주세요`
- `아메리카노 0잔 주세요`
- `레몬에이드 따뜻하게 주세요`

따라서 의미 분류 결과는 `ORDER`로 유지하고, 주문 구조의 유효성을 별도 필드로 관리한다.

---

## 1. 권장 출력 구조

```json
{
  "intent": "ORDER",
  "order_status": "INVALID",
  "items": [
    {
      "item_id": 0,
      "menu": "아메리카노",
      "quantity": null,
      "temperature": null,
      "missing_slots": ["quantity", "temperature"],
      "validation_errors": []
    }
  ],
  "validation_errors": [],
  "waiting_for": {
    "item_id": 0,
    "slot": "quantity"
  },
  "robot_response": "아메리카노 몇 잔 주문하시겠어요?"
}
```

---

## 2. order_status 정의

| 값 | 의미 |
|---|---|
| `VALID` | 모든 필수 슬롯이 있고 값 충돌이 없음 |
| `INCOMPLETE` | 주문 의도는 맞지만 필수 슬롯이 비어 있음 |
| `CONFLICT` | 서로 충돌하는 값이 동시에 존재함 |
| `OUT_OF_POLICY` | 메뉴판 또는 운영 규칙에 맞지 않음 |
| `UNPARSABLE` | ORDER로 보이지만 주문 항목을 구성할 수 없음 |

`INVALID` 하나로만 처리하지 않고 위 상태를 구분하는 것이 후속 질문 생성에 유리하다.

---

## 3. validation_errors 코드

| 코드 | 조건 | 예시 응답 |
|---|---|---|
| `MISSING_MENU` | 메뉴가 없음 | `어떤 메뉴를 주문하시겠어요?` |
| `MISSING_QUANTITY` | 수량이 없음 | `아메리카노 몇 잔 주문하시겠어요?` |
| `MISSING_TEMPERATURE` | 온도 필수 메뉴인데 온도가 없음 | `아이스로 드릴까요, 따뜻하게 드릴까요?` |
| `CONFLICTING_TEMPERATURE` | ICE와 HOT이 동시에 검출됨 | `아이스와 따뜻한 음료 중 하나를 선택해주세요.` |
| `INVALID_QUANTITY` | 수량이 0 이하이거나 허용 범위를 초과함 | `수량을 1잔 이상으로 말씀해주세요.` |
| `UNKNOWN_MENU` | 메뉴판에 없는 메뉴 | `해당 메뉴를 찾지 못했습니다.` |
| `TEMPERATURE_NOT_ALLOWED` | 온도 고정 메뉴에 허용되지 않는 온도 요청 | `레몬에이드는 차갑게만 제공됩니다.` |
| `AMBIGUOUS_ITEM_LINK` | 수량 또는 온도를 어느 메뉴에 연결할지 불명확함 | `어느 메뉴를 두 잔으로 주문하시겠어요?` |
| `TOO_MANY_ITEMS` | 최대 주문 항목 수 초과 | `한 번에 최대 5개 메뉴까지 주문할 수 있습니다.` |

---

## 4. intent와 주문 유효성 분리 이유

### intent가 담당하는 것

사용자가 무엇을 하려는지 분류한다.

- `ORDER`
- `MODIFY`
- `CANCEL`
- `PAYMENT`
- `GUIDE`
- `AFFIRM`
- `DENY`
- `UNKNOWN`

### validation이 담당하는 것

ORDER 결과가 실제 주문으로 확정 가능한지 판단한다.

이 둘을 섞으면 다음 문제가 생긴다.

1. `ORDER` 데이터가 `INVALID_ORDER`와 분리되어 학습 데이터가 줄어든다.
2. 빈 슬롯 주문과 완전 주문이 서로 다른 intent가 되어 대화 상태 관리가 복잡해진다.
3. 잘못된 주문 유형이 늘어날 때마다 intent 클래스가 계속 증가한다.
4. `아메리카노 주세요`처럼 자연스러운 불완전 주문까지 오류 intent로 처리할 위험이 있다.

---

## 5. 판단 예시

### 완전한 주문

입력:

```text
아이스 아메리카노 두 잔 주세요
```

출력:

```json
{
  "intent": "ORDER",
  "order_status": "VALID",
  "items": [
    {
      "menu": "아메리카노",
      "quantity": 2,
      "temperature": "ICE",
      "missing_slots": [],
      "validation_errors": []
    }
  ]
}
```

### 불완전 주문

입력:

```text
아메리카노 주세요
```

출력:

```json
{
  "intent": "ORDER",
  "order_status": "INCOMPLETE",
  "items": [
    {
      "menu": "아메리카노",
      "quantity": null,
      "temperature": null,
      "missing_slots": ["quantity", "temperature"],
      "validation_errors": ["MISSING_QUANTITY", "MISSING_TEMPERATURE"]
    }
  ]
}
```

### 온도 충돌

입력:

```text
아이스 따뜻한 아메리카노 한 잔 주세요
```

출력:

```json
{
  "intent": "ORDER",
  "order_status": "CONFLICT",
  "items": [
    {
      "menu": "아메리카노",
      "quantity": 1,
      "temperature": null,
      "missing_slots": [],
      "validation_errors": ["CONFLICTING_TEMPERATURE"]
    }
  ],
  "robot_response": "아이스와 따뜻한 음료 중 하나를 선택해주세요."
}
```

### 메뉴 누락

입력:

```text
두 잔 주세요
```

출력:

```json
{
  "intent": "ORDER",
  "order_status": "INCOMPLETE",
  "items": [
    {
      "menu": null,
      "quantity": 2,
      "temperature": null,
      "missing_slots": ["menu", "temperature"],
      "validation_errors": ["MISSING_MENU"]
    }
  ],
  "robot_response": "어떤 메뉴를 두 잔 주문하시겠어요?"
}
```

### 운영 규칙 위반

입력:

```text
따뜻한 레몬에이드 한 잔 주세요
```

출력:

```json
{
  "intent": "ORDER",
  "order_status": "OUT_OF_POLICY",
  "items": [
    {
      "menu": "레몬에이드",
      "quantity": 1,
      "temperature": "HOT",
      "missing_slots": [],
      "validation_errors": ["TEMPERATURE_NOT_ALLOWED"]
    }
  ],
  "robot_response": "레몬에이드는 차갑게만 제공됩니다. 차갑게 주문하시겠어요?"
}
```

---

## 6. 구조 B 데이터에 추가할 필드

기존 구조 B에 다음 필드를 추가한다.

```json
{
  "text": "아메리카노 주세요",
  "intent": "ORDER",
  "order_status": "INCOMPLETE",
  "items": [
    {
      "item_id": 0,
      "menu": "아메리카노",
      "quantity": null,
      "temperature": null,
      "missing_slots": ["quantity", "temperature"],
      "validation_errors": ["MISSING_QUANTITY", "MISSING_TEMPERATURE"]
    }
  ],
  "validation_errors": [],
  "source": {
    "split": "train",
    "row": 2
  }
}
```

ORDER가 아닌 문장은 `order_status = null`, `items = []`로 저장한다.

---

## 7. 모델 설계 원칙

새 모델은 다음처럼 역할을 분리한다.

```text
ko-ELECTRA
├── intent head
├── entity extraction head
└── relation/grouping head
        ↓
rule-based validator
        ↓
order_status + validation_errors
```

`order_status`와 `validation_errors`는 처음부터 별도 신경망으로 학습하기보다, 추출 결과에 규칙을 적용해 계산하는 것이 현실적이다.

새 intent를 추가하는 것은 다음 경우에만 검토한다.

- 주문 의도가 아니라 사용자가 시스템 사용법을 묻는 별도의 발화 유형이 발견됨
- 기존 intent로 의미를 설명할 수 없는 발화가 충분히 많이 수집됨
- 해당 클래스를 독립적으로 학습할 만큼 데이터가 확보됨

단순히 주문 슬롯이 비었거나 형식이 잘못된 경우에는 새 intent를 추가하지 않는다.
