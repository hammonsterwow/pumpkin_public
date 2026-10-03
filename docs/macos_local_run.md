# macOS에서 Pumpkin ROS2 텍스트 테스트 실행

이 문서는 유지성 개발 PC의 저장소 경로를 기준으로 작성했습니다.

```text
/Users/ysy/Documents/GitHub/pumpkin
```

macOS 환경은 **텍스트 입력으로 NLU, Decision, Response Manager, Action 흐름을 확인하는 테스트 전용**입니다.

- macOS에서는 STT와 TTS 노드를 실행하지 않습니다.
- Faster-Whisper, PortAudio, sounddevice 같은 Mac 네이티브 오디오 의존성을 설치하지 않습니다.
- Jetson의 `stt_node.py`, `tts_node.py`, CUDA 실행 스크립트, `.venv`, `.venv-nlu` 구성은 변경하지 않습니다.
- 실제 음성 인식, 음성 출력, 로봇 구동 검증은 Jetson에서 기존 실행 방법을 사용합니다.

## 1. 저장소 최신화

PR이 병합되기 전에는 다음 브랜치를 사용합니다.

```bash
cd /Users/ysy/Documents/GitHub/pumpkin
git fetch origin
git checkout feat/pc-ros-voice-runner
git pull origin feat/pc-ros-voice-runner
```

PR 병합 후에는 `main`을 사용합니다.

```bash
cd /Users/ysy/Documents/GitHub/pumpkin
git checkout main
git pull
```

## 2. 기존 Python 가상환경 종료

터미널 앞에 `(.venv)`가 표시되어 있다면 Pixi 환경과 겹치지 않도록 종료합니다.

```bash
deactivate
```

`deactivate: command not found`가 나오면 이미 일반 셸입니다.

## 3. Pixi 설치

```bash
curl -fsSL https://pixi.sh/install.sh | bash
exec zsh
pixi --version
```

## 4. macOS 테스트 환경 설치

```bash
cd /Users/ysy/Documents/GitHub/pumpkin
pixi install
```

설치되는 주요 구성:

- ROS2 Humble
- Python
- PyTorch CPU
- Transformers

설치 확인:

```bash
pixi run python -c "import torch, transformers, huggingface_hub; print('Python packages OK')"
pixi run bash --noprofile --norc -c 'command -v ros2'
```

## 5. ROS2 workspace 빌드

처음 빌드하거나 이전 빌드가 실패했다면:

```bash
cd /Users/ysy/Documents/GitHub/pumpkin
pixi run build-ros-clean
```

이후 일반 빌드:

```bash
pixi run build-ros
```

## 6. 터미널 1: 텍스트 테스트 파이프라인 실행

```bash
cd /Users/ysy/Documents/GitHub/pumpkin
pixi run run-macos
```

실행되는 노드:

```text
/nlu_node
/decision_node
/response_manager_node
/action_node
```

정상 시작 메시지:

```text
stt=disabled (macOS native audio stack is not used)
tts=disabled (Jetson TTS code is not used or modified)
Pumpkin ROS text-test pipeline is READY on macOS (STT/TTS disabled).
```

## 7. 터미널 2: 텍스트 대화 테스트

새 터미널에서 실행합니다.

```bash
cd /Users/ysy/Documents/GitHub/pumpkin
pixi run terminal-chat
```

전체 JSON을 함께 확인하려면:

```bash
pixi run terminal-chat-debug
```

`terminal_chat.py`가 입력 문장을 `/voice_text`에 발행하므로 실제 `nlu_node → decision_node → response_manager_node → action_node` 흐름을 확인할 수 있습니다.

## 8. 상태 확인

ROS 노드 목록:

```bash
cd /Users/ysy/Documents/GitHub/pumpkin
pixi run bash --noprofile --norc -c 'source ros2_ws/install/setup.bash && ros2 node list'
```

정상 목록에는 `/stt_node`와 `/tts_node`가 없어야 합니다.

로그:

```bash
tail -f /tmp/pumpkin-logs/nlu_node.log
tail -f /tmp/pumpkin-logs/decision_node.log
tail -f /tmp/pumpkin-logs/action_node.log
```

NLU 모델 파일 확인:

```bash
ls -lh /Users/ysy/Documents/GitHub/pumpkin/nlu/saved_models/structure_b_item_query_decoder/best_model.pt
ls -ld /Users/ysy/Documents/GitHub/pumpkin/nlu/saved_models/structure_b_item_query_decoder/tokenizer
```

## 종료

터미널 1에서 `Ctrl+C`를 누르면 Mac 테스트용으로 실행한 ROS 노드가 종료됩니다.
