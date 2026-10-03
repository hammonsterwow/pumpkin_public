# Pumpkin 웹 실행 팀원 매뉴얼

이 문서는 같은 `yulllee0829/pumpkin` 저장소를 공유하는 팀원이 관리자 POS 웹을 로컬 컴퓨터에서 실행하는 방법을 설명합니다.

현재 웹 코드는 `feature/pos-web-integration` 브랜치에 있습니다. PR이 `main`에 병합되기 전까지는 반드시 이 브랜치로 전환해야 합니다.

---

## 1. 준비물

다음 프로그램이 설치되어 있어야 합니다.

- Git
- Node.js와 npm
- Python 3.11 권장

설치 확인:

```bash
git --version
node --version
npm --version
python --version
```

Windows에서 `python` 명령이 동작하지 않으면 `py --version`을 사용합니다.

---

## 2. 저장소를 처음 받는 팀원

### macOS / Linux

```bash
cd ~
git clone https://github.com/yulllee0829/pumpkin.git
cd pumpkin
git fetch origin
git switch --track origin/feature/pos-web-integration
```

### Windows PowerShell

```powershell
cd $HOME
git clone https://github.com/yulllee0829/pumpkin.git
cd pumpkin
git fetch origin
git switch --track origin/feature/pos-web-integration
```

브랜치 확인:

```bash
git branch --show-current
```

정상 출력:

```text
feature/pos-web-integration
```

---

## 3. 저장소를 이미 받은 팀원

저장소 폴더에서 실행합니다.

```bash
cd ~/pumpkin
git fetch origin
git switch feature/pos-web-integration
```

처음 전환하는데 브랜치를 찾지 못하면 다음 명령을 사용합니다.

```bash
git switch --track origin/feature/pos-web-integration
```

최신 코드 받기:

```bash
git pull
```

Windows에서는 `cd ~/pumpkin` 대신 실제 저장 위치로 이동합니다.

예:

```powershell
cd $HOME\pumpkin
```

---

## 4. 웹 화면만 먼저 실행하기 — Mock 모드

실제 ko-ELECTRA 모델 없이 UI와 주문 흐름만 확인할 때 사용합니다.

### macOS / Linux

```bash
cd ~/pumpkin/web
cp -n .env.example .env
npm install
```

`.env` 파일을 열어 다음처럼 설정합니다.

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_API=true
```

웹 실행:

```bash
npm run dev
```

### Windows PowerShell

```powershell
cd $HOME\pumpkin\web
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm install
```

`.env` 내용:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_API=true
```

웹 실행:

```powershell
npm run dev
```

브라우저에서 다음 주소를 엽니다.

```text
http://localhost:3000
```

Mock 모드에서는 Python API 서버를 실행하지 않아도 됩니다.

---

## 5. 실제 Pumpkin 모델과 연결해서 실행하기

실제 모델 연결은 터미널 두 개가 필요합니다.

### 터미널 1 — FastAPI 모델 서버

저장소 루트로 이동합니다.

```bash
cd ~/pumpkin
```

#### macOS / Linux

가상환경 생성 및 실행:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r api/requirements.txt
```

API 실행:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

#### Windows PowerShell

가상환경 생성 및 실행:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r api/requirements.txt
```

API 실행:

```powershell
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API 확인:

```text
http://localhost:8000/health
```

정상 응답:

```json
{
  "status": "ok"
}
```

API 문서:

```text
http://localhost:8000/docs
```

### 터미널 2 — React 웹

```bash
cd ~/pumpkin/web
```

Windows PowerShell:

```powershell
cd $HOME\pumpkin\web
```

`.env` 파일을 다음처럼 설정합니다.

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_API=false
```

실행:

```bash
npm install
npm run dev
```

브라우저:

```text
http://localhost:3000
```

---

## 6. 실제 모델 실행에 필요한 폴더

다음 학습 모델 폴더가 있어야 실제 NLU 분석이 동작합니다.

```text
nlu/saved_models/intent_model/
nlu/saved_models/menu_model/
nlu/saved_models/temperature_model/
nlu/saved_models/quantity_model/
```

모델 파일이 GitHub에 올라와 있지 않으면 모델을 가진 팀원이 별도로 전달해야 합니다. 모델이 없을 때는 `VITE_USE_MOCK_API=true`를 사용합니다.

---

## 7. 자주 발생하는 오류

### 브랜치를 찾을 수 없음

오류:

```text
pathspec 'feature/pos-web-integration' did not match
```

해결:

```bash
git fetch origin
git switch --track origin/feature/pos-web-integration
```

### npm 명령을 찾을 수 없음

Node.js가 설치되지 않았거나 터미널을 재시작하지 않은 상태입니다.

```bash
node --version
npm --version
```

두 명령이 모두 실행되는지 확인합니다.

### 8000번 주소에서 404가 표시됨

`http://localhost:8000/`에는 화면이 없어서 정상적으로 404가 나옵니다.

다음 주소를 사용합니다.

```text
API 상태: http://localhost:8000/health
API 문서: http://localhost:8000/docs
웹 화면: http://localhost:3000
```

### 모델 API 연결 안 됨

1. FastAPI 터미널이 실행 중인지 확인합니다.
2. `.env`의 주소가 `http://localhost:8000`인지 확인합니다.
3. `.env`를 수정했다면 `npm run dev`를 종료한 후 다시 실행합니다.

### 모델 파일을 찾지 못함

우선 UI를 확인하려면 `.env`를 다음처럼 변경합니다.

```env
VITE_USE_MOCK_API=true
```

---

## 8. 매번 최신 코드로 실행하는 순서

```bash
cd ~/pumpkin
git switch feature/pos-web-integration
git pull
cd web
npm install
npm run dev
```

실제 모델까지 사용할 때는 별도 터미널에서 다음 명령도 실행합니다.

```bash
cd ~/pumpkin
source .venv/bin/activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Windows PowerShell 가상환경 실행:

```powershell
.\.venv\Scripts\Activate.ps1
```
