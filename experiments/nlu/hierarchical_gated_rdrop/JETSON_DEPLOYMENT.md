# Jetson Orin Nano에 4번째 NLU 모델 배포

> [!NOTE]
> 이 문서는 `hierarchical_gated_multitask_koelectra_rdrop` 모델을 사용하던 **과거 배포 기록**입니다. 현재 production 주문 STT는 ROS2의 `robot_controller.stt_node_unbiased`를 사용합니다. 당시 standalone STT 코드는 `experiments/voice/legacy_stt/`로 보관 위치를 옮겼습니다.

대상 모델은 `hierarchical_gated_multitask_koelectra_rdrop`입니다. 한 번의 추론으로 `intent`, `menu`, `temperature`, `quantity`를 출력합니다.

## 0. 필요한 파일

Colab 학습 결과에서 아래 파일을 준비합니다.

```text
experiment_results/
├── best_model.pt
├── label_maps.json
├── tokenizer/
└── encoder_config/   # 새 노트북에서 생성되는 경우 함께 복사, 없어도 당시 추론 코드는 동작
```

실제 배포에 평가 CSV와 JSON은 필요하지 않습니다.

## 1. Jetson에서 프로젝트 코드 받기

PR이 아직 병합되지 않았다면:

```bash
cd ~/pumpkin
git fetch origin
git switch feature/hierarchical-gated-rdrop-nlu
git pull
```

PR이 `main`에 병합된 뒤라면:

```bash
cd ~/pumpkin
git switch main
git pull
```

## 2. JetPack 및 PyTorch 확인

Jetson에서 실행합니다.

```bash
cat /etc/nv_tegra_release
dpkg-query --show nvidia-jetpack || true
python3 --version
python3 -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"
```

`torch.cuda.is_available()`이 `True`여야 GPU 추론이 가능합니다.

Jetson에서는 저장소 루트의 데스크톱용 PyTorch 고정을 그대로 설치하지 않고, 설치된 JetPack 버전에 맞는 NVIDIA Jetson용 PyTorch를 사용합니다.

## 3. 추론용 Python 환경

NVIDIA PyTorch가 시스템 Python에 설치돼 있다면 시스템 패키지를 볼 수 있는 가상환경을 만듭니다.

```bash
cd ~/pumpkin
python3 -m venv --system-site-packages .venv-jetson
source .venv-jetson/bin/activate
python3 -m pip install --upgrade pip
pip install -r nlu/requirements-jetson-inference.txt
```

설치 확인:

```bash
python3 -c "import torch, transformers; print(torch.__version__); print(transformers.__version__); print(torch.cuda.is_available())"
```

## 4. Mac에서 모델을 Jetson으로 복사

먼저 Jetson에 목적지 폴더를 만듭니다. 아래 사용자 이름, IP, 경로는 실제 환경에 맞게 변경합니다.

```bash
ssh jetson@192.168.0.42 \
  "mkdir -p /home/jetson/pumpkin/nlu/saved_models/hierarchical_gated_rdrop"
```

Mac에서 `experiment_results`가 있는 폴더로 이동한 뒤 복사합니다.

```bash
scp experiment_results/best_model.pt \
    experiment_results/label_maps.json \
    jetson@192.168.0.42:/home/jetson/pumpkin/nlu/saved_models/hierarchical_gated_rdrop/

scp -r experiment_results/tokenizer \
    jetson@192.168.0.42:/home/jetson/pumpkin/nlu/saved_models/hierarchical_gated_rdrop/
```

`encoder_config` 폴더가 있다면 함께 복사합니다.

```bash
scp -r experiment_results/encoder_config \
    jetson@192.168.0.42:/home/jetson/pumpkin/nlu/saved_models/hierarchical_gated_rdrop/
```

최종 구조:

```text
pumpkin/
└── nlu/
    └── saved_models/
        └── hierarchical_gated_rdrop/
            ├── best_model.pt
            ├── label_maps.json
            ├── tokenizer/
            └── encoder_config/   # 선택
```

## 5. Jetson 환경 및 모델 검사

```bash
cd ~/pumpkin
source .venv-jetson/bin/activate
bash scripts/check_jetson_nlu.sh
```

당시 정상 출력 예시는 다음과 같습니다.

```json
{
  "intent": "ORDER",
  "order": {
    "menu": "...",
    "temperature": "...",
    "quantity": 2
  },
  "device": "cuda"
}
```

`device`가 `cpu`로 나오면 PyTorch CUDA 연결을 다시 확인합니다.

## 6. 속도 측정

```bash
python3 -m nlu.benchmark_multitask --warmup 10 --runs 50
```

CPU와 GPU를 비교하려면:

```bash
python3 -m nlu.benchmark_multitask --device cpu --warmup 5 --runs 20
python3 -m nlu.benchmark_multitask --device cuda --warmup 10 --runs 50
```

## 7. 과거 standalone STT 통합 재현

당시 사용한 standalone STT 코드는 현재 archive로 이동했습니다.

```bash
python3 experiments/voice/legacy_stt/main.py
```

이 명령은 **과거 실험 재현용**입니다. 현재 로봇의 production 음성 주문 파이프라인을 실행하려면 저장소 루트에서 다음을 사용합니다.

```bash
bash scripts/run_ros_voice_nodes.sh
```

현재 production STT 진입점은 `robot_controller.stt_node_unbiased`입니다.

## 8. 자주 발생하는 오류

### `No module named torch`

JetPack에 맞는 NVIDIA Jetson용 PyTorch가 설치되지 않은 상태입니다. 일반 PC용 PyTorch를 임의로 설치하지 말고 JetPack 버전을 먼저 확인합니다.

### `torch.cuda.is_available() == False`

PyTorch와 JetPack/CUDA 조합이 맞지 않거나 CPU용 PyTorch가 설치된 상태일 수 있습니다.

### `Missing: .../best_model.pt`

모델 복사 경로가 잘못됐습니다. 당시 모델의 기준 위치는 다음과 같습니다.

```text
nlu/saved_models/hierarchical_gated_rdrop/best_model.pt
```

### 모델 로딩 중 메모리 부족

다른 AI 프로세스를 종료하고 다시 실행합니다. 당시 추론 배치 크기는 1이며 `max_length=64`로 사용했습니다.

### 첫 실행에서 인터넷 연결 오류

당시 `predict_multitask.py`는 koELECTRA-small 구조 설정을 내장하고 전체 가중치를 `best_model.pt`에서 복원하도록 구성했습니다. tokenizer와 checkpoint가 완전하게 복사됐는지 확인합니다.
