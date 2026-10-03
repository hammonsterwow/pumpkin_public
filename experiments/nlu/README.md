# NLU Experiments Archive

이 디렉터리는 Pumpkin NLU 모델의 **과거 실험 코드와 문서**를 보관하기 위한 공간입니다.

> 이곳의 문서는 현재 실행 방법을 설명하는 운영 문서가 아닙니다.  
> 현재 프로젝트는 `structure_b_item_query_decoder` 계열 모델만 사용합니다.

## 현재 사용 모델

- 모델 계열: Structure B
- 구조: koELECTRA Encoder + Item Query Decoder
- 주요 기능:
  - 주문 의도 분류
  - 복수 메뉴 주문 분리
  - 메뉴·온도·수량 추출
  - 누락 옵션을 임의로 채우지 않고 재질문 대상으로 처리

현재 모델의 설치·실행·배포 방법은 추후 `nlu/README.md` 하나에만 최신 상태로 관리합니다.

## 과거 NLU 문서

아래 문서는 이전 모델 구조를 설명하는 기록입니다.

| 문서 | 대상 모델 | 상태 |
|---|---|---|
| `nlu/README.md` | 독립 koELECTRA Intent Classifier | Legacy |
| `nlu/MULTITASK_DEPLOYMENT.md` | Hierarchical Gated Multi-Task + R-Drop | Legacy |
| `nlu/JETSON_DEPLOYMENT.md` | 4번째 멀티태스크 모델 Jetson 배포 | Legacy |

위 문서의 명령어, 모델 경로, API 응답 형식은 현재 Structure B 모델과 다를 수 있으므로 그대로 사용하지 않습니다.

## 권장 보관 구조

과거 모델별 코드와 문서는 다음 형식으로 정리합니다.

```text
experiments/
└── nlu/
    ├── README.md
    ├── intent_classifier/
    │   └── README.md
    ├── shared_multitask/
    │   └── README.md
    ├── hierarchical_gated_rdrop/
    │   └── README.md
    └── structure_b_item_query_decoder/
        └── README.md
```

현재 운영 코드와 과거 실험 코드를 구분하기 위해 다음 원칙을 적용합니다.

1. `nlu/`에는 현재 서비스에서 사용하는 코드와 최신 문서만 둡니다.
2. 더 이상 사용하지 않는 학습·추론 코드는 `experiments/nlu/<모델명>/`으로 이동합니다.
3. 과거 배포 문서도 해당 모델 실험 폴더로 이동합니다.
4. 모델 가중치(`*.pt`, `*.pth`, `*.onnx`, `*.engine`)는 Git에 올리지 않습니다.
5. 실험 문서 첫 부분에는 반드시 `Legacy` 또는 `Archived` 상태를 표시합니다.

## 실험 문서 작성 양식

새로운 실험 기록은 다음 양식을 사용합니다.

```markdown
# 모델 또는 실험 이름

- 상태: Experimental / Archived
- 실험 날짜:
- 담당자:
- 기반 모델:
- 데이터셋:
- 목적:

## 모델 구조

## 학습 방법

## 평가 결과

## 장점

## 한계

## 현재 모델에 반영된 내용
```

## 문서 관리 기준

- 현재 사용법은 `nlu/README.md`에만 작성합니다.
- 과거 모델 비교와 학습 과정은 이 디렉터리에 기록합니다.
- 동일한 실행 방법을 여러 README에 중복 작성하지 않습니다.
- 모델 구조나 실행 명령이 바뀌면 운영 README를 먼저 수정합니다.
