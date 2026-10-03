# 2026-08-10 실물 로봇 상호작용 실험 및 트러블슈팅 기록

> 2026-08-10 기준 최근 Jetson Orin Nano 실물 연속 테스트에서 확인한 로봇 대화·STT·주문 흐름 문제와 해결 과정을 정리한다. 단순 결과만 남기지 않고 **관찰 → 원인 분석 → 수정 → 검증 → 남은 문제** 순서로 기록해 이후 개발보고서, 시연 준비, 회귀 테스트에 재사용할 수 있도록 한다.

## 1. 실험 목적

실제 카메라·마이크·스피커·LCD·목 모터가 연결된 Pumpkin 로봇에서 다음 전체 흐름을 반복 시험했다.

```text
고객 감지
→ 로봇 인사/TTS
→ STT(Faster-Whisper)
→ NLU(koELECTRA Structure B)
→ Decision/FSM
→ Response Manager
→ Action
→ TTS/LCD/머리 동작
→ 다음 사용자 입력
```

주요 목표는 다음과 같다.

1. 음성 주문이 실제 환경에서 끊기거나 왜곡되지 않는지 확인
2. 짧은 후속 답변, 주문 수정, 추가 주문이 상태 머신에서 정상 처리되는지 확인
3. 안내 질문이 실제 로봇 방향 동작으로 연결되는지 확인
4. 코드에 수정이 존재하더라도 실제 실물 런처가 해당 production 모듈을 실행하는지 확인
5. 발견된 문제를 재현 가능한 테스트와 PR로 남겨 같은 오류가 다시 생기지 않도록 함

---

## 2. 테스트 실행 방법

### 터미널 1 — 전체 로봇 실행

```bash
cd ~/pumpkin
git pull
bash scripts/run_robot_interaction_logs.sh
```

### 터미널 2 — 핵심 상호작용 로그 확인

```bash
cd ~/pumpkin
bash scripts/run_robot_interaction_view.sh
```

핵심 확인 로그 예시는 다음과 같다.

```text
🗣️ 내가 한 말: ...
🧠 NLU가 직접 읽은 정보: ...
✅ Decision: ...
🤖 로봇: ...
🎭 출력 명령: ...
```

문제 위치를 찾을 때는 다음 기준을 사용한다.

- `🗣️ 내가 한 말`부터 틀림 → STT/VAD/오디오 입력 문제
- STT 문장은 맞지만 `🧠 NLU`가 틀림 → NLU/후처리 문제
- NLU까지 맞지만 주문 상태가 틀림 → Decision/FSM/주문 merge 문제
- 응답 문장은 맞지만 방향·표정·행동이 틀림 → Response/Action/하드웨어 연동 문제

---

## 3. 문제 해결 기록

## 3.1 화장실 안내가 일반 매장 안내로 끝나는 문제

### 관찰

화장실 위치를 물었을 때 응답이 실제 방향 안내로 이어지지 않고 일반적인 매장 안내 수준에서 끝나는 문제가 있었다.

### 원인

Response 단계에서 화장실 안내 의도는 존재했지만, 실제 `GUIDE_CUSTOMER` action과 좌/우 방향 정보가 충분히 연결되지 않았다.

### 해결

- 화장실 방향을 Response Manager가 명시적으로 보강
- 기본 방향은 `RIGHT`
- 환경변수 `PUMPKIN_RESTROOM_DIRECTION`으로 변경 가능
- Action 단계에서 `GUIDE_CUSTOMER`가 실제 방향 명령으로 이어지도록 연결

### 관련 변경

- PR #89
- merge commit: `fabf1c736794244888eceb2afc77e045c20fd7bb`
- commit message: `fix: connect restroom guide to direction action`

### 결과

화장실 질문이 단순 문장 응답이 아니라 로봇의 방향 안내 흐름으로 연결되도록 수정했다.

---

## 3.2 메뉴 재진술 시 이전 슬롯이 남아 주문이 잘못 유지되는 문제

### 관찰

