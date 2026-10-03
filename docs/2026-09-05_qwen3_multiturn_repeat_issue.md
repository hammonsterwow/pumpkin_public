# 2026-09-05 Qwen3-0.6B 멀티턴 반복·한국어 품질 이슈

## 1. 테스트 환경

Jetson Orin Nano에서 다음 구성으로 standalone 대화를 수행하였다.

```text
Model: lmstudio-community/Qwen3-0.6B-GGUF:Q4_K_M
Runtime: llama.cpp
llama.cpp build: b10818-4d9176092
Quantization: Q4_K_M
Context: 1024
Mode: qwen3_nonthinking.jinja
```

생성 속도는 대부분 약 32~54 tok/s로 충분히 빨랐다. 그러나 대화 품질에서 반복 응답, 의미 오해, 비문 생성이 확인되었다.

---

## 2. 1차 관찰: 동일 응답 반복

| 사용자 입력 | 모델 응답 | Generation |
|---|---|---:|
| `안녕` | `안녕하세요! 어떤 일에 대해 이야기해 드릴 수 있어요?` | 46.1 tok/s |
| `아이스아메리카노 하나줘` | `안녕하세요! 아이스아메리카노 하나 드릴 수 있어요. 😊` | 47.8 tok/s |
| `오늘 덥다` | `오늘 덥구니, 아침에 커피 드릴 수 있어요! 😄` | 49.8 tok/s |
| `음료 추천해줘` | `아침에 추천해드릴 수 있어요! 😄` | 54.0 tok/s |
| `카페라떼 얼마야?` | `아침에 추천해드릴 수 있어요! 😄` | 44.7 tok/s |
| `뭔소리니` | `아침에 추천해드릴 수 있어요! 😄` | 54.2 tok/s |
| `으일?` | `아침에 추천해드릴 수 있어요! 😄` | 43.7 tok/s |

초기에는 한 번 생성된 잘못된 문장이 이후 chat history에 포함되면서 동일 문장을 재사용하는 `multi-turn degeneration / history contamination` 가능성을 우선 의심하였다.

---

## 3. 추가 관찰: 히스토리만의 문제가 아님

추가 테스트에서는 대화 초반부터 의미 오해와 비문이 발생하였다.

| 사용자 입력 | 모델 응답 | Generation |
|---|---|---:|
| `안녕` | `안녕하세요! 어떤 일상이든 친근하게 대신해 주세요! 😊` | 48.2 tok/s |
| `커피 추천좀` | `안녕하세요! 커피 추천해 주세요! 😊` | 46.2 tok/s |
| `나한테 해달라고` | `안녕하세요! 나한테 해달라고 해요? 😊` | 45.1 tok/s |
| `왜 그래` | `요즘 갑득한 일어가지고 있어요! 😊` | 54.6 tok/s |
| `아니야` | `아니야? 하루하루 갑득한 일어가지고 있어요! 😊` | 42.7 tok/s |
| `뭐라도?` | `무슨 건이 있어요? 😊` | 38.7 tok/s |
| `갑득한이 뭔소리야` | `아니야? 하루하루 갑득한 일어가지고 있어요! 😊` | 46.2 tok/s |
| `지랄 ㄴ` | `지랄? 하루하루 갑득한 일어가지고 있어요! 😊` | 47.3 tok/s |
| `what are you doing now` | `안녕하세요! 하루하루 갑득한 일어가지고 있어요! 😊` | 47.6 tok/s |

따라서 문제를 chat history 하나만으로 설명하기 어렵고, 다음 가능성을 분리 검증해야 한다.

1. Qwen3-0.6B 자체의 작은 모델 크기로 인한 한국어 품질 한계
2. Q4_K_M 양자화로 인한 품질 저하
3. 사용 중인 community GGUF 변환본의 영향
4. 멀티턴 히스토리에 의한 반복 증폭
5. Pumpkin 도메인 및 역할 정보 부족

현재 사용 중인 `qwen3_nonthinking.jinja`는 Qwen 공식 llama.cpp 문서에서 non-thinking hard switch 용도로 제시하는 템플릿이므로, 우선 템플릿 자체보다는 모델/양자화/히스토리 영향을 분리해 본다.

---

## 4. 주문 문장 테스트 추가

| 사용자 입력 | 모델 응답 | Generation |
|---|---|---:|
| `카페라떼 하나 주세요` | `카페라테가 한 잔으로 나왔어요. 🍵` | 35.3 tok/s |
| `뭔소리` | `요즘은 간단한 카페라테로 하루 보내세요! 😊` | 32.3 tok/s |
| `싫어` | `요즘도 아침에 간단한 카페라테를 만듭니다. 🍵` | 35.8 tok/s |

첫 주문 입력에서는 `카페라떼`와 `한 잔` 정도는 의미적으로 잡았지만, 주문 확인 또는 다음 FSM 상태로 이어지지 못했다. 이후에는 다시 비맥락적 문장으로 드리프트하였다.

이는 Qwen을 주문 상태의 authoritative decision model로 사용할 수 없다는 기존 설계를 다시 확인해 준다.

---

## 5. 현재 판단

```text
Jetson 실행 가능성       : 성공
생성 속도               : 매우 양호 (약 32~54 tok/s)
기본 한국어 생성         : 가능하나 불안정
자유 멀티턴 대화         : 불안정
카페 도메인 응답         : 부족
주문 상태 판단           : 사용 부적합
```

따라서 Qwen3-0.6B를 바로 폐기하지는 않지만, 현재의 `community Q4_K_M + 자유 멀티턴` 조합을 그대로 Pumpkin에 통합하지 않는다.

---

## 6. 다음 분리 실험

### A. stateless single-turn 테스트

chat history 영향을 제거하기 위해 각 문장을 독립 실행한다.

테스트 문장:

```text
안녕
커피 추천해줘
오늘 덥다
카페라떼 하나 주세요
카페라떼 얼마야?
```

### B. 공식 Qwen Q8_0 GGUF와 비교

현재 community Q4_K_M 변환본과 별개로 공식 `Qwen/Qwen3-0.6B-GGUF:Q8_0`을 동일 조건에서 테스트한다.

목적:

- Q8_0에서 한국어가 정상화되면 Q4_K_M 또는 변환본 영향 가능성
- Q8_0에서도 비슷하면 0.6B 모델 크기 자체의 품질 한계 가능성

### C. Structured / State-conditioned Prompt

최종 ROS2 통합에서는 장시간 자유대화 히스토리를 그대로 넣지 않고 매 턴 다음 정보만 제공한다.

```text
FSM state
waiting_for
current_order
validated menu facts
user_text
selected vision context
```

Qwen은 이 구조화 상태를 받아 **이번 턴의 자연어 응답만 생성**한다.

주문 사실, 가격, 온도, 수량, 수정·취소·확정은 기존 koELECTRA NLU와 FSM을 authoritative source로 유지한다.

---

## 7. 설계 결론

```text
Free-form Chatbot                         X
Qwen이 주문 상태를 직접 판단              X
긴 chat history를 계속 누적               X

koELECTRA + DialogueActResolver + FSM     O
State-conditioned Qwen Response Generator O
Critical response template fallback       O
```

Q8_0 및 stateless 테스트 후에도 한국어 품질이 부족하면 다음 후보를 검토한다.

1. Qwen3-0.6B LoRA SFT
2. 더 큰 경량 모델(예: 1.7B급)의 Jetson 동시 구동 가능성 측정
3. Teacher-generated state-to-response 데이터 학습
