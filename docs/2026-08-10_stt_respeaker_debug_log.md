# 2026-08-10 STT · ReSpeaker Lite 현장 디버깅 기록

## 1. 기록 목적

2026-08-10 Jetson Orin Nano 실기 테스트에서 확인된 음성 대화 문제와 ReSpeaker Lite 오디오 경로 조사 결과를 한곳에 기록한다.

이 문서는 단순 작업 메모가 아니라 아래 흐름이 다시 보이도록 작성한다.

1. 현장에서 어떤 문제가 발생했는가
2. 로그에서 어떤 원인이 확인되었는가
3. 어떤 코드 수정으로 대응했는가
4. 실제 ReSpeaker Lite 장치가 어떻게 인식되는가
5. 아직 검증하지 못한 부분은 무엇인가
6. 다음 실험에서 무엇을 확인해야 하는가

후속 AEC/full-duplex 작업은 GitHub Issue #100에서 추적한다.

---

## 2. 실기 주문 대화에서 발견된 문제

실제 로봇 주문 흐름을 반복 테스트하면서 다음 문제가 확인되었다.

### 문제 1. 주문 수정 단계에서 짧은 답변 인식 불안정

대표 흐름:

```text
사용자: 바닐라라떼 세 잔 주세요.
로봇: 따뜻하게 드릴까요, 아이스로 드릴까요?
사용자: 뜨겁게 주세요.
로봇: 따뜻한 바닐라라떼 3잔 맞으신가요?
사용자: 아니요.
로봇: 어떤 부분을 바꿀까요?
사용자: 네 잔이요.
```

현장에서는 수정 질문 뒤 `네 잔이요`와 같은 짧은 발화가 STT에 잘 잡히지 않는 경우가 있었다.

#### 원인

`MODIFY_ORDER`가 일반 주문 발화와 동일한 VAD 시작 조건을 사용하고 있었다.

- 일반 주문: 연속 7 block 수준의 보수적인 speech start
- 확인/짧은 답변: 더 짧은 speech start 필요

또한 외부 ROS VAD가 실제 음성을 녹음했더라도 Faster-Whisper 내부 VAD가 짧은 한국어 발화를 제거해 `No speech was recognized`가 발생하는 경우가 확인되었다.

### 문제 2. STT 재시도 소진 후 대화가 멈춤

기존 흐름에서는 STT 실패가 여러 번 누적되면 `STT_FAILED` 상태에서 더 이상 새 주문을 받지 못하는 경우가 있었다.

사용자 관점에서는 다음 안내 뒤 대화가 사실상 종료되는 문제가 있었다.

```text
주문을 잘 듣지 못했어요. 화면을 확인하거나 다시 시도해 주세요.
```

### 문제 3. 주문 수정 질문에서 고개 SHAKE

`어떤 부분을 바꿀까요?`처럼 정보를 요청하는 상황인데 Action rule에서 `MODIFY_ORDER`가 SHAKE 동작으로 표현되어 의미가 어색했다.

### 문제 4. 로봇 발화 종료 후 응답 타이밍이 느림

TTS 종료 후에도 microphone guard가 남아 있어 사용자가 로봇 말이 끝난 직후 바로 대답하기 어렵게 느껴졌다.

---

## 3. 적용된 해결 — PR #86

관련 PR:

- PR #86 `Improve STT recovery and response timing`
- merge commit: `41740323947e626cc3ec2df4fecf7c7f6cfa068c`

### 3.1 MODIFY_ORDER도 short VAD 사용

`ASK_TEMPERATURE`, `ASK_QUANTITY`뿐 아니라 `MODIFY_ORDER`도 confirmation/short VAD trigger를 사용하도록 변경했다.

기대 로그:

```text
Published STT trigger: confirm (tts_done)
Listening... mode=confirmation, start_blocks=4
```

수정 단계의 `네 잔이요`, `아이스요`, `레몬에이드요` 같은 짧은 응답을 일반 주문보다 빠르게 감지하는 목적이다.

### 3.2 Faster-Whisper 내부 VAD empty fallback

외부 VAD가 녹음을 성공했는데 Whisper 결과가 비어 있는 경우에만 같은 녹음 파일을 `vad_filter=False`로 한 번 더 추론한다.

기대 로그:

```text
Whisper internal VAD returned empty text; retrying once without it.
```

