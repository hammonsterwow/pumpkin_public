# 테이블 정의서

> 2026 한이음 드림업 프로그램 설계서의 **테이블 정의서** 항목에 사용할 수 있도록 현재 `main` 브랜치의 실제 저장 구조를 기준으로 정리한 문서이다.
>
> 현재 주문/고객 데이터는 SQLite, 얼굴 임베딩은 Firebase Firestore, 메뉴 기준정보는 `config/menu_catalog.json`을 사용한다. 따라서 구현되지 않은 관계형 테이블을 임의로 추가하지 않고, **실제 구현 기준**과 **비관계형 저장소**를 구분하여 작성한다.

---

## 1. `orders` table

**저장소:** SQLite (`data/orders.sqlite3`)  
**설명:** 고객 앱, 로봇, POS에서 생성된 주문의 기본 정보를 저장한다.

| 항목명 | Type | 필수/선택 | 키 목록 | 활성여부 | 설명 |
|---|---|---|---|---|---|
| `id` | TEXT | 필수 | PK | 활성 | 주문 내부 고유 ID(UUID) |
| `order_number` | TEXT | 필수 | UNIQUE | 활성 | 사용자/관리자에게 표시하는 주문번호. `ORD-YYYYMMDD-###` 형식 |
| `request_id` | TEXT | 필수 | UNIQUE | 활성 | 동일 주문 요청의 중복 생성을 방지하기 위한 요청 식별자 |
| `source` | TEXT | 필수 |  | 활성 | 주문 생성 경로. `APP`, `ROBOT`, `POS` |
| `customer_id` | TEXT | 선택 |  | 활성 | 주문 고객 식별자. 비회원 또는 현장 주문은 NULL 가능 |
| `status` | TEXT | 필수 |  | 활성 | 주문 상태. `RECEIVED`, `PREPARING`, `READY`, `PICKED_UP`, `CANCELLED` |
| `original_text` | TEXT | 선택 |  | 활성 | 로봇 음성 주문일 경우 STT로 변환된 원본 주문 문장 |
| `metadata_json` | TEXT | 필수 |  | 활성 | 주문 요청에 포함된 추가 메타데이터를 JSON 문자열로 저장 |
| `total_price` | INTEGER | 필수 |  | 활성 | 주문 전체 금액 |
| `created_at` | TEXT | 필수 |  | 활성 | 주문 생성 시각(UTC ISO 8601) |
| `updated_at` | TEXT | 필수 |  | 활성 | 주문 상태 또는 정보 최종 수정 시각(UTC ISO 8601) |

### 비고

- `request_id`는 앱/로봇이 같은 요청을 재전송하더라도 주문이 중복 생성되지 않도록 사용한다.
- `customer_id`는 현재 `customers.sqlite3`와 별도 SQLite 파일에 저장되므로 DB 수준 FK 제약은 걸려 있지 않다.

---

## 2. `order_items` table

**저장소:** SQLite (`data/orders.sqlite3`)  
**설명:** 하나의 주문에 포함된 메뉴별 상세 주문 항목을 저장한다. 한 주문에 여러 메뉴를 포함할 수 있도록 `orders`와 1:N 관계로 구성한다.

| 항목명 | Type | 필수/선택 | 키 목록 | 활성여부 | 설명 |
|---|---|---|---|---|---|
| `id` | TEXT | 필수 | PK | 활성 | 주문 항목 고유 ID(UUID) |
| `order_id` | TEXT | 필수 | FK | 활성 | 연결된 주문 ID. `orders.id` 참조 |
| `menu_id` | TEXT | 필수 |  | 활성 | 공통 메뉴 카탈로그의 공식 `menu_id` |
| `menu_name` | TEXT | 필수 |  | 활성 | 주문 시점의 메뉴명 |
| `temperature` | TEXT | 필수 |  | 활성 | 온도 옵션. `HOT`, `ICE`, `NONE` |
| `size` | TEXT | 필수 |  | 활성 | 사이즈 값. 현재 주문 API는 `SMALL`, `MEDIUM`, `LARGE`, `NONE` 형식을 지원하며 실제 카페 메뉴 정책에서는 기본적으로 `NONE` 사용 |
| `quantity` | INTEGER | 필수 |  | 활성 | 주문 수량 |
| `options_json` | TEXT | 필수 |  | 활성 | 추가 옵션 목록을 JSON 문자열로 저장 |
| `unit_price` | INTEGER | 필수 |  | 활성 | 메뉴 1개 기준 단가 |

### 관계

```text
orders (1) ────────< order_items (N)
     id                 order_id
```

- `order_items.order_id`는 `orders.id`를 참조한다.
- 주문 삭제 시 해당 주문의 상세 항목도 `ON DELETE CASCADE`로 함께 삭제된다.

---

## 3. `customers` table

**저장소:** SQLite (`data/customers.sqlite3`)  
**설명:** 등록 고객의 기본 정보와 단골 맞춤 응대에 필요한 선호 메뉴, 방문 횟수, 얼굴 등록 상태를 저장한다.

