# Jetson–Expo 주문 연동 운영 매뉴얼

이 문서는 Pumpkin 프로젝트에서 다음 흐름을 다시 실행하고 확인하기 위한 매뉴얼이다.

```text
Expo 고객 앱
    ↓ POST /api/v1/orders
Jetson FastAPI 주문 서버
    ↓
SQLite 주문 저장소
    ↓ GET /api/v1/orders
관리자 POS 또는 테스트 도구
```

현재 확인된 기능은 다음과 같다.

- Expo 앱에서 사전 주문 생성
- Jetson FastAPI에서 주문 수신
- `data/orders.sqlite3`에 주문 저장
- 주문에 `source=APP`, `status=RECEIVED` 기록
- 동일한 API에 향후 로봇 주문을 `source=ROBOT`으로 저장 가능
- POS는 주문 API를 조회하고 상태만 변경하도록 설계

> 현재 Expo 앱의 주문 생성은 서버와 연결되어 있다. 다만 앱의 **주문 내역 화면은 아직 서버의 주문 목록을 조회하지 않고 로컬 상태를 사용하므로 비어 보일 수 있다.**

---

## 1. 주요 경로

```text
pumpkin/
├── api/
│   ├── main.py
│   ├── routers/orders.py
│   ├── schemas/order.py
│   ├── services/order_service.py
│   └── repositories/sqlite_order_repository.py
│
├── apps/customer-mobile/
│   ├── App.tsx
│   └── src/api/orderApi.ts
│
├── data/
│   └── orders.sqlite3          # Jetson 로컬에서 자동 생성
│
└── docs/
    └── jetson_expo_order_manual.md
```

`data/orders.sqlite3`는 실행 중 생성되는 로컬 데이터베이스다. GitHub에 올리지 않는다.

---

## 2. 네트워크 구성

권장 구성은 다음과 같다.

```text
Mac/노트북: Expo 개발 서버 실행
휴대폰: Expo Go 실행
Jetson: FastAPI 주문 서버 실행
```

세 장치를 같은 Wi-Fi 또는 같은 휴대폰 핫스팟에 연결한다.

공용 Wi-Fi는 장치 간 통신을 차단할 수 있다. 휴대폰에서 Jetson 주소가 열리지 않으면 개인 핫스팟이나 공유기를 사용한다.

---

## 3. Jetson IP 확인

Jetson에서 실행한다.

```bash
hostname -I
```

예시:

```text
10.240.33.54 172.17.0.1
```

현재 프로젝트에서 사용한 Jetson LAN IP는 다음과 같다.

```text
10.240.33.54
```

`172.17.0.1`은 일반적으로 Docker 가상 네트워크 주소이므로 휴대폰 Expo 앱에서 사용하지 않는다.

네트워크가 바뀌면 Jetson IP도 바뀔 수 있으므로 실험 전마다 `hostname -I`로 다시 확인한다.

---

## 4. Jetson 저장소 최신화

Jetson 터미널에서 실행한다.

```bash
cd ~/pumpkin

git checkout main
git pull --ff-only origin main
```

현재 브랜치 확인:

```bash
git branch --show-current
```

정상 결과:

```text
main
```

변경 상태 확인:

```bash
git status
```

---

## 5. Python 가상환경과 패키지 준비

최초 한 번만 가상환경을 만든다.

```bash
cd ~/pumpkin
python3 -m venv .venv
```

가상환경 활성화:

```bash
source .venv/bin/activate
```

필요 패키지 설치:

```bash
pip install -r api/requirements.txt
```

터미널 앞에 `(.venv)`가 표시되면 활성화된 상태다.

---

## 6. Jetson 주문 API 실행

먼저 8000번 포트가 사용 중인지 확인한다.

```bash
sudo ss -ltnp | grep :8000
```

아무 결과도 없으면 비어 있는 상태다.

기존 서버를 종료해야 한다면:

```bash
sudo fuser -k 8000/tcp
```

서버 실행:

