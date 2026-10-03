# Pumpkin TOD · Qwen3-0.6B LoRA Training

이 폴더는 `Qwen/Qwen3-0.6B`를 Pumpkin TOD Student v1로 LoRA SFT하기 위한 학습 파이프라인이다.

## 최종 Student v1 baseline

학교 학습 서버에서 실제 확인한 환경을 기준으로 첫 baseline을 아래처럼 고정한다.

- GPU: NVIDIA TITAN Xp 12 GB × 3 (`physical GPU 1,2,3` 사용, GPU 0 사용 금지)
- Python: 3.10.13
- Student: `Qwen/Qwen3-0.6B`
- Method: LoRA, QLoRA 사용 안 함
- Precision: FP16 (`bf16=false`)
- Teacher 없음
- 외부 데이터 없음
- Pumpkin train 25,985 / validation 2,887 / fixed test 1,507
- max length: 512
- LoRA r=32 / alpha=64 / dropout=0.05
- epoch: 1부터 시작
- per-device train batch: 2
- gradient accumulation: 5
- 3 GPU effective batch: `2 × 5 × 3 = 30`
- gradient checkpointing: OFF
- DDP `find_unused_parameters`: OFF
- non-thinking (`enable_thinking=False`)
- assistant answer에만 loss 적용
- validation으로 best checkpoint 선택
- test는 모델/하이퍼파라미터 결정 후 마지막에 평가

첫 1 epoch 후 validation 결과를 보고 부족하면 저장된 checkpoint에서 추가 학습한다. 처음부터 무조건 3 epoch를 돌리지 않는다.

## 1. 왜 QLoRA가 아닌가

Qwen3-0.6B는 TITAN Xp에서 FP16 base model 로드 시 약 1.1 GB 수준으로 확인되었고, LoRA 학습도 12 GB VRAM 안에 들어간다. 현재 병목은 VRAM 부족이 아니라 TITAN Xp의 연산 속도이므로 4-bit QLoRA로 바꿔도 optimizer step 수가 줄지 않는다.

따라서 첫 baseline은 일반 LoRA + FP16으로 학습하고, Jetson 배포 단계에서 필요하면 merge 후 별도로 양자화한다.

```text
Qwen3-0.6B FP16 + LoRA
        ↓
validation / test
        ↓
LoRA merge
        ↓
Q4/Q5/Q8 등 배포용 양자화
        ↓
Jetson Orin Nano
```

## 2. 학습 서버 작업 폴더

학교 서버에서는 GitHub 개인 SSH 인증을 남기지 않고 필요한 파일만 Mac에서 전송하는 방식을 사용할 수 있다.

권장 구조:

```text
~/pumpkin-tod-train/
├── .venv/
├── .cache/
│   └── huggingface/
├── data/tod/qwen/
├── experiments/tod_slm/training/
├── scripts/
└── outputs/
```

환경 활성화 예:

```bash
cd ~/pumpkin-tod-train
source .venv/bin/activate

export HF_HOME="$HOME/pumpkin-tod-train/.cache/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
export PYTHONNOUSERSITE=1
```

## 3. Python / PyTorch

현재 학교 서버에서 확인한 기준:

```text
NVIDIA driver: 535.230.02
NVIDIA-SMI CUDA compatibility: 12.2
Python: 3.10.13
GPU: TITAN Xp 12 GB × 4
```

PyTorch는 서버 환경에 맞는 CUDA wheel을 먼저 설치하고, 그 다음 학습 requirements를 설치한다.

```bash
python -m pip install -U pip
pip install -r experiments/tod_slm/training/requirements.txt
```

GPU 확인:

```bash
python - <<'PY'
import torch
print('torch:', torch.__version__)
print('cuda:', torch.version.cuda)
print('available:', torch.cuda.is_available())
print('gpus:', torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(i, torch.cuda.get_device_name(i))
PY
```

## 4. GPU 0 사용 금지

학교 서버에서는 physical GPU 0을 사용하지 않는다.

3 GPU 학습 시:

```bash
export CUDA_VISIBLE_DEVICES=1,2,3
```

이렇게 설정하면 PyTorch 내부 번호는 다시 매겨진다.

```text
PyTorch cuda:0 = physical GPU 1
PyTorch cuda:1 = physical GPU 2
PyTorch cuda:2 = physical GPU 3
```

## 5. Token length preflight

학습 전에 Qwen3 tokenizer/chat template로 실제 길이를 전부 측정한다.

```bash
python experiments/tod_slm/training/inspect_token_lengths.py
```

실제 측정 결과:

```text
train max       480
validation max  479
test max        499
p99 overall     481
recommended     512
```

따라서 기본 config는 `max_length=512`, `overlength_policy=error`다. 현재 데이터는 한 샘플도 자르지 않고 512 안에 들어간다.

결과 저장 위치:

```text
outputs/tod_slm/qwen3_0.6b_lora_v1/preflight/token_lengths.json
```

## 6. 3 GPU 첫 baseline 실행

권장 실행 명령:

```bash
CUDA_VISIBLE_DEVICES=1,2,3 \
USE_ACCELERATE=1 \
NUM_PROCESSES=3 \
MIXED_PRECISION=fp16 \
bash scripts/train_tod_qwen_lora.sh
```

스크립트는 먼저 token-length preflight를 실행하고, 통과하면 `accelerate launch`로 3개 프로세스를 시작한다.

정상 시작 시 다음을 확인한다.

```text
WORLD_SIZE=3
effective batch=30
```

`nvidia-smi`에서는 GPU 0에 학습 Python 프로세스가 없어야 하고 GPU 1,2,3에 각각 학습 프로세스가 보여야 한다.

## 7. 속도 확인 기록

