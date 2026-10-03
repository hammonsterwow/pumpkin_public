# Jetson Orin Nano CUDA/NLU 환경 상태

최종 확인일: 2026-07-17

이 문서는 Jetson Orin Nano에서 Faster-Whisper와 PyTorch 기반 NLU를 함께 실행하기 위해 확인한 환경, 실패 원인, 최종 해결 상태를 기록한다.

## 1. 최종 장비 환경

```text
Device: Jetson Orin Nano
Ubuntu: 22.04
Python: 3.10
L4T: R36.5.0
JetPack: 6.2.2+b24
CUDA Toolkit: 12.6
nvcc: V12.6.68
NLU PyTorch: 2.8.0
PyTorch CUDA build: 12.6
```

확인 명령:

```bash
cat /etc/nv_tegra_release
apt list --installed | grep nvidia-jetpack
nvcc --version
```

최종 확인 결과:

```text
# R36 (release), REVISION: 5.0
nvidia-jetpack: 6.2.2+b24
CUDA compilation tools: release 12.6, V12.6.68
```

## 2. 최초 문제

시스템 Python과 기존 프로젝트 가상환경 `.venv`에 일반 PyPI의 CPU 전용 PyTorch 2.2.2가 설치되어 있었다.

```text
Torch: 2.2.2
Built CUDA: None
CUDA available: False
cuDNN: None
```

따라서 CUDA Toolkit과 JetPack이 정상 설치되어 있어도 PyTorch 기반 koELECTRA NLU는 GPU를 사용할 수 없었다.

반면 Faster-Whisper가 사용하는 CTranslate2는 GPU를 정상 감지했다.

```text
CTranslate2 CUDA devices: 1
```

즉, 시스템 CUDA 전체의 문제가 아니라 NLU가 사용하는 PyTorch 빌드의 문제였다.

## 3. Python 환경 분리

기존 `.venv`는 ROS2와 Faster-Whisper/CTranslate2용으로 유지하고, NLU 전용 독립 환경 `.venv-nlu`를 생성했다.

중요: `--system-site-packages`를 사용하면 시스템의 CPU PyTorch가 노출되므로 사용하지 않는다.

```bash
cd ~/pumpkin
rm -rf .venv-nlu
python3 -m venv .venv-nlu
echo 'export PYTHONNOUSERSITE=1' >> .venv-nlu/bin/activate
source .venv-nlu/bin/activate
python -m pip install --upgrade pip
```

격리 확인:

```bash
python - <<'PY'
import site
import sys

print("Python:", sys.executable)
print("User site enabled:", site.ENABLE_USER_SITE)

try:
    import torch
    print("문제: torch가 보입니다.", torch.__file__)
except ModuleNotFoundError:
    print("정상: 독립 환경에 torch가 없습니다.")
PY
```

정상 기준:

```text
User site enabled: False
정상: 독립 환경에 torch가 없습니다.
```

ROS2 패키지는 가상환경에 복사하지 않고 ROS2 setup을 통해 사용한다.

```bash
source /opt/ros/humble/setup.bash
source ~/pumpkin/ros2_ws/install/setup.bash
```

확인 결과 `.venv-nlu` Python에서 `rclpy`와 `robot_controller` import가 정상 동작했다.

## 4. NLU Python 의존성

```bash
cd ~/pumpkin
source .venv-nlu/bin/activate

python -m pip install --no-cache-dir \
  "numpy<2" \
  "transformers==4.40.2" \
  "huggingface-hub>=0.21.2,<1.0" \
  "fsspec==2024.6.1" \
  safetensors \
  tokenizers \
  "sympy>=1.13.3" \
  networkx \
  jinja2
```

## 5. Jetson CUDA용 PyTorch 설치

일반 명령인 `pip install torch` 또는 `pip install torch==2.2.2`는 사용하지 않는다.

Jetson/Python 3.10/aarch64/CUDA 12.6용 PyTorch 2.8.0 wheel을 다운로드하여 `.venv-nlu`에만 설치했다.

```bash
cd ~/Downloads

wget -O torch-2.8.0-cp310-cp310-linux_aarch64.whl \
  https://github.com/davidl-nv/torch/raw/refs/heads/main/torch-2.8/torch-2.8.0-cp310-cp310-linux_aarch64.whl

python3 -m zipfile -t torch-2.8.0-cp310-cp310-linux_aarch64.whl
```

정상 기준:

```text
Done testing
```

설치:

```bash
cd ~/pumpkin
source .venv-nlu/bin/activate

python -m pip install \
  --no-cache-dir \
  --no-deps \
  ~/Downloads/torch-2.8.0-cp310-cp310-linux_aarch64.whl
```

설치 확인:

```text
Torch: 2.8.0
Location: /home/pumpkin/pumpkin/.venv-nlu/lib/python3.10/site-packages
No broken requirements found.
```

## 6. `LD_LIBRARY_PATH` 충돌

다음과 같이 시스템 라이브러리 경로를 앞에 넣으면 PyTorch 2.8 Python 파일과 시스템 PyTorch 공유 라이브러리가 섞여 import 오류가 발생했다.

```text
ImportError: cannot import name '_get_function_stack_at' from 'torch._C'
```

문제를 일으킨 형태:

