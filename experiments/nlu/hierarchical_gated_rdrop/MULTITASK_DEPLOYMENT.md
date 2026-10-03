# Hierarchical Gated Multi-Task NLU 적용 방법

> [!NOTE]
> 이 문서는 `hierarchical_gated_multitask_koelectra_rdrop` 모델을 적용하던 **과거 실험·배포 기록**입니다. 현재 production 주문 STT는 ROS2의 `robot_controller.stt_node_unbiased`를 사용합니다. 당시 standalone STT 코드는 `experiments/voice/legacy_stt/`에 보관합니다.

이 문서는 Colab 노트북에서 학습한 `hierarchical_gated_multitask_koelectra_rdrop` 모델을 Pumpkin 저장소와 당시 STT 코드에 연결했던 방법을 설명합니다.

## 1. 노트북을 저장소에 추가

다운로드한 노트북을 아래 경로에 넣습니다.

```text
notebooks/hierarchical_gated_multitask_koelectra_rdrop.ipynb
```

당시 브랜치 작업 예시:

```bash
git checkout feature/hierarchical-gated-rdrop-nlu
git add notebooks/hierarchical_gated_multitask_koelectra_rdrop.ipynb
git commit -m "Add hierarchical gated multi-task training notebook"
git push
```

## 2. Colab에서 학습

노트북을 Colab에서 열고 다음 파일을 업로드합니다.

```text
train.csv
valid.csv
test.csv
```

전체 셀을 실행하면 다음 파일이 포함된 `experiment_results.zip`이 생성됩니다.

```text
experiment_results/
├── best_model.pt
├── tokenizer/
├── experiment_config.json
├── label_maps.json
├── validation_history.csv
├── test_metrics.json
├── test_predictions.csv
├── test_errors.csv
└── class_metrics.csv
```

## 3. 배포에 필요한 파일만 복사

압축을 푼 뒤 아래 세 항목을 저장소 작업 폴더에 복사합니다.

```text
nlu/saved_models/hierarchical_gated_rdrop/
├── best_model.pt
├── label_maps.json
└── tokenizer/
```

예시:

```bash
mkdir -p nlu/saved_models/hierarchical_gated_rdrop
cp experiment_results/best_model.pt nlu/saved_models/hierarchical_gated_rdrop/
cp experiment_results/label_maps.json nlu/saved_models/hierarchical_gated_rdrop/
cp -R experiment_results/tokenizer nlu/saved_models/hierarchical_gated_rdrop/
```

`experiment_config.json`, 평가 CSV와 JSON은 실험 기록용이므로 별도 보관할 수 있습니다.

## 4. 모델 파일 Git 관리 주의

현재 `.gitignore`는 모델 가중치 계열 파일과 `nlu/saved_models/`를 Git에서 제외합니다.

```text
*.pt
*.pth
*.onnx
*.engine
nlu/saved_models/
```

권장 방식은 다음과 같습니다.

1. 소스 코드와 노트북만 GitHub에 저장합니다.
2. `experiment_results.zip` 또는 배포용 모델 폴더는 별도 저장소에 보관합니다.
3. Jetson 또는 팀원 PC에 모델 폴더를 직접 복사합니다.

가중치까지 Git으로 관리해야 한다면 일반 Git 대신 Git LFS를 사용하고 팀원 모두가 Git LFS를 설치해야 합니다.

## 5. 텍스트 한 문장 테스트

저장소 루트에서 실행합니다.

```bash
python -m nlu.predict_multitask "아이스 카페라떼 두 잔 주세요"
```

threshold를 직접 지정할 수도 있습니다. threshold는 test 결과를 반복 확인해 정하지 말고 validation 결과 또는 실제 서비스 검증 세트로 정합니다.

```bash
python -m nlu.predict_multitask \
  "아이스 카페라떼 두 잔 주세요" \
  --intent-threshold 0.5 \
  --slot-threshold 0.5
```

당시 출력 예시:

```json
{
  "text": "아이스 카페라떼 두 잔 주세요",
  "intent": "ORDER",
  "intent_confidence": 0.97,
  "order": {
    "menu": "카페라떼",
    "temperature": "ICE",
    "quantity": 2,
    "confidence": {
      "menu": 0.96,
      "temperature": 0.99,
      "quantity": 0.98
    },
    "missing_slots": [],
    "needs_reprompt": false
  },
  "needs_reprompt": false,
  "robot_response": "아이스 카페라떼 2잔 맞으신가요?"
}
```

실제 class 문자열은 학습 CSV의 class 값과 동일하게 출력됩니다.

## 6. Python 코드에서 사용

```python
from nlu import HierarchicalNLUPredictor

predictor = HierarchicalNLUPredictor(
    "nlu/saved_models/hierarchical_gated_rdrop"
)

stt_text = "아이스 카페라떼 두 잔 주세요"
result = predictor.predict(stt_text)

print(result["intent"])
print(result["order"])
print(result["robot_response"])
```

## 7. 과거 standalone STT와 연결

당시 standalone STT는 모델 폴더를 확인해 NLU와 연결하는 실험 진입점으로 사용했습니다. 해당 코드는 현재 다음 위치로 archive했습니다.

```text
experiments/voice/legacy_stt/
```

과거 흐름을 재현하려면:

```bash
python experiments/voice/legacy_stt/main.py
```

이 명령은 **현재 production 실행법이 아닙니다.** 현재 로봇 음성 주문 파이프라인은 다음 런처를 사용합니다.

```bash
bash scripts/run_ros_voice_nodes.sh
```

현재 production STT 진입점은 `robot_controller.stt_node_unbiased`입니다.

## 8. 패키지 버전

Colab 노트북은 학습 환경 버전을 `experiment_config.json`에 기록합니다. 배포 환경에서 문제가 생기면 우선 이 파일에 기록된 `torch`, `transformers` 버전과 당시 저장소 환경을 비교합니다.

Jetson에서는 일반 PC용 `torch` wheel 대신 JetPack 버전에 맞는 NVIDIA PyTorch 패키지를 사용해야 할 수 있으므로, Jetson 배포 시에는 JetPack과 호환되는 PyTorch를 우선 확인합니다.
