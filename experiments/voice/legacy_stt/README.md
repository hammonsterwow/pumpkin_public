# Legacy Standalone STT

이 디렉터리는 Pumpkin 프로젝트 초기 단계에서 사용한 **standalone Faster-Whisper STT / NLU 통합 코드**를 보관합니다.

## 상태

- **Legacy / Experiment Archive**
- 현재 로봇 production runtime에서는 사용하지 않습니다.
- 현재 실제 STT 실행 경로는 ROS2 package의 `robot_controller.stt_node_unbiased`입니다.
- `stt_node_unbiased.py`는 `stt_node_safe.py`와 `stt_node.py`를 상속해 현재 VAD, TTS 간섭 방지, turn cancellation, stale result 차단 등을 처리합니다.

현재 production 실행은 저장소 루트에서 다음 런처를 사용합니다.

```bash
bash scripts/run_ros_voice_nodes.sh
```

## 보관 파일

```text
main.py        과거 standalone 진입점
pipeline.py    고정 길이 녹음 -> Faster-Whisper -> NLU 통합 예제
record.py      초기 단순 녹음 유틸리티
transcribe.py  초기 CPU/base Whisper 변환 예제
test_stt.py    Jetson CUDA standalone STT 테스트
```

이 코드는 과거 실험 재현과 개발 과정 참고를 위해 보존합니다. 새 기능은 이 디렉터리에 추가하지 않습니다.