```bash
cd ~/pumpkin
source .venv/bin/activate

uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000
```

정상 메시지:

```text
Uvicorn running on http://0.0.0.0:8000
Application startup complete.
```

실험 중에는 서버 로그를 보기 위해 이 터미널을 열어 둔다.

---

## 7. 서버가 최신 코드인지 확인

새 터미널을 하나 열고 다음 명령을 실행한다.

```bash
curl -s http://127.0.0.1:8000/openapi.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['title']); print(*d['paths'].keys(), sep='\n')"
```

다음 항목이 보여야 한다.

```text
Pumpkin Physical AI API
/api/v1/orders
/api/v1/orders/{order_id}
/api/v1/orders/{order_id}/status
```

다른 제목이 나오거나 주문 API가 없으면 예전 서버가 실행 중일 가능성이 있다.

이 경우:

```bash
sudo fuser -k 8000/tcp
cd ~/pumpkin
git checkout main
git pull --ff-only origin main
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## 8. 브라우저에서 API 확인

### Jetson 자체에서

```text
http://127.0.0.1:8000/docs
```

### 휴대폰에서

```text
http://10.240.33.54:8000/docs
```

휴대폰에 Swagger 화면과 다음 API가 보이면 네트워크 연결이 성공한 것이다.

```text
POST  /api/v1/orders
GET   /api/v1/orders
GET   /api/v1/orders/{order_id}
PATCH /api/v1/orders/{order_id}/status
```

다음 주소는 404가 나와도 정상이다.

```text
http://10.240.33.54:8000/
```

현재 `/` 홈페이지 경로를 만들지 않았기 때문에 다음 응답이 나올 수 있다.

```json
{"detail":"Not Found"}
```

주문 API 오류가 아니다.

---

## 9. Jetson에서 API 단독 테스트

### 주문 목록 조회

```bash
curl -s http://127.0.0.1:8000/api/v1/orders \
  | python3 -m json.tool
```

처음이면 다음처럼 표시될 수 있다.

```json
[]
```

### 테스트 주문 생성

```bash
curl -X POST http://127.0.0.1:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: manual-test-001" \
  -d '{
    "schema_version": "1.0",
    "request_id": "manual-test-001",
    "source": "APP",
    "customer_id": null,
    "items": [
      {
        "menu_id": "americano",
        "menu_name": "아메리카노",
        "temperature": "ICE",
        "size": "NONE",
        "quantity": 1,
        "options": [],
        "unit_price": 4500
      }
    ],
    "original_text": null,
    "metadata": {
      "pickup_store": "EWHA_01"
    }
  }'
```

정상 응답에는 다음 값이 포함된다.

```text
order_id
order_number
source: APP
status: RECEIVED
total_price: 4500
```

동일한 `request_id`와 `Idempotency-Key`로 다시 요청하면 새 주문을 중복 생성하지 않고 기존 주문을 반환한다.

---

## 10. Expo 앱 환경변수 설정

Expo를 실행하는 Mac 또는 노트북에서 진행한다.

```bash
cd /Users/ysjy/Documents/Github/pumpkin

git checkout main
git pull --ff-only origin main

