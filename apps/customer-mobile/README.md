# Pumpkin 고객 앱

Firebase와 Cloud Run에 연결된 Pumpkin 고객용 모바일 앱입니다. 로그인, 메뉴 주문, 사전 주문, 단골 선호 메뉴 저장, 얼굴 등록을 한 앱에서 제공합니다.

## Windows에서 한 번에 실행

저장소 루트에서 아래 파일을 더블클릭합니다.

```text
run_customer_mobile_windows.cmd
```

PowerShell에서 실행하려면:

```powershell
cd C:\Users\yulle\pumpkin
.\run_customer_mobile_windows.cmd
```

또는 실행 스크립트를 직접 호출할 수 있습니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_customer_mobile.ps1
```

스크립트가 자동으로 다음 작업을 수행합니다.

1. `apps/customer-mobile/.env`가 없으면 검증된 `.env.example`을 복사합니다.
2. 단독 얼굴 촬영 데모 설정을 제거하여 Firebase 연동 완성 앱으로 실행합니다.
3. 필요한 Firebase·Cloud Run 공개 설정이 모두 있는지 검사합니다.
4. `npm install`로 의존성을 준비합니다.
5. Expo 터널을 포트 `8099`에서 시작하고 QR 코드를 표시합니다.

터미널에 `Tunnel ready`가 나온 뒤 QR을 iPhone 카메라 또는 Expo Go로 스캔합니다.

처음 내려받는 경우:

```powershell
git clone https://github.com/yulllee0829/pumpkin.git
cd pumpkin
.\run_customer_mobile_windows.cmd
```

기존 저장소를 최신화하는 경우:

```powershell
cd C:\Users\yulle\pumpkin
git switch main
git pull --ff-only
.\run_customer_mobile_windows.cmd
```

> OneDrive 폴더에서 Git이 파일 삭제를 반복해서 묻는 문제가 있었다면 `C:\Users\yulle\pumpkin`처럼 OneDrive 밖의 새 클론을 권장합니다.

## 얼굴 등록의 실제 처리 흐름

1. 고객이 Firebase Auth 계정으로 로그인합니다.
2. 앱이 iPhone 카메라로 다섯 자세를 촬영합니다.
3. 앱은 iOS 파일 URI를 `expo/fetch`로 Firebase Storage의 임시 경로에 직접 업로드합니다.
4. Cloud Run의 `pumpkin-face-backend`가 임시 사진을 읽습니다.
5. InsightFace `buffalo_l`이 각 사진을 임베딩으로 변환합니다.
6. 정상 임베딩의 평균인 centroid를 Firestore `users/{uid}.faceEmbedding`에 저장합니다.
7. 처리가 성공하면 임시 원본 사진을 삭제합니다.
8. 이후 Jetson이 카메라 얼굴 임베딩과 Firestore centroid를 비교해 단골을 인식합니다.

얼굴 **등록**에는 Jetson 연결이 필요하지 않습니다. Jetson은 로봇 현장에서 등록된 고객을 **인식**할 때 사용합니다.

## 설정

공개 클라이언트 설정은 `.env.example`에 포함되어 있습니다.

- 고객 API: `pumpkin-relay` Cloud Run
- 얼굴 임베딩 API: `pumpkin-face-backend` Cloud Run
- Firebase Auth / Firestore / Storage 프로젝트: `pumpkin-63c92`

`EXPO_PUBLIC_*` 값은 Expo 앱 번들에 포함되는 공개 클라이언트 설정입니다. 서비스 계정 JSON, relay token, Firebase Admin 비밀키 같은 서버 비밀값은 저장소에 추가하면 안 됩니다.

완성 앱이 기본값입니다. 아래 설정은 별도 촬영 테스트 화면만 강제로 여는 개발용 옵션이므로 일반 실행에는 넣지 마세요.

```dotenv
EXPO_PUBLIC_FACE_ENROLLMENT_DEMO=1
```

## 문제 해결

### `Creating blobs from 'ArrayBuffer'...`

오래된 업로드 코드가 실행 중인 상태입니다. 최신 `main`은 `uploadBytes` 대신 `expo/fetch`와 파일 URI를 사용합니다.

```powershell
git switch main
git pull --ff-only
Select-String -Path .\apps\customer-mobile\src\firebase\faceEnrollment.ts -Pattern "expo/fetch"
```

`import { fetch } from 'expo/fetch';`가 나오면 올바른 버전입니다. 그 뒤 원클릭 실행기를 다시 실행합니다.

### Expo Go가 `Opening project...`에서 멈춤

터미널에 `Tunnel connected`와 `Tunnel ready`가 모두 나온 뒤 새 QR을 스캔합니다. 이전 Expo Go 프로젝트 화면은 닫고, 필요하면 Wi-Fi 대신 휴대폰 데이터로 QR을 다시 엽니다.

### `EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL이 설정되지 않았습니다`

원클릭 실행기를 저장소 루트에서 실행하세요. 이 실행기가 검증된 `.env.example`로 `.env`를 자동 생성합니다.

## 수동 개발 명령

```powershell
cd apps\customer-mobile
npm install
npx expo start --tunnel --clear --port 8099
```

환경:

- Expo SDK 54
- React Native 0.81
- Firebase JS SDK
- Expo Camera
- Expo FileSystem