메뉴/옵션 재질문 중 사용자가 기존 주문을 부정하고 새로운 메뉴를 다시 말해도 이전 슬롯 정보가 남아 있는 경우가 있었다.

예를 들어 사용자가 `아니라 ...`와 같이 주문을 다시 말했을 때 새 정보가 기존 값을 덮어쓰지 못할 수 있었다.

### 원인

대화 슬롯 merge가 기본적으로 기존 값을 보호하는 방향으로 동작해, 명시적 정정 발화까지 stale slot으로 취급했다.

### 해결

- `아니라` 등의 정정 cue 추가
- 현재 기다리고 있는 슬롯에 대해 사용자가 명시적으로 재진술하면 overwrite 허용
- 회귀 테스트 `test_slot_restatement_correction.py` 추가

### 관련 변경

- PR #90
- merge commit: `e65570a86ed1cafa78a0039a9b44ffa19fbd22b1`
- commit message: `fix: recover strawberry restatements during slot prompts`

### 결과

정정 의도가 분명한 경우 이전 슬롯보다 새 발화가 우선하도록 수정했다.

---

## 3.3 딸기스무디/수량 표현 등 STT prompt bias 문제

### 관찰

Whisper가 메뉴명을 안정적으로 인식하도록 initial prompt에 메뉴·수량 예시를 많이 넣었으나, 실제 실물 환경에서는 prompt가 오히려 결과를 특정 단어로 끌어가는 문제가 나타났다.

초기 대응에서는 메뉴와 수량 표현을 균형 있게 넣도록 prompt를 수정했다.

### 1차 해결

- 주문용/확인용 initial prompt 분리
- 특정 메뉴에 과도하게 치우치지 않도록 prompt 균형 조정
- `스무디스무디` 같은 비정상 반복 결과 필터링

### 관련 변경

- PR #91
- merge commit: `e62d58dd3832cea132c2c409941d5f2e0eb1d3d3`
- commit message: `fix: balance STT prompts for menu recognition`

### 후속 판단

실물 테스트에서 prompt 문구 자체가 음성 인식 결과로 누출되는 더 큰 문제가 확인되어, 이 방식은 이후 PR #94에서 production 기준으로 폐기했다.

---

## 3.4 짧은 수량/온도 후속 답변과 부분 주문 결합 문제

### 관찰

사용자가 한 번에 전체 주문을 말하지 않고 다음과 같이 나눠 말할 때 일부 슬롯이 잘못 연결될 수 있었다.

```text
한 잔이랑 바닐라라떼 15 잔
```

또한 짧은 온도 표현이 STT 오인식으로 들어왔을 때도 안전하게 보정할 필요가 있었다.

### 원인

텍스트에 명시된 수량·온도 증거와 NLU 모델 출력의 결합 규칙이 복합 주문/부분 주문에 충분히 대응하지 못했다.

### 해결

- 명시 수량을 가장 가까운 메뉴와 결합
- 앞쪽의 독립 수량은 orphan partial item으로 보존
- 매우 제한적인 HOT STT alias만 허용
- 긴 무관 문장을 HOT으로 잘못 보정하지 않도록 방어

### 관련 변경

- PR #92
- merge commit: `b83c2b0801ef20206cbfdca3e59cfc1ae65f31b5`
- commit message: `fix: recover live quantity and temperature slot recognition`

### 결과

실제 후속 답변과 부분 주문에서 NLU 모델 출력만 믿지 않고, 사용자가 실제로 말한 슬롯 증거를 함께 사용하도록 개선했다.

---

## 3.5 취소된 STT가 늦게 결과를 publish하고 다음 턴을 오염시키는 문제

### 관찰

이전 STT 턴이 취소되었는데도 늦게 transcription이 끝나면서 `네` 같은 결과가 다음 대화 턴에 들어오는 문제가 발생했다.

또한 `sounddevice` read가 멈추면 STT가 계속 대기해 전체 대화가 정지할 수 있었다.

### 원인

기존 STT는 여러 recording/transcription thread가 공용 cancel/busy 상태를 공유했다. 취소된 오래된 thread가 나중에 결과를 publish하거나 상태를 해제할 가능성이 있었다.