정상적으로 인식된 발화에는 추가 추론 비용이 발생하지 않는다.

### 3.3 최종 STT 실패 시 주문을 처음부터 재시작

STT retry가 모두 소진되면 local `STT_FAILED`에서 멈추지 않고 synthetic recovery intent를 Decision FSM에 전달한다.

결과:

- 현재 주문 초기화
- 새 session 생성
- state → `ORDER_LISTEN`
- `REORDER_REQUEST`
- 사용자에게 `주문을 처음부터 다시 말씀해 주세요.` 출력

### 3.4 MODIFY_ORDER head CENTER

주문 변경 질문 시 head action을 `SHAKE`가 아니라 `CENTER`로 변경했다.

### 3.5 TTS 뒤 guard 단축

physical demo 기준 post-TTS acoustic guard를 0.15 s에서 0.05 s로 줄였다.

현재는 AEC가 검증되지 않았으므로 **로봇이 말하는 도중 STT를 여는 full-duplex는 아직 적용하지 않았다.**

---

## 4. ReSpeaker Lite 장치 조사

### 4.1 사용 장비

Pumpkin 하드웨어 구성에서 사용하는 마이크는:

```text
Seeed Studio ReSpeaker Lite
M03 / USB 2-Mic Array
XMOS XU316
```

Jetson에서 USB 장치 확인 결과:

```text
2886:0019 Seeed Technology Co., Ltd. ReSpeaker Lite
```

별도 TTS 스피커:

```text
1908:2070 GEMBIRD Honk HK-5002 USB Speaker
```

### 4.2 ALSA capture / playback 확인

`arecord -l`:

```text
card 0: Lite [ReSpeaker Lite], device 0: USB Audio
```

`aplay -l`에서도 동일한 ReSpeaker Lite가 playback 장치로 존재했다.

즉 ReSpeaker Lite는 Jetson에서 단순 microphone-only 장치가 아니라 **capture + playback 가능한 USB audio device**로 인식된다.

### 4.3 실제 USB stream 사양

실행:

```bash
cat /proc/asound/card0/stream0
```

결과:

```text
Playback:
  Format: S16_LE
  Channels: 2
  Rates: 16000

Capture:
  Format: S16_LE
  Channels: 2
  Rates: 16000
```

따라서 현재 ReSpeaker Lite USB stream은:

- 16 kHz
- 16-bit signed little endian
- playback 2ch
- capture 2ch

로 동작한다.

Faster-Whisper 입력에 사용하기에도 16 kHz라는 점은 적합하다.

### 4.4 ALSA mixer control 확인

실행:

```bash
amixer -c 0
amixer -c 0 contents
```

일반적인 볼륨/AEC/NS switch는 노출되지 않았다.

확인된 항목은 주로:

- Clock Source Validity
- Capture Channel Map
- Playback Channel Map

이었다.

따라서 AEC, noise suppression 등의 기능이 사용된다면 ALSA mixer에서 별도 프로그램으로 ON/OFF하는 형태보다는 **XMOS firmware 내부 DSP 경로에 포함되는 구조일 가능성이 높다.**

단, 이 단계에서는 실제 capture signal에 AEC/NS가 어느 정도 적용되고 있는지 실측하지 않았다.

---

## 5. 현재 Pumpkin 오디오 구조와 한계

현재 구조는 개념적으로 다음과 같다.

```text
ReSpeaker Lite mic
    ↓ USB capture
Jetson STT

Jetson TTS
    ↓
별도 USB Speaker
```

Pumpkin 실행 스크립트는 ReSpeaker 입력을 자동 선택하지만 기본 input channel 수는 1이다.

```bash
AUDIO_CHANNELS="${PUMPKIN_AUDIO_CHANNELS:-1}"
```

하지만 실제 ReSpeaker capture는 2채널을 제공한다.

또한 TTS는 ReSpeaker playback이 아닌 별도 USB Speaker로 출력된다.

이 상태에서는 ReSpeaker가 로봇 TTS playback reference를 직접 받지 못하므로 **ReSpeaker 자체 AEC 성능을 충분히 활용하고 있다고 판단하지 않는다.**

현재 자기 음성 재인식을 막는 핵심 방법은 ReSpeaker AEC가 아니라 `stt_node.py`의 TTS hard gate이다.

