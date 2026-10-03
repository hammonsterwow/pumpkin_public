# 2026-09-05 Qwen3-0.6B 스몰토크 확장 및 Standalone 검증 기록

## 1. 작업 목적

현재 Pumpkin의 주문 대화 시스템은 `STT → NLU → Decision/FSM → Response Manager → Action → TTS` 구조로 동작한다. 주문 메뉴·온도·수량과 같은 도메인 정보는 기존 koELECTRA 기반 NLU가 안정적으로 처리하지만, 사용자가 실제 대화에서 사용하는 짧은 긍정 표현, 일반적인 일상어, 스몰토크까지 프로젝트 자체 데이터와 규칙만으로 모두 커버하기에는 한계가 있다고 판단하였다.

특히 `응`, `그래`, `그걸로 해`, `오늘 덥다`, `너 이름 뭐야?`와 같이 카페 주문 데이터에 직접 포함되지 않거나 주문 슬롯으로 구조화하기 어려운 표현을 매번 규칙과 데이터 증강으로 추가하는 방식은 확장성이 낮다.

따라서 일반 한국어 능력을 이미 보유한 경량 사전학습 언어모델을 기존 주문 시스템에 보조적으로 추가하여, 주문 판단의 안정성은 유지하면서 자연스러운 스몰토크와 응답 다양성을 확보할 수 있는지 검증하기로 하였다.

---

## 2. 현재 구조에서 확인한 사항

### 2.1 기존 NLU/FSM은 유지

Qwen 계열 모델이 주문 메뉴, 온도, 수량, 수정, 취소, 확정과 같은 핵심 주문 판단을 직접 담당하도록 전체 구조를 교체하지 않는다.

기존 역할은 다음과 같이 유지한다.

```text
STT
→ koELECTRA NLU
→ DialogueActResolver
→ Decision / FSM
→ Response Manager
→ Action
→ TTS / LCD / Motion
```

- koELECTRA NLU: 주문 Intent 및 주문 항목 구조화
- DialogueActResolver: 현재 대화 상태를 고려한 짧은 표현 처리
- Decision/FSM: 주문 상태, 누락 슬롯, 수정·취소·확정 등 실제 행동 결정
- Response Manager: 결정 결과를 실제 사용자 응답 문장으로 변환

현재 `DialogueActResolver`에는 `네`, `응`, `맞아`, `맞아요`, `좋아요` 등 대표적인 긍정 표현이 별도 처리되어 있다. 이는 실제 주문 안정성을 위해 계속 유지한다.

### 2.2 생성형 모델의 역할 분리

새로 도입하는 Qwen은 주문의 실제 상태를 결정하는 모델이 아니라 다음 역할을 담당하도록 설계한다.

- 스몰토크 응답
- 비주문 일반 발화 이해 보조
- 주문 상태에 맞는 자연스러운 문장 생성
- 기존 고정 템플릿의 표현 다양화
- 단골 고객 및 상황 맥락을 반영한 자연스러운 응대

예시:

```text
현재 FSM 상태: ASK_TEMPERATURE
현재 주문: 아메리카노 1잔
사용자 발화: 오늘 진짜 춥다
```

예상 생성 응답:

```text
그러게요, 오늘은 좀 쌀쌀하네요. 아메리카노는 따뜻하게 드릴까요, 아이스로 드릴까요?
```

스몰토크를 수행하더라도 현재 FSM이 요구하는 질문을 잊지 않고 다시 주문 흐름으로 돌아오도록 하는 것을 핵심 요구사항으로 정의하였다.

---

## 3. 적용 후보 모델 선정

첫 검증 모델로 `Qwen3-0.6B`를 선정하였다.

선정 이유:

- 0.6B급 경량 모델로 Jetson Orin Nano 8GB에서 테스트할 수 있는 크기
- 사전학습 및 대화형 post-training을 통해 일반 언어 능력을 이미 보유
- 프로젝트 자체 데이터만으로 처음부터 일반 한국어 표현을 학습시키는 부담을 줄일 수 있음
- 향후 LoRA를 통해 Pumpkin의 로봇 캐릭터와 FSM 상태 기반 응답 패턴만 추가 학습할 수 있음

초기 검증 단계에서는 LoRA를 적용하지 않는다.

```text
Qwen3-0.6B 순정 모델
→ GGUF
→ Q4_K_M 4-bit quantization
→ llama.cpp
→ Jetson Orin Nano standalone 실행
```

먼저 순정 모델의 한국어·스몰토크 능력과 Jetson 자원 사용량을 확인한 뒤, 실제 필요성이 확인되면 LoRA 학습을 진행한다.

---

## 4. Standalone 검증

### 4.1 목적

ROS2 전체 시스템에 바로 통합하지 않고 Qwen만 단독으로 실행하여 다음 항목을 먼저 측정한다.