cd apps/customer-mobile
```

`.env` 파일을 만든다.

```bash
cat > .env <<'EOF'
EXPO_PUBLIC_API_BASE_URL=http://10.240.33.54:8000
EOF
```

Jetson IP가 바뀌었으면 해당 주소도 바꾼다.

휴대폰 앱에서 다음 주소를 사용하면 안 된다.

```text
http://localhost:8000
http://127.0.0.1:8000
```

휴대폰에서 `localhost`는 Jetson이 아니라 휴대폰 자신을 의미한다.

---

## 11. Expo 앱 실행

패키지 설치:

```bash
cd /Users/ysjy/Documents/Github/pumpkin/apps/customer-mobile
npm install
```

Expo 캐시를 삭제하고 실행:

```bash
npx expo start -c
```

휴대폰에서 Expo Go를 열고 QR 코드를 스캔한다.

환경변수를 변경했으면 Expo를 반드시 `-c` 옵션으로 다시 시작한다.

---

## 12. Expo 앱 주문 전송 테스트

앱에서 다음 순서로 진행한다.

```text
오더
→ 메뉴 선택
→ ICE 또는 HOT 선택
→ 수량 선택
→ 장바구니 담기
→ 장바구니
→ 주문 접수하기
```

성공하면 서버가 발급한 주문번호를 포함한 알림이 표시된다.

예시:

```text
주문번호 ORD-20260714-001로 접수되었습니다.
```

Jetson 터미널에는 다음 요청 로그가 보여야 한다.

```text
POST /api/v1/orders 201 Created
```

---

## 13. 앱 주문이 실제 저장됐는지 확인

Jetson 새 터미널에서 실행한다.

```bash
curl -s http://127.0.0.1:8000/api/v1/orders \
  | python3 -m json.tool
```

앱 주문은 다음 값으로 구분한다.

```json
{
  "source": "APP",
  "status": "RECEIVED"
}
```

메뉴, 온도, 수량, 가격도 함께 확인한다.

```text
menu_name: 아메리카노
temperature: ICE
quantity: 1
total_price: 4500
```

이 결과가 나오면 전체 흐름이 성공한 것이다.

```text
Expo 앱
→ 휴대폰 네트워크
→ Jetson FastAPI
→ SQLite DB 저장
```

---

## 14. SQLite 주문 DB 확인

DB 경로:

```text
~/pumpkin/data/orders.sqlite3
```

파일 확인:

```bash
ls -lh ~/pumpkin/data/orders.sqlite3
```

SQLite 명령줄 도구가 설치되어 있다면:

```bash
sqlite3 ~/pumpkin/data/orders.sqlite3
```

SQLite 내부에서:

```sql
.tables
SELECT order_number, source, status, total_price, created_at FROM orders;
.quit
```

DB 파일은 실제 주문 기록이므로 삭제하거나 GitHub에 커밋하지 않는다.

---

## 15. 주문 상태 변경 테스트

먼저 주문 목록에서 `order_id`를 복사한다.

```bash
curl -s http://127.0.0.1:8000/api/v1/orders \
  | python3 -m json.tool
```

상태 변경 예시:

```bash
curl -X PATCH \
  http://127.0.0.1:8000/api/v1/orders/ORDER_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status":"PREPARING"}'
```

허용되는 상태 전이는 다음과 같다.

```text
RECEIVED → PREPARING → READY → PICKED_UP
     └──────────────→ CANCELLED
```

예를 들어 `RECEIVED`에서 바로 `READY`로 바꾸면 409 오류가 발생하는 것이 정상이다.

---

## 16. 로봇 주문이 연결될 최종 구조

향후 ROS2 로봇 주문은 다음 흐름으로 같은 API를 사용한다.

```text
STT
→ NLU
→ decision_node
→ 사용자 최종 확인
→ OrderApiClient
→ POST /api/v1/orders
→ source=ROBOT
```

앱 주문과 로봇 주문은 같은 DB와 같은 주문 규격을 사용한다.

```text
APP 주문   → source=APP
로봇 주문  → source=ROBOT
```

POS는 `GET /api/v1/orders`로 두 종류의 주문을 함께 조회한다.

---

## 17. Git pull 시 주문 DB 충돌이 발생한 경우

정상 상태에서는 `data/orders.sqlite3`가 `.gitignore`에 의해 무시된다.

다음 오류가 발생하면:

```text
error: 병합 때문에 추적하지 않는 다음 작업 폴더의 파일을 덮어씁니다:
  data/orders.sqlite3