### 해결

`SafeSTTNode` 도입:

- STT turn별 token 부여
- turn별 cancel event 사용
- 현재 active token이 아닌 결과 publish 차단
- callback queue 기반 audio capture
- 1.5초 audio stream watchdog
- stream stall 시 `error:audio_stream_stalled`로 정상 retry 흐름 진입
- 짧은 confirmation 입력 별도 처리

NLU에서도 bare `네`가 수량 4로 해석되지 않도록 standalone confirmation grounding을 먼저 수행하도록 수정했다.

### 관련 변경

- PR #93
- merge commit: `8a2e8b7ad89c8e3042d2f06e904a712cbbfe1a10`
- commit message: `fix: prevent STT retry stalls and stale voice results`

### 결과

오래된 STT 결과가 다음 대화를 오염시키는 race condition과 마이크 stream stall에 대한 복구 장치를 추가했다.

---

## 3.6 Whisper initial prompt 문구가 실제 사용자 발화처럼 출력되는 문제

### 관찰

실제 사용자는 말하지 않았는데 다음과 같은 문장이 STT 결과로 출력되었다.

```text
두 잔을 고치면 아메리카노, 카페라떼, 딸기스무디, 레몬에이드 중 하나를 말합니다.
```

이 문장은 기존 confirmation initial prompt에 들어 있던 안내 문구와 거의 동일했다.

### 원인

production STT가 Faster-Whisper에 lexical `initial_prompt`를 직접 넘기고 있었고, 약하거나 noisy한 입력에서 Whisper가 prompt 자체를 hallucination하는 것으로 판단했다.

### 해결

`UnbiasedSTTNode` 추가:

- 모든 listen mode에서 `initial_prompt=None`
- 메뉴/수량/정정 예시를 Whisper에 주지 않음
- `language='ko'`만 유지
- 예전 prompt 문구가 결과로 누출되는 경우를 별도 필터로 차단
- SafeSTT의 turn isolation/watchdog는 그대로 상속

### 관련 변경

- PR #94
- merge commit: `69e87bd483d557c7e012357fcbfea4f3ffe9c91a`
- commit message: `fix: remove Whisper initial prompt bias`

### 결과

STT는 음성과 한국어 language 정보만으로 decoding하고, 메뉴/수량 해석은 NLU가 담당하도록 역할을 다시 분리했다.

---

## 3.7 음료 수령 위치 안내를 화장실과 반대 방향으로 분리

### 관찰

사용자가 `음료수 어디서 받아요?`라고 물었을 때 로봇이 일반 안내만 수행했다.

### 요구사항

- 화장실과 음료 수령대는 서로 다른 방향으로 안내
- 별도 방향값을 중복 관리하기보다 화장실 방향의 반대편으로 계산

### 해결

- `PickupAwareResponseManager` 추가
- pickup 관련 발화 탐지
- restroom direction이 RIGHT이면 pickup은 LEFT
- restroom direction이 LEFT이면 pickup은 RIGHT
- 음료 수령대 전용 speech/display 문구 추가
- 기존 Action의 LEFT/RIGHT guide 동작 재사용

### 관련 변경

- PR #95
- merge commit: `94350a293b554132e3199f1f3a33c22faf96ac14`
- commit message: `feat: guide drink pickup opposite restroom`

### 현재 기본값

```text
화장실: RIGHT
음료 수령대: LEFT
```

---

## 3.8 주문 확인 중 명시적으로 추가한 새 음료가 주문에 들어가지 않는 문제

### 재현 로그

```text
사용자: 아이스 아메리카노 두 잔 주세요.
로봇: 아이스 아메리카노 2잔 맞으신가요?
사용자: 딸기스무디 두 잔도 추가해주세요.
NLU: 메뉴=딸기스무디, 수량=2잔
로봇: 아이스 아메리카노 2잔 맞으신가요?
```

### 분석

STT와 NLU는 정상이었다. 문제는 Decision 단계였다.