1. Jetson에서 llama.cpp CUDA 빌드 및 실행 가능 여부
2. Qwen3-0.6B Q4_K_M 모델 로딩 가능 여부
3. 한국어 기본 대화 품질
4. 스몰토크 가능 여부
5. 짧은 응답 생성 속도
6. 모델 실행 중 RAM 및 GPU 사용량

### 4.2 테스트 환경

```text
Device: NVIDIA Jetson Orin Nano Developer Kit
OS: Ubuntu 22.04 / JetPack 6.2.1
CUDA: 12.6
llama.cpp build: b10818-4d9176092
Model: lmstudio-community/Qwen3-0.6B-GGUF:Q4_K_M
Quantization: Q4_K_M (Q4_K - Medium)
Context: 1024
Output: 최대 64 tokens
Mode: non-thinking custom chat template
```

### 4.3 CLI 옵션 호환성 문제

초기 실행 시 현재 설치된 `llama-cli`에서 `-cnv`, `--conversation` 옵션이 인식되지 않는 문제가 발생하였다.

```text
error: invalid argument: -cnv
error: invalid argument: --conversation
```

현재 빌드에서는 별도의 conversation 옵션을 넣지 않고 chat template을 지정한 상태로 CLI를 실행하여 대화 모드가 정상 동작하는 것을 확인하였다.

### 4.4 실제 한국어·스몰토크 테스트 결과

순정 Qwen3-0.6B Q4_K_M 모델을 Jetson에서 standalone으로 실행하여 다음과 같은 결과를 확인하였다.

| 사용자 입력 | 모델 응답 | Generation |
|---|---|---:|
| `안녕` | `안녕하세요! 어떤 일에 대해 이야기해 드릴 수 있어요?` | 46.1 tok/s |
| `아이스아메리카노 하나줘` | `안녕하세요! 아이스아메리카노 하나 드릴 수 있어요. 😊` | 47.8 tok/s |
| `오늘 덥다` | `오늘 덥구니, 아침에 커피 드릴 수 있어요! 😄` | 49.8 tok/s |
| `음료 추천해줘` | `아침에 추천해드릴 수 있어요! 😄` | 54.0 tok/s |

Prompt 처리 속도는 각 턴에서 `771.0`, `615.8`, `561.4`, `15.8 tok/s`로 출력되었다. 마지막 prompt 속도가 크게 낮아진 이유는 추가 확인이 필요하므로 현재는 원인 미확정으로 기록한다.

### 4.5 자연스러움 평가

#### 긍정적 결과

- 기본적인 한국어 문장 생성은 가능하였다.
- `안녕`과 같은 일반 인사 발화에는 문법적으로 자연스러운 답변을 생성하였다.
- 생성 속도가 약 46~54 tok/s로 매우 빨라 짧은 로봇 응답을 생성하기에는 충분한 가능성을 확인하였다.
- 주문 문장인 `아이스아메리카노 하나줘`를 일반적인 의미 수준에서는 이해하였다.

#### 확인된 한계

순정 모델만으로는 Pumpkin 카페 로봇의 응답 생성기로 바로 사용하기 어렵다고 판단하였다.

- `오늘 덥다` → `오늘 덥구니`와 같이 어색하거나 잘못된 한국어 표현이 생성됨
- 현재 시간이나 문맥에 없는 `아침`이라는 표현을 임의로 추가함
- `음료 추천해줘`에 실제 메뉴를 추천하지 못하고 `아침에 추천해드릴 수 있어요`라고 응답함
- 주문 요청에도 `아이스아메리카노 하나 드릴 수 있어요`처럼 주문 상태를 확인하거나 FSM의 다음 질문으로 연결하지 못함
- 이모지를 사용하여 실제 TTS 로봇 응답으로는 불필요한 표현이 포함됨

따라서 순정 Qwen은 **일반적인 한국어 생성 능력과 높은 추론 속도는 확보했지만, 카페 도메인 지식·로봇 역할·FSM 상태 유지·응답 정책에 대한 grounding이 부족**한 상태로 평가하였다.

### 4.6 Jetson 자원 상태

Standalone 테스트 시 `tegrastats`에서 RAM은 대략 `3.25~3.28GB / 7.62GB` 수준으로 관찰되었으며 SWAP 사용량은 거의 없었다. 온도는 약 46~48°C 범위로 안정적이었다.

다만 측정 로그에서는 `GR3D_FREQ 0%`가 유지되었기 때문에 해당 구간이 실제 생성 시점과 정확히 겹쳤는지 확인이 필요하다. 따라서 **CUDA GPU offload 성공 여부는 모델 초기 로딩 로그와 생성 중 tegrastats를 추가로 확인한 뒤 최종 확정**한다.

---

## 5. 현재 판단

Standalone 1차 검증 결과는 다음과 같다.

