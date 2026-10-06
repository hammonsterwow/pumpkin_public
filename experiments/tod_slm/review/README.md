# Pumpkin TOD 검수 웹

규칙으로 생성한 TOD 데이터를 표본 검수하기 위한 로컬 웹이다. Python 3 표준 라이브러리만 사용하며, 원본 학습 JSONL은 수정하지 않는다.

## 실행

저장소 루트에서:

```bash
python experiments/tod_slm/review/app.py
```

기본 주소:

```text
http://127.0.0.1:8765
```

브라우저가 자동으로 열리지 않으면 위 주소를 직접 연다. 종료는 `Ctrl+C`다.

## 현재 기본 검수 세트

편의 스크립트는 다음 combined 파일을 연다.

```text
data/tod/pumpkin_tod_v1_review_sample.jsonl
```

총 400개다.

```text
MULTITURN  200
BASE DATA  200
-----------
합계       400
```

### MULTITURN 200

문맥이 필요했던 source scenario에서 각 40개씩 검수한다.

```text
AFFIRM              40
DENY                40
MODIFY              40
CANCEL              40
CONTEXTUAL ORDER    40
----------------------
합계               200
```

### BASE DATA 200

`data/tod/pumpkin_tod_v1_train_valid.jsonl`의 fully-supervised **19,332개**에서 층화 표본을 뽑는다.

```text
BASE DATA · 단일 주문 완료       40
BASE DATA · 단일 수량 질문       25
BASE DATA · 단일 온도 질문       20
BASE DATA · 다중 주문 완료       35
BASE DATA · 다중 수량 질문       25
BASE DATA · 다중 온도 질문       25
BASE DATA · 안내                 15
BASE DATA · UNKNOWN              15
-----------------------------------
합계                            200
```

각 bucket의 앞부분만 가져오지 않고 전체 구간에 걸쳐 deterministic midpoint systematic sampling으로 고르게 선택한다.

고정 test는 사람 검수 표본 생성에 사용하지 않는다. 검수 결과를 보고 생성 규칙을 수정하는 과정에서 test 정보를 미리 반영하지 않기 위해서다. 현재 train/valid에는 `order_missing_menu`가 없으므로 이 유형은 BASE DATA 수동 표본에 넣지 않고 generator 자동 검증으로만 유지한다.

## 기존 MULTITURN 200개를 이미 검수한 경우

기존 결과 파일을 지우지 않는다.

```text
data/tod/pumpkin_tod_v1_review_results.jsonl
```

MULTITURN 표본의 ID는 그대로 유지된다. 새 combined 400개를 열면 기존 200개 판정이 자동으로 복원되고, 기본 `미검수만` 화면에는 새 **BASE DATA 200개**가 남는다.

## 화면에서 확인할 것

한 샘플에 다음 정보가 표시된다.

```text
① 이전 주문 상태
② 로봇이 직전에 한 말
③ 사용자가 한 말
④ 적용 후 주문 상태
⑤ FSM 상태 변화
⑥ 이번 턴의 시스템 동작 / response_key
⑦ 로봇 응답
```

BASE DATA는 독립적인 초기 주문 발화이므로 보통:

```text
state_before = 주문 없음
fsm_state_before = ORDER_LISTEN
history = 없음
```

에서 시작한다.

## 키보드 검수

```text
1  정상
2  문맥 오류
3  이전 상태 오류
4  이후 상태 오류
5  판단 오류
6  응답 오류
7  기타 오류

←  이전
→  다음
```

숫자 키로 판정하면 즉시 결과 파일에 저장되고 다음 미검수 샘플로 이동한다.

## 결과 파일

```text
data/tod/pumpkin_tod_v1_review_results.jsonl
```

웹을 종료하고 다시 실행해도 기존 결과를 읽어서 이어서 검수할 수 있다.

오류가 발견되면 개별 JSON 한 줄을 직접 고치지 않는다. 오류 유형과 메모만 저장한 뒤 생성 규칙을 수정하고 전체 데이터를 다시 생성한다.

## 데이터 생성

combined 검수 표본은 다음 스크립트가 만든다.

```bash
python3 experiments/tod_slm/data_generation/build_review_samples.py
```

출력:

```text
data/tod/pumpkin_tod_v1_base_review_sample.jsonl
data/tod/pumpkin_tod_v1_review_sample.jsonl
data/tod/pumpkin_tod_v1_review_stats.json
```

GitHub Actions는 BASE DATA 200개, MULTITURN 200개, combined 400개, 중복 ID 없음, test 수동검수 미사용, 로컬 review server health check까지 자동 검증한다.