실제 서버에서 동일한 데이터/config 계열로 확인한 대략적인 차이:

```text
TITAN Xp 1장: 약 39.6 s/optimizer step
TITAN Xp 3장: 약 12.6 s/optimizer step
```

3 GPU가 거의 3배 가까이 빨라졌다. 따라서 본 baseline은 GPU 1,2,3 세 장을 사용한다.

## 8. LoRA 설정

`configs/qwen3_0.6b_lora_v1.yaml`:

```text
r=32
alpha=64
dropout=0.05
```

Target modules:

```text
q_proj
k_proj
v_proj
o_proj
gate_proj
up_proj
down_proj
```

첫 Student v1 결과를 얻기 전에는 r/LR을 여러 조합으로 동시에 바꾸지 않는다.

## 9. 왜 1 epoch부터 시작하는가

train 25,985개 전체를 한 번 모두 보는 1 epoch 자체가 정상적인 SFT 실험이다. 먼저 1 epoch를 수행하고 validation을 본 뒤 다음을 결정한다.

```text
1 epoch Student v1
        ↓
validation 평가
        ↓
충분함 → test 평가
부족함 → checkpoint에서 추가 학습
```

같은 run을 이어가는 경우 `--resume-from-checkpoint`를 사용한다. 예를 들어 총 2 epoch까지 이어가려면 config의 `epochs`를 2로 변경한 뒤 1 epoch에서 저장된 checkpoint를 지정한다.

```bash
CUDA_VISIBLE_DEVICES=1,2,3 \
USE_ACCELERATE=1 \
NUM_PROCESSES=3 \
MIXED_PRECISION=fp16 \
bash scripts/train_tod_qwen_lora.sh \
  --resume-from-checkpoint outputs/tod_slm/qwen3_0.6b_lora_v1/checkpoints/checkpoint-XXXX
```

새 데이터나 teacher augmentation을 추가해 Student v2를 만드는 경우에는 기존 데이터도 함께 섞어 catastrophic forgetting을 줄이는 것을 원칙으로 한다.

## 10. 학습 구조

Qwen chat row는:

```text
system → user → assistant
```

구조다.

`train_lora.py`는 같은 Qwen3 chat template를 이용해 tokenization하고:

```text
SYSTEM tokens     → labels = -100
USER tokens       → labels = -100
ASSISTANT tokens  → 실제 labels
```

로 만들어 assistant target에만 loss를 준다.

Qwen3 baseline은 항상:

```python
enable_thinking=False
```

로 chat template를 적용한다.

## 11. 저장 구조

학습 결과는 Git에 넣지 않는다.

```text
outputs/tod_slm/qwen3_0.6b_lora_v1/
├── run_config.yaml
├── run_metadata.json
├── git_commit.txt
├── training_summary.json
├── preflight/
├── checkpoints/
├── best_adapter/
├── logs/
├── evaluation/
└── merged_model/
```

`save_total_limit=3`으로 중간 checkpoint가 무한히 쌓이지 않게 한다. `load_best_model_at_end=true`로 validation loss 기준 best checkpoint를 선택한 뒤 `best_adapter/`에 별도 저장한다.

Git repository가 아닌 파일전송형 학습 서버에서는 `git_commit.txt`가 `unknown`일 수 있으며 학습 오류가 아니다.

## 12. Validation 평가

학습 후 기본 평가:

```bash
bash scripts/eval_tod_qwen.sh
```

기본값은 validation이다.

주요 지표:

```text
JSON Valid Rate
Intent Accuracy
Order Status Accuracy
Decision Accuracy
Response Key Accuracy
FSM State Accuracy
State Exact Match
State Slot Precision / Recall / F1
Utterance Items Exact Match
Hallucinated Slot Rate
Response Exact Match
```

`Hallucinated Slot Rate`는 gold `utterance_items`에서 사용자가 말하지 않은 슬롯이 null인데 모델이 값을 생성한 경우를 센다.

## 13. 고정 Test 평가

validation 결과와 모델 선택이 모두 끝난 뒤 한 번 평가한다.

```bash
SPLIT=test bash scripts/eval_tod_qwen.sh
```

test 결과를 보고 LoRA r, learning rate, epoch를 다시 조절하면 test leakage가 생긴다. 모델 선택은 validation으로만 한다.

## 14. LoRA merge

Jetson 배포/양자화 전 base + adapter를 하나의 Hugging Face 모델 디렉터리로 합칠 때:

```bash
bash scripts/merge_tod_qwen_lora.sh
```

기본 출력:

```text
outputs/tod_slm/qwen3_0.6b_lora_v1/merged_model/
```

merge는 학습 직후 필수는 아니다. 먼저 adapter 상태로 validation/test 평가를 완료한다.

## 15. 서버 경고 정리

학교 서버에서 반복적으로 확인된 경고:

```text
ERROR: ld.so: object '/usr/local/lib/libaudit.so' from /etc/ld.so.preload ...
```

서버 전역 `/etc/ld.so.preload` 설정 문제이며 현재 학습 자체와는 별개다. 공용 서버이므로 임의로 sudo 수정하지 않는다.

또한 kernel 5.4 환경에서는 Hugging Face/Accelerate가 kernel 5.5 이상을 권장한다는 경고가 출력될 수 있다. 실제 hang이 발생하면 서버 관리자와 kernel 업그레이드를 상의한다.

## 16. Git에 올릴 것 / 올리지 않을 것

Git에 올릴 것:

```text
학습 코드
config
평가 코드
작은 metrics 요약(필요 시 선별)
```

Git에 올리지 않을 것:

```text
checkpoint
best_adapter binary
merged model
TensorBoard logs
Hugging Face cache
대규모 prediction/log
```

현재 `.gitignore`에서 `outputs/` 전체를 제외한다.