```text
Jetson 모델 로딩      : 성공
한국어 생성           : 가능
생성 속도             : 매우 양호 (약 46~54 tok/s)
카페 도메인 자연스러움 : 부족
FSM/주문 상태 grounding: 없음
메모리 여유           : standalone 기준 양호
GPU offload            : 추가 확인 필요
```

따라서 Qwen3-0.6B를 폐기하기보다는, **기존 koELECTRA + FSM을 유지하면서 Qwen을 자연어 응답 계층으로 제한하고 Pumpkin 상태 정보를 입력으로 제공하는 방향**이 적절하다고 판단하였다.

---

## 6. 향후 통합 구조

```text
사용자 발화
    ↓
STT
    ↓
koELECTRA NLU
    ↓
DialogueActResolver
    ↓
Decision / FSM
    ↓
Hybrid Response Manager
   ├─ Critical Response → 기존 Template
   └─ Natural / Small Talk → Qwen3-0.6B
    ↓
Action
    ↓
TTS / LCD / Head / Arm
```

### Template을 유지할 영역

- 주문 최종 확정
- 취소
- 결제 안내
- 시스템 오류
- 모델 timeout 및 생성 실패

### Qwen을 활용할 영역

- 인사
- 자연스러운 재질문
- 스몰토크
- 단골 고객 개인화 응대
- 현재 FSM 상태를 유지한 자연어 응답 생성

Qwen이 timeout, crash, empty response 등의 문제를 발생시키면 기존 Response Manager 템플릿으로 즉시 fallback하여 주문 서비스가 중단되지 않도록 설계한다.

---

## 7. 학습 방향 결정

Standalone 테스트 결과, 일반적인 한국어 지식을 처음부터 학습시킬 필요는 없지만 Pumpkin 도메인에 맞는 응답 방식은 추가 학습 또는 강한 상태 기반 prompting이 필요함을 확인하였다.

향후 LoRA 학습 시에는 기존 NLU 데이터 전체를 그대로 Qwen에 학습시키지 않고 다음 종류의 데이터만 별도로 구성한다.

```text
1. FSM State → Response 데이터
2. 주문 중 Small Talk → 주문 목표 복귀 데이터
3. 일반 한국어 대화 replay 데이터
4. Teacher Model로 생성한 다양한 표현 데이터
5. 단골·비전 Context가 포함된 개인화 응답 데이터
6. Out-of-scope 및 fallback 데이터
```

핵심 방향은 다음과 같다.

> 일반 한국어 능력은 사전학습 모델에서 활용하고, Pumpkin 데이터는 카페 주문 규칙과 로봇 역할 및 FSM 상태에 맞는 응답 방식만 추가 학습한다.

---

## 8. 이번 작업 결과

### 완료

- 기존 자체 구축 데이터 및 규칙만으로 일반 한국어와 스몰토크를 모두 처리하기 어렵다는 한계 정리
- 기존 koELECTRA NLU와 FSM을 유지하는 하이브리드 구조 결정
- Qwen3-0.6B를 자연어 응답 및 스몰토크용 SLM 후보로 선정
- Qwen3-0.6B Q4_K_M을 Jetson Orin Nano에서 standalone 로딩 및 대화 실행 성공
- 한국어 기본 대화와 카페 관련 발화에 대한 순정 모델 품질 확인
- 약 46~54 tok/s의 생성 속도 확인
- standalone 기준 약 3.25~3.28GB RAM 사용 상태 관찰
- 순정 모델의 카페 도메인 grounding과 자연스러운 응답 품질 한계 확인
- Hybrid Response Manager 및 Template fallback 구조 유지 결정

### 미완료 / 다음 작업

- 생성 중 `GR3D_FREQ` 및 모델 로딩 로그를 통한 CUDA GPU offload 최종 확인
- 순정 모델에 FSM state/order context를 직접 prompt로 제공한 2차 테스트
- 이모지 금지, 사실 임의 생성 금지, 1~2문장 제한 등 system prompt 강화 테스트
- 기존 STT/NLU/Vision과 Qwen을 동시에 실행한 통합 메모리 검증
- Vanilla + Prompting으로 충분한지 확인 후 LoRA 필요 여부 최종 결정

---

## 9. 다음 단계

1. 모델 초기 로딩 로그에서 GPU layer offload 여부를 확인한다.
2. 실제 생성 중 `tegrastats`의 `GR3D_FREQ` 변화를 확인한다.
3. 단순 스몰토크가 아니라 `FSM state + order + user_text`를 함께 제공하는 structured prompt 테스트를 진행한다.
4. 로봇 역할과 금지 조건을 강화한 system prompt로 순정 모델 성능을 한 번 더 평가한다.
5. Prompting만으로 목표 품질에 도달하지 못할 경우 Teacher 기반 응답 데이터셋을 구축하고 Qwen3-0.6B에 LoRA SFT를 적용한다.
6. 이후 ROS2 Response Manager에 semantic fallback 및 자연어 생성 계층을 단계적으로 통합한다.