```

DB를 먼저 백업한다.

```bash
cd ~/pumpkin
cp data/orders.sqlite3 ~/orders.sqlite3.backup
```

원격 저장소의 DB 제거 수정이 반영되어 있는지 가져온다.

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

DB가 사라졌거나 손상된 경우 백업을 복원한다.

```bash
mkdir -p ~/pumpkin/data
cp ~/orders.sqlite3.backup ~/pumpkin/data/orders.sqlite3
```

절대 주문 DB를 무조건 삭제한 뒤 pull하지 않는다.

---

## 18. 자주 발생하는 오류

### 18.1 `Address already in use`

원인:

```text
8000번 포트에서 기존 서버가 실행 중
```

해결:

```bash
sudo fuser -k 8000/tcp
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

### 18.2 휴대폰에서 `/docs`가 열리지 않음

확인 순서:

```bash
hostname -I
sudo ss -ltnp | grep :8000
```

- 휴대폰과 Jetson이 같은 Wi-Fi인지 확인
- Expo `.env`가 현재 Jetson IP인지 확인
- 서버가 `--host 0.0.0.0`으로 실행됐는지 확인
- 공용 Wi-Fi라면 핫스팟으로 변경

---

### 18.3 `/`에서 `404 Not Found`

정상이다. 다음 주소를 사용한다.

```text
/docs
/api/v1/orders
/health
```

---

### 18.4 Swagger에는 API가 보이는데 실행하면 404

예전 서버와 새 서버가 동시에 실행 중이거나 브라우저 캐시가 남아 있을 수 있다.

```bash
sudo fuser -k 8000/tcp
cd ~/pumpkin
git checkout main
git pull --ff-only origin main
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

휴대폰 브라우저를 새로고침한다.

---

### 18.5 Expo 주문 실패

우선 휴대폰 브라우저에서 다음 주소가 열리는지 확인한다.

```text
http://JETSON_IP:8000/docs
```

그다음 `.env` 확인:

```bash
cat apps/customer-mobile/.env
```

Expo 재시작:

```bash
npx expo start -c
```

---

### 18.6 주문은 저장됐는데 앱 주문 내역이 비어 있음

현재 알려진 상태다.

```text
주문 생성 → 서버 저장 완료
주문 내역 화면 → 아직 로컬 orders 배열 사용
```

Jetson에서 다음 명령으로 실제 저장 여부를 확인한다.

```bash
curl -s http://127.0.0.1:8000/api/v1/orders \
  | python3 -m json.tool
```

후속 작업에서 앱 주문 내역 화면을 `GET /api/v1/orders`에 연결한다.

---

## 19. 서버 종료

서버가 실행 중인 터미널에서:

```text
Ctrl + C
```

강제 종료:

```bash
sudo fuser -k 8000/tcp
```

---

## 20. 매 실험 전 체크리스트

```text
[ ] Jetson, 휴대폰, Expo PC가 같은 네트워크인가?
[ ] Jetson IP를 hostname -I로 확인했는가?
[ ] Jetson main 브랜치를 pull했는가?
[ ] Python 가상환경을 활성화했는가?
[ ] 8000번 포트에 중복 서버가 없는가?
[ ] FastAPI를 0.0.0.0:8000으로 실행했는가?
[ ] 휴대폰에서 http://JETSON_IP:8000/docs가 열리는가?
[ ] Expo .env에 현재 Jetson IP가 들어 있는가?
[ ] Expo를 npx expo start -c로 실행했는가?
[ ] 앱 주문 후 Jetson GET /api/v1/orders에서 source=APP을 확인했는가?
```

---

## 21. 가장 짧은 실행 요약

### Jetson

```bash
cd ~/pumpkin
git checkout main
git pull --ff-only origin main
source .venv/bin/activate
sudo fuser -k 8000/tcp 2>/dev/null || true
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Expo PC

```bash
cd /Users/ysjy/Documents/Github/pumpkin
git checkout main
git pull --ff-only origin main
cd apps/customer-mobile
printf 'EXPO_PUBLIC_API_BASE_URL=http://10.240.33.54:8000\n' > .env
npx expo start -c
```

### 주문 저장 확인

```bash
curl -s http://127.0.0.1:8000/api/v1/orders \
  | python3 -m json.tool
```