| 항목명 | Type | 필수/선택 | 키 목록 | 활성여부 | 설명 |
|---|---|---|---|---|---|
| `customer_id` | TEXT | 필수 | PK | 활성 | 고객 고유 식별자 |
| `name` | TEXT | 필수 |  | 활성 | 고객 이름 |
| `preferred_menu` | TEXT | 필수 |  | 활성 | 고객 선호 메뉴. 미등록 시 빈 문자열 |
| `preferred_temperature` | TEXT | 필수 |  | 활성 | 선호 온도. 기본값 `NONE` |
| `preferred_quantity` | INTEGER | 필수 |  | 활성 | 선호 주문 수량. 기본값 1 |
| `visit_count` | INTEGER | 필수 |  | 활성 | 등록 고객 방문 횟수. 기본값 0 |
| `face_registered` | INTEGER | 필수 |  | 활성 | 얼굴 임베딩 등록 여부. SQLite에서 `0/1`로 저장 |
| `created_at` | TEXT | 필수 |  | 활성 | 고객 정보 최초 생성 시각(UTC ISO 8601) |
| `updated_at` | TEXT | 필수 |  | 활성 | 고객 정보 최종 수정 시각(UTC ISO 8601) |

### 비고

- `face_registered`는 얼굴 사진 촬영 완료 자체가 아니라 최종 얼굴 임베딩을 사용할 수 있는 상태인지 나타내는 플래그로 사용한다.
- 고객 기본 정보와 얼굴 특징 벡터를 한 SQLite 테이블에 직접 함께 저장하지 않고 역할을 분리한다.

---

## 4. Firebase Firestore `users` collection — 얼굴 임베딩 관련 필드

**저장소:** Firebase Firestore  
**설명:** 고객 앱의 Firebase 인증 UID를 기준으로 얼굴 등록 상태와 최종 얼굴 임베딩을 저장한다. 아래는 현재 Jetson의 Firebase 얼굴 임베딩 생성 API가 직접 기록하는 필드만 정리한 것이다.

| 항목명 | Type | 필수/선택 | 키 목록 | 활성여부 | 설명 |
|---|---|---|---|---|---|
| `uid` | STRING | 필수 | Document ID | 활성 | Firebase Authentication 사용자 UID |
| `faceRegistered` | BOOLEAN | 선택 |  | 활성 | 얼굴 임베딩 등록 완료 여부 |
| `faceEnrollmentStatus` | STRING | 선택 |  | 활성 | 얼굴 등록 상태. 등록 완료 시 `registered` |
| `faceEmbedding.model` | STRING | 선택 |  | 활성 | 얼굴 임베딩 생성에 사용한 모델명 |
| `faceEmbedding.dimension` | NUMBER | 선택 |  | 활성 | 임베딩 벡터 차원 |
| `faceEmbedding.centroid` | ARRAY<NUMBER> | 선택 |  | 활성 | 정면·좌·우·상·하 얼굴 특징 벡터를 종합한 대표 임베딩 |
| `faceEmbedding.updatedAt` | STRING | 선택 |  | 활성 | 임베딩 생성 시각(UTC ISO 8601 문자열) |
| `updatedAt` | STRING | 선택 |  | 활성 | 사용자 얼굴 등록 정보 최종 수정 시각 |

### 비고

- 임베딩 생성 시 `users/{uid}` 문서에 `merge=True` 방식으로 얼굴 관련 필드를 추가/갱신한다.
- 얼굴 등록에 사용한 임시 사진은 Firebase Storage의 `face-enrollment-temp/{uid}/` 아래에 저장한 뒤 임베딩 생성 후 삭제하도록 구현되어 있다.

---

# 테이블이 아닌 공통 데이터 저장 구조

## 5. `config/menu_catalog.json` — 메뉴 Single Source of Truth

현재 메뉴 정보는 별도의 `menu` DB 테이블이 아니라 `config/menu_catalog.json`을 **서비스 메뉴 기준 원본(Single Source of Truth)** 으로 사용한다.

| 항목명 | Type | 설명 |
|---|---|---|
| `menu_id` | INTEGER | 메뉴 고유 ID. 현재 1~5 |
| `name` | STRING | 한글 메뉴명 |
| `eng_name` | STRING | 영문 메뉴명 |
| `aliases` | ARRAY<STRING> | STT/NLU 및 서비스 매칭용 메뉴 별칭 |
| `category` | STRING | 메뉴 카테고리 (`ESPRESSO`, `BEVERAGE`) |
| `price` | INTEGER | 판매 가격 |
| `available_temperatures` | ARRAY<STRING> | 주문 가능한 온도 (`ICE`, `HOT`) |
| `is_available` | BOOLEAN | 판매 가능 여부 |
| `image` | STRING / NULL | 메뉴 이미지 경로 또는 URL |
| `description` | STRING | 메뉴 설명 |

### 현재 메뉴

| menu_id | 메뉴명 | 온도 | 가격 |
|---:|---|---|---:|
| 1 | 아메리카노 | ICE / HOT | 3,000원 |
| 2 | 카페라떼 | ICE / HOT | 4,000원 |
| 3 | 바닐라라떼 | ICE / HOT | 4,500원 |
| 4 | 레몬에이드 | ICE | 4,500원 |
| 5 | 딸기스무디 | ICE | 5,000원 |

---

# 설계서 삽입 권장 구성

한이음 제작설계서의 **테이블 정의서** 페이지에는 아래 순서로 넣는 것을 권장한다.

1. `orders` + `order_items` — **주문 데이터**
2. `customers` — **단골 고객 데이터**
3. Firebase `users` 얼굴 관련 필드 — **얼굴 인식 개인화 데이터**
4. 하단 주석으로 `menu_catalog.json`이 **메뉴 기준 원본이며 DB 테이블이 아님**을 명시

> 이전 설계 초안에 있던 `menu`, `favorite_menu`, `admin`, `robot`, `conversation_log` 등의 관계형 테이블은 현재 `main` 브랜치의 실제 DB 생성 코드에는 존재하지 않는다. 최종 설계서에서는 구현된 저장 구조와 문서가 서로 다르게 보이지 않도록 위 정의를 기준으로 정리하는 것이 적절하다.
