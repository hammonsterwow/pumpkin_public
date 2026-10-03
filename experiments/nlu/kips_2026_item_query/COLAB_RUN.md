# Google Colab 실행 코드

아래 순서대로 Colab 셀에 실행하면 됩니다. 저장소가 private이므로 Colab Secrets에 `GITHUB_TOKEN`을 먼저 등록하는 방식을 권장합니다.

## 0. Colab Secrets 준비

Colab 왼쪽의 열쇠 아이콘(Secrets)에서 다음 값을 추가합니다.

```text
Name: GITHUB_TOKEN
Value: 본인 GitHub Personal Access Token
```

토큰은 이 private repository를 읽을 수 있는 권한만 있으면 됩니다.

## 1. 패키지 설치 및 repository clone

```python
from google.colab import userdata
import os
import subprocess
from pathlib import Path

TOKEN = userdata.get('GITHUB_TOKEN')
if not TOKEN:
    raise RuntimeError('Colab Secrets에 GITHUB_TOKEN을 등록하세요.')

REPO_DIR = Path('/content/pumpkin')
if not REPO_DIR.exists():
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    clone_url = f'https://{TOKEN}@github.com/yulllee0829/pumpkin.git'
    subprocess.run(
        ['git', 'clone', '--depth', '1', clone_url, str(REPO_DIR)],
        check=True,
        env=env,
    )

os.chdir(REPO_DIR)
subprocess.run([
    'pip', 'install', '-q', '-U',
    'transformers==4.46.3',
    'scikit-learn==1.6.1',
    'pandas>=2.0',
    'tqdm>=4.66',
    'sentencepiece==0.2.0',
], check=True)

print('repo:', REPO_DIR)
```

> 주의: clone URL에 token이 포함되므로 notebook을 다른 사람과 공유할 때 해당 셀의 출력이나 실행 기록에 token이 노출되지 않았는지 확인하세요. 가능하면 Colab Secrets를 사용하고 notebook에는 token 값을 직접 적지 마세요.

## 2. GPU 확인

```python
import torch

print('cuda:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('GPU:', torch.cuda.get_device_name(0))
```

GPU가 `False`라면 Colab 메뉴에서 **런타임 → 런타임 유형 변경 → GPU**를 선택하세요.

## 3. 메인 논문 실험 실행

아래 명령은 canonical dataset을 repository의 `data/`에서 그대로 사용합니다.

- `data/structure_b_train_valid.jsonl` — 22,512개
- `data/structure_b_test.jsonl` — 1,507개

```python
import subprocess

subprocess.run([
    'python', '-m',
    'experiments.nlu.kips_2026_item_query.run_all',
    '--mode', 'main',
    '--result-dir', '/content/kips_2026_results',
], check=True)
```

실행되는 모델은 다음 세 개입니다.

```text
M0  KoELECTRA-small + Independent Item Heads
M1  KoELECTRA-small + Item Query Decoder
M2  M1 + differential LR + multi-order oversampling + weighted loss
```

각 모델을 seed `42`, `43`, `44`로 실행하므로 총 **9 training runs**입니다.

## 4. 메인 결과 확인

```python
import pandas as pd

main_runs = pd.read_csv('/content/kips_2026_results/main_runs.csv')
main_summary = pd.read_csv('/content/kips_2026_results/main_summary.csv')
paper_table = pd.read_csv('/content/kips_2026_results/paper_main_table.csv')

display(main_runs)
display(main_summary)
display(paper_table)
```

논문에서는 `paper_main_table.csv`의 아래 지표를 중심으로 사용합니다.

```text
1-item EM
2-item EM
3-item EM
Multi EM
Overall Order EM
Intent Macro F1
```

## 5. Ablation 빠른 실행 — seed 42 하나

Ablation은 최종 모델의 각 개선 요소가 실제로 성능 향상에 기여했는지 확인하는 실험입니다.

```text
A0 = M1 Item Query 기본형
A1 = A0 + differential LR
A2 = A1 + multi-order oversampling
A3 = A2 + weighted loss = M2
```

다음 명령은 seed 42 하나만 사용합니다.

```python
subprocess.run([
    'python', '-m',
    'experiments.nlu.kips_2026_item_query.run_all',
    '--mode', 'ablation',
    '--ablation-seeds', '42',
    '--result-dir', '/content/kips_2026_results',
], check=True)
```

이미 메인 실험에서 `M1 seed42`, `M2 seed42`가 완료되어 있으면 해당 run의 `result.json`을 재사용합니다. 따라서 새로 학습해야 하는 것은 주로 A1, A2입니다.

## 6. 논문용 Ablation — 3 seeds

빠른 실험 결과가 합리적이고 논문에 ablation 표를 넣기로 했다면 다음과 같이 다시 실행합니다.

```python
subprocess.run([
    'python', '-m',
    'experiments.nlu.kips_2026_item_query.run_all',
    '--mode', 'ablation',
    '--ablation-seeds', '42,43,44',
    '--result-dir', '/content/kips_2026_results',
], check=True)
```

결과는 다음에서 확인합니다.

```python
ablation = pd.read_csv('/content/kips_2026_results/ablation_summary.csv')
display(ablation)
```

## 7. R-Drop까지 추가하고 싶을 때

R-Drop은 선택 사항입니다. 같은 입력을 dropout 상태에서 두 번 forward하므로 학습 계산량이 증가합니다.

```python
subprocess.run([
    'python', '-m',
    'experiments.nlu.kips_2026_item_query.run_all',
    '--mode', 'ablation',
    '--ablation-seeds', '42',
    '--rdrop',
    '--result-dir', '/content/kips_2026_results',
], check=True)
```

이 설정은 다음을 추가합니다.

```text
A4 = A3 + R-Drop
```

A4가 유의미하게 좋아질 때만 3 seeds로 확장하는 것을 권장합니다.

## 8. 결과 다운로드

```python
from google.colab import files
files.download('/content/kips_2026_results.zip')
```

`run_all.py`는 종료 시 자동으로 `kips_2026_results.zip`을 생성합니다.

## 실험 순서 요약

```text
[1] Main experiment
M0 × seeds 42/43/44
M1 × seeds 42/43/44
M2 × seeds 42/43/44
= 9 runs

        ↓

[2] Main 결과 확인
1-item / 2-item / 3-item / Overall EM

        ↓

[3] Ablation screening
M1 → +Diff LR → +Oversampling → +Weighted Loss
seed 42

        ↓

[4] 논문에 ablation을 넣을 가치가 있으면
Ablation 3 seeds

        ↓

[5] 선택
+ R-Drop
```

## Test set 사용 원칙

이 실험 폴더의 configuration은 사전에 고정되어 있습니다. `structure_b_test.jsonl` 결과를 보고 learning rate, loss weight, oversampling ratio를 다시 바꾸면 test leakage가 됩니다.

설정 변경이 필요하면 validation 결과만 보고 결정한 뒤, 새로운 실험 계획을 먼저 고정하고 최종 test를 다시 수행하세요.