```text
TTS speaking
→ STT cancel / 대기
→ TTS done
→ 짧은 guard
→ STT 시작
```

---

## 6. 목표 구조

장기 목표는 다음과 같은 AEC 기반 full-duplex 구조이다.

```text
Jetson TTS
    ↓ USB playback
ReSpeaker Lite / XMOS
    ↓
Speaker output
    ↓
공간에 로봇 음성 재생

사용자 음성 + 로봇 음성
    ↓
ReSpeaker Mic
    ↓
XMOS AEC / Noise Processing
    ↓ USB capture
VAD
    ↓
Faster-Whisper
    ↓
NLU
```

이 구조가 검증되면 사용자는 로봇 TTS가 완전히 끝나기 전에도 다음처럼 끼어들 수 있다.

```text
로봇: 바닐라라떼는 따뜻하게 드릴까요, 아이스로—
사용자: 아이스로 주세요.
```

이 기능을 구현할 때는 단순 STT continuous listening뿐 아니라 **barge-in 시 TTS 중단/감쇠 정책**도 함께 고려한다.

---

## 7. 아직 확정하지 않은 것

다음 항목은 오늘 장치 목록만으로 확정하지 않았다.

1. ReSpeaker capture ch0/ch1의 정확한 역할
2. 현재 USB firmware 버전
3. 현재 capture signal에서 noise suppression이 어느 정도 적용되는지
4. ReSpeaker playback을 reference로 사용할 때 실제 AEC 성능
5. 로봇 TTS와 사용자가 동시에 말할 때 사용자 음성이 충분히 보존되는지

따라서 이 항목들은 추측으로 코드에 반영하지 않는다.

---

## 8. 다음 실험 계획

후속 추적: **Issue #100 — `audio: ReSpeaker Lite AEC 검증 및 full-duplex STT 전환`**

스피커/출력 장비 준비 후 아래 순서로 진행한다.

### Step 1. ReSpeaker 2채널 녹음 비교

```bash
arecord \
  -D hw:CARD=Lite,DEV=0 \
  -f S16_LE \
  -r 16000 \
  -c 2 \
  -d 10 \
  ~/respeaker_stereo.wav
```

이후 ch0/ch1을 분리해 실제 음질과 noise characteristic을 비교한다.

### Step 2. ReSpeaker playback 확인

ReSpeaker의 실제 speaker/headphone output에 스피커를 연결한 뒤:

```bash
speaker-test \
  -D plughw:CARD=Lite,DEV=0 \
  -r 16000 \
  -c 2 \
  -t wav
```

으로 playback 경로를 확인한다.

### Step 3. AEC 비교 실험

동일 조건에서 비교한다.

```text
A. 별도 USB Speaker playback + ReSpeaker capture
B. ReSpeaker playback → speaker + ReSpeaker capture
```

비교 항목:

- robot TTS가 capture에 남는 정도
- RMS / waveform
- 사용자 동시 발화 보존 여부
- Faster-Whisper 결과

### Step 4. full-duplex 전환 판단

AEC 효과가 충분한 경우에만:

- TTS speaking 중 STT hard gate 옵션화/제거
- continuous microphone capture
- 사용자 발화 감지 시 TTS 중단/감쇠
- 자기 TTS 오인식 회귀 테스트

를 진행한다.

---

## 9. 오늘의 결론

오늘 실험에서 가장 중요한 결론은 다음과 같다.

1. 주문 수정 단계의 짧은 STT 응답 실패는 VAD/Whisper 내부 VAD/재시도 복구 구조 문제였고 PR #86에서 보완했다.
2. ReSpeaker Lite는 Jetson에서 정상적으로 capture와 playback을 모두 제공한다.
3. 실제 stream은 16 kHz / S16_LE / 2ch이다.
4. 현재 Pumpkin은 ReSpeaker 2채널 중 기본 1채널만 사용한다.
5. 현재 TTS가 별도 USB Speaker로 나가므로 ReSpeaker AEC를 충분히 활용하고 있다고 볼 수 없다.
6. AEC 성능은 스피커를 ReSpeaker playback 경로에 연결한 뒤 반드시 실측해야 한다.
7. AEC 검증 전까지는 현재의 TTS hard gate 기반 half-duplex 구조를 유지한다.
8. 검증 성공 시 최종 목표는 AEC 기반 full-duplex + barge-in 음성 대화이다.