`ORDER_CONFIRM` 상태에서는 안전을 위해 임의의 ORDER prediction을 바로 주문에 반영하지 않고 기존 확인을 반복한다. 기존 `is_additional_order_request()`는 특정 고정 문구와 정확히 일치하는 경우만 추가 주문으로 인정해 `딸기스무디 두 잔도 추가해주세요` 같은 자연스러운 문장을 놓쳤다.

### 해결

`AdditionalOrderDecisionNode` 추가:

- `추가`, 자연스러운 `더 ... 주세요` 패턴 감지
- 메뉴가 명시된 추가 주문만 안전하게 append
- 기존 주문 + incoming item을 결합한 뒤 주문 상태 재구축
- bare `추가할게요`는 phantom item을 만들지 않도록 차단
- 단순 메뉴 언급만으로는 기존 주문을 변경하지 않음

### 관련 변경

- PR #96
- merge commit: `d6264a5dfea96ce05a1acf87b03f71e8089f23c5`
- commit message: `fix: append explicit additional drinks during confirmation`

### 결과

```text
아이스 아메리카노 2잔
+ 딸기스무디 두 잔도 추가해주세요
→ 아메리카노 2잔 + 딸기스무디 2잔
```

형태의 명시적 새 메뉴 추가가 주문에 반영되도록 수정했다.

---

## 3.9 코드에는 수정이 있는데 실물 런처가 구형 모듈을 실행하는 문제

### 관찰

`setup.py` production entrypoint는 최신 STT/Decision으로 변경되어 있었지만, 실제 실물 테스트에서는 기대한 startup log와 새 동작이 보이지 않았다.

### 원인

`scripts/run_ros_voice_nodes.sh`가 console entrypoint를 사용하지 않고 다음 구형 모듈을 직접 실행하고 있었다.

```text
robot_controller.stt_node
robot_controller.decision_node_order_handoff
```

따라서 코드 저장소에 최신 수정이 존재해도 **실제 실물 테스트에는 적용되지 않는 상태**였다.

### 해결

실물 런처를 다음 production 모듈로 직접 변경했다.

```text
STT      → robot_controller.stt_node_unbiased
Decision → robot_controller.decision_node_additional_order
```

추가로 런처에 실제 runtime module 이름을 출력하도록 하고, 구형 모듈 경로가 다시 들어오면 실패하는 회귀 테스트를 추가했다.

### 관련 변경

- PR #97
- merge commit: `5ab661186acd382dbeb5e0656f9302af4c8541b9`
- commit message: `fix: launch production STT and decision modules`

### 확인해야 하는 startup log

```text
STT runtime: robot_controller.stt_node_unbiased
Decision runtime: robot_controller.decision_node_additional_order
Safe STT turn isolation enabled: stale-result guard + audio-stream watchdog
Whisper lexical initial prompts disabled; decoding uses audio + language only
```

### 의미

이번 실험에서 가장 중요한 운영 교훈 중 하나이다. **코드를 수정한 것과 실제 실물 런타임에 수정이 적용된 것은 별개이므로, startup에서 실제 module/config를 반드시 출력해야 한다.**

---

## 3.10 VAD가 너무 보수적이라 짧고 조용한 발화를 놓치는 문제

### 기존 실물 설정

```text
speech threshold = RMS 3500
speech start = 7 blocks
block = 50 ms
→ 약 350 ms 동안 RMS 3500 이상이어야 speech 시작
```

생활소음 오작동을 줄이는 데는 유리했지만, 실제 사용자가 평소 목소리로 짧게 말하는 다음 발화를 놓칠 가능성이 컸다.

```text
네
아니요
두 잔이요
아이스요
```

### 해결 방향

시작 감지만 민감하게 하고, 문장 끝을 판단하는 endpoint 조건은 유지했다.

### 변경값

| 항목 | 기존 | 변경 |
|---|---:|---:|
| speech threshold | 3500 | 2800 |
| 일반 주문 start blocks | 7 | 4 |
| 일반 주문 최소 지속 | 약 350 ms | 약 200 ms |
| confirmation start blocks | 4 | 2 |
| confirmation 최소 지속 | 약 200 ms | 약 100 ms |
| end threshold | 1800 | 유지 |
| silence duration | 0.6 s | 유지 |
| end ceiling ratio | 0.75 | 유지 |