```bash
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:/usr/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu/tegra:${LD_LIBRARY_PATH:-}"
```

NLU용 PyTorch 실행 시에는 우선 `LD_LIBRARY_PATH`를 제거한다.

```bash
env -u LD_LIBRARY_PATH PYTHONNOUSERSITE=1 python ...
```

## 7. L4T R36.4.7 NvMap 오류

PyTorch가 CUDA 장치를 정상 감지한 뒤 첫 CUDA 메모리 할당에서 다음 오류가 발생했다.

```text
NvMapMemAllocInternalTagged: error 12
RuntimeError: NVML_SUCCESS == r INTERNAL ASSERT FAILED
```

작은 FP16 텐서에서도 재현되어 NLU 모델 크기 문제가 아니라 L4T R36.4.7의 CUDA/NvMap 문제로 판단했다.

JetPack을 6.2.2, L4T를 R36.5로 업데이트한 뒤 같은 CUDA 텐서 테스트가 정상 동작했다.

## 8. 최종 CUDA 검증

```bash
cd ~/pumpkin
source .venv-nlu/bin/activate

env -u LD_LIBRARY_PATH \
  PYTHONNOUSERSITE=1 \
  python - <<'PY'
import torch

print("Torch:", torch.__version__)
print("Built CUDA:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name(0))

x = torch.randn(
    (512, 512),
    device="cuda",
    dtype=torch.float16,
)
y = x @ x
torch.cuda.synchronize()

print("Tensor device:", y.device)
print("Tensor dtype:", y.dtype)
print("Tensor result:", y.mean().item())
print("CUDA 기본 연산 성공")
PY
```

최종 결과:

```text
Torch: 2.8.0
Built CUDA: 12.6
CUDA available: True
GPU: Orin
Tensor device: cuda:0
Tensor dtype: torch.float16
CUDA 기본 연산 성공
```

## 9. NLU 단독 GPU 추론 검증

```bash
cd ~/pumpkin
source .venv-nlu/bin/activate
source /opt/ros/humble/setup.bash
source ~/pumpkin/ros2_ws/install/setup.bash

env -u LD_LIBRARY_PATH \
  PYTHONNOUSERSITE=1 \
  PUMPKIN_PROJECT_ROOT="$HOME/pumpkin" \
  PUMPKIN_NLU_DEVICE=cuda \
  python -m nlu.predict_structure_b \
  "아이스 아메리카노 두 잔 주세요"
```

최종 결과:

```json
{
  "intent": "ORDER",
  "intent_confidence": 0.9999,
  "order_status": "VALID",
  "items": [
    {
      "menu": "아메리카노",
      "temperature": "ICE",
      "quantity": 2,
      "missing_slots": []
    }
  ],
  "needs_reprompt": false,
  "device": "cuda",
  "robot_response": "아이스 아메리카노 2잔 맞으신가요?"
}
```

따라서 koELECTRA + Item Query Decoder 기반 Structure B NLU가 Jetson GPU에서 정상적으로 추론되는 것을 확인했다.

## 10. 현재 환경 구조

```text
~/pumpkin/.venv
├── ROS2 통합 노드
├── Faster-Whisper
└── CTranslate2 CUDA

~/pumpkin/.venv-nlu
├── PyTorch 2.8.0 CUDA 12.6
├── Transformers 4.40.2
├── koELECTRA
└── Structure B NLU
```

## 11. 주의사항

1. `.venv-nlu`에서 `pip install torch`, `pip install torch==2.2.2`를 실행하지 않는다.
2. `.venv-nlu`에서 저장소 루트의 기존 `requirements.txt`를 그대로 설치하지 않는다. CPU용 PyTorch로 덮어쓸 수 있다.
3. NLU 실행 시 사용자 전역 패키지를 차단하기 위해 `PYTHONNOUSERSITE=1`을 유지한다.
4. NLU 실행 시 시스템 PyTorch 공유 라이브러리가 섞이지 않도록 불필요한 `LD_LIBRARY_PATH`를 넣지 않는다.
5. JetPack 6.2.1/L4T R36.4.7로 되돌리지 않는다. 첫 CUDA 메모리 할당에서 NvMap 오류가 재발할 수 있다.
6. 시스템 Python과 기존 `.venv`의 CPU용 PyTorch는 NLU용 CUDA PyTorch로 간주하지 않는다.

## 12. 현재 결론

최종적으로 JetPack 6.2.2, L4T R36.5, CUDA 12.6, PyTorch 2.8.0 조합에서 CUDA 기본 연산과 Structure B NLU 단독 GPU 추론이 모두 성공했다.

기존 문제의 원인은 한 가지가 아니라 다음 세 가지가 순차적으로 겹친 것이었다.

```text
1. 일반 PyPI CPU 전용 PyTorch 2.2.2
2. LD_LIBRARY_PATH로 인한 PyTorch 공유 라이브러리 혼합
3. L4T R36.4.7의 첫 CUDA 메모리 할당/NvMap 오류
```

다음 단계는 `.venv-nlu`의 NLU 노드를 기존 ROS2/Faster-Whisper 실행 스크립트와 분리 실행하여 전체 음성 주문 파이프라인의 동시 메모리 사용량과 안정성을 검증하는 것이다.