`UnbiasedSTTNode`가 `PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS`를 읽도록 연결하여 일반 주문과 짧은 confirmation의 시작 조건을 분리했다.

### 관련 변경

- PR #98
- merge commit: `1231fd1abfb822318456f73079285059d319f2c4`
- PR title: `tune: 실물 STT VAD 시작 민감도 조정`

### startup 확인값

```text
[VAD] normal: rms>=2800.0 x 4 blocks
[VAD] confirmation: rms>=2800.0 x 2 blocks
[VAD] end: rms<1800.0, silence=0.6s
```

### 후속 평가 방법

다음 발화를 평소 목소리로 반복해 `speech_detected` 성공률과 STT 결과를 비교한다.

```text
아이스 아메리카노 두 잔 주세요.
딸기스무디 두 잔도 추가해주세요.
두 잔이요.
네.
아니요.
```

주변 소음까지 너무 쉽게 잡으면 threshold를 3000 정도로 다시 높여 A/B 테스트한다.

---

## 4. 오늘 확인한 중요한 원인 분리 기준

이번 실험에서 단순히 "음성 주문이 안 된다"고 보지 않고 파이프라인 단계별로 원인을 분리하는 것이 효과적이었다.

### STT 문제

```text
사용자 실제 발화 ≠ 🗣️ 내가 한 말
```

확인 대상:

- ReSpeaker/ALSA 입력
- VAD threshold/start blocks
- TTS acoustic tail
- Faster-Whisper
- stale STT thread
- prompt hallucination

### NLU 문제

```text
🗣️ 내가 한 말은 맞음
하지만 메뉴/온도/수량/intent가 틀림
```

확인 대상:

- koELECTRA prediction
- explicit slot grounding
- 후처리
- confidence/label policy

### Decision/FSM 문제

```text
STT와 NLU는 맞음
하지만 주문이 추가/수정되지 않음
```

확인 대상:

- 현재 dialogue state
- correction/additional order cue
- current_order merge
- overwrite/append 규칙

### Action 문제

```text
응답 문장은 맞음
하지만 로봇 방향/표정/행동이 틀림
```

확인 대상:

- Response Manager action payload
- `robot_action`
- head/action mapping
- 실제 motor controller

---

## 5. 현재 production 실행 기준

2026-08-10 기준 실물 런타임에서 중요한 production module은 다음과 같다.

```text
STT
robot_controller.stt_node_unbiased
  └─ SafeSTTNode 기반

NLU
robot_controller.nlu_node
  └─ Structure B / koELECTRA-small

Decision
robot_controller.decision_node_additional_order
  └─ OrderHandoffDecisionNode 확장

Response
robot_controller.response_manager_node
  └─ pickup-aware manager 사용

Action
robot_controller.action_node_order_handoff
```

STT 모델과 NLU 모델의 `small`은 서로 다른 의미이다.

```text
STT: Faster-Whisper small
NLU: koELECTRA-small
```

따라서 `🗣️ 내가 한 말`이 틀린 문제는 koELECTRA-small 변경과 직접 관련이 없으며, STT/VAD 쪽을 먼저 확인한다.

---

## 6. 아직 해결되지 않은 문제

### 수량-only 추가 발화의 additive semantics

다음 흐름은 아직 별도 해결이 필요하다.

```text
기존 주문: 아이스 레몬에이드 5잔
사용자: 주문 추가!
로봇: 어떤 부분을 바꿀까요?
사용자: 한 잔 더 추가해 주세요.
현재 잘못된 결과: 5잔 → 1잔
기대 결과: 5잔 + 1잔 → 6잔
```

PR #96은 `딸기스무디 두 잔도 추가해주세요`처럼 **메뉴가 명시된 추가 주문**을 해결한 것이며, 메뉴가 없는 수량-only 증가는 의도적으로 해결 범위에서 제외했다.

후속 작업은 GitHub Issue #101에서 추적한다.

- Issue #101: `[Robot Dialogue] 수량만 추가하는 발화가 기존 수량을 덮어쓰는 문제`

구현 시 다음을 구분해야 한다.

1. `한 잔 더 추가해 주세요` → additive quantity
2. `한 잔으로 바꿔 주세요` → replacement quantity
3. 여러 메뉴가 이미 있을 때 수량만 말하면 대상 메뉴 재질문
4. `주문 추가!` 자체를 수정 흐름이 아닌 추가 주문 흐름으로 보낼지 검토

---

## 7. 이번 실험에서 얻은 개발 원칙

1. **실물 로그의 단계별 출력이 가장 중요하다.** STT, NLU, Decision을 한 문장으로 묶어서 보지 않는다.
2. **Whisper prompt로 비즈니스 규칙을 주입하지 않는다.** 음성 인식은 음성에 집중하고 메뉴/수량 판단은 NLU/Decision에서 처리한다.
3. **짧은 confirmation과 일반 주문은 같은 VAD 조건을 쓰지 않는다.**
4. **취소된 비동기 STT 결과는 반드시 turn token으로 차단한다.**
5. **주문 수정(replace)과 주문 추가(append/additive)를 별도 의미로 관리한다.**
6. **파일을 수정했다고 production이 바뀐 것으로 가정하지 않는다.** 실제 launcher가 어느 module을 실행하는지 startup log와 테스트로 검증한다.
7. **실물에서 발견한 문제는 재현 테스트와 PR을 함께 남긴다.** 이후 보고서에는 단순 구현 내용보다 문제 발견 → 원인 분석 → 해결 과정을 증거로 활용할 수 있다.

---

## 8. 관련 PR 요약

| PR | 문제/개선 | 상태 |
|---:|---|---|
| #89 | 화장실 방향 안내를 실제 guide action에 연결 | 해결 |
| #90 | 슬롯 재질문 중 명시적 주문 정정 복구 | 해결 |
| #91 | STT 메뉴 prompt bias 1차 완화 | 이후 #94로 대체 |
| #92 | 실물 수량/온도/부분 주문 슬롯 복구 | 해결 |
| #93 | stale STT 결과, retry race, audio stream stall 방지 | 해결 |
| #94 | Whisper lexical initial prompt 제거 | 해결 |
| #95 | 음료 수령대를 화장실 반대 방향으로 안내 | 해결 |
| #96 | 주문 확인 중 명시적 새 메뉴 추가 | 해결 |
| #97 | 실물 launcher가 최신 STT/Decision을 실제 실행하도록 수정 | 해결 |
| #98 | 실물 VAD 시작 민감도 조정 | 1차 튜닝 완료 |
| Issue #101 | 수량-only additive 주문 의미 처리 | 미해결/추적 중 |

---

## 9. 다음 실물 테스트 체크리스트

- [ ] startup에 `stt_node_unbiased`가 표시되는지
- [ ] startup에 `decision_node_additional_order`가 표시되는지
- [ ] `Whisper lexical initial prompts disabled` 로그 확인
- [ ] 일반 주문을 평소 목소리로 말해 VAD 시작 확인
- [ ] `네`, `아니요`가 짧게 말해도 잡히는지 확인
- [ ] `아이스 아메리카노 두 잔 주세요` 정상 처리
- [ ] `딸기스무디 두 잔도 추가해주세요` append 확인
- [ ] 화장실/음료 수령대 방향이 서로 반대인지 확인
- [ ] 사용자 발화와 `/voice_text`가 다른 경우 원본 STT 로그 저장
- [ ] 주변 소음 false trigger 빈도 확인
- [ ] Issue #101 수량-only 추가 주문 재현 여부 확인

## 10. CI 참고

위 PR들에는 회귀 테스트 코드가 추가되었지만, 현재 저장소에서 해당 커밋에 연결된 GitHub Actions workflow run은 확인되지 않았다. 따라서 문서에서 `CI 통과`로 표현하지 않으며, 실물 테스트와 로컬 테스트 결과를 별도로 관리한다.
