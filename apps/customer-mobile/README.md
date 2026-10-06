# Pumpkin 고객 앱

Firebase와 Cloud Run에 연결된 Pumpkin 고객용 Expo 앱입니다. 로그인, 메뉴 사전주문, 선호 메뉴 관리와 얼굴 등록을 제공합니다.

## 실행

처음 받는 경우:

```powershell
git clone https://github.com/hammonsterwow/pumpkin_public.git
cd pumpkin_public
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_customer_mobile.ps1
```

이미 저장소가 있다면:

```powershell
cd <pumpkin_public 저장소 경로>
git switch main
git pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_customer_mobile.ps1
```

실행 스크립트는 다음을 수행합니다.

1. `apps/customer-mobile/.env.example`의 공개 Firebase/Cloud Run 설정을 `.env`에 반영합니다.
2. 필수 공개 설정이 있는지 검사합니다.
3. `npm install`로 의존성을 준비합니다.
4. Expo tunnel을 기본 포트 `8099`에서 시작합니다.

터미널에 `Tunnel ready`가 표시된 뒤 Expo Go에서 QR을 스캔합니다.

설치를 건너뛰고 실행하려면:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_customer_mobile.ps1 -SkipInstall
```

## 얼굴 등록 흐름

```text
Firebase Auth 로그인
→ 앱에서 front / left / right / up / down 5장 촬영
→ Firebase Storage 임시 업로드
→ pumpkin-face-backend Cloud Run
→ InsightFace buffalo_l 임베딩 생성
→ 5개 임베딩 centroid 계산
→ Firestore users/{uid}.faceEmbedding 저장
→ 임시 원본 삭제
→ Jetson 현장에서 등록 고객 인식
```

얼굴 등록 자체에는 Jetson 연결이 필요하지 않습니다. Jetson은 매장에서 Firestore에 저장된 임베딩과 실시간 카메라 임베딩을 비교할 때 사용합니다.

## 공개 클라이언트 설정

기본 공개 설정은 `.env.example`에 있습니다.

- 주문 API: `EXPO_PUBLIC_API_BASE_URL`
- 얼굴 임베딩 API: `EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL`
- Firebase Auth / Firestore / Storage 공개 설정

`EXPO_PUBLIC_*` 값은 앱 번들에 포함되는 공개 클라이언트 설정입니다. 서비스 계정 JSON, Relay token, Firebase Admin 자격증명 같은 서버 비밀값을 넣으면 안 됩니다.

## 수동 실행

```powershell
cd apps\customer-mobile
npm install
npx expo start --tunnel --clear --port 8099
```

## 확인 명령

TypeScript:

```powershell
npm run typecheck
```

Expo 설정/의존성:

```powershell
npm run doctor
```

## 주요 환경

- Expo SDK 57
- React Native
- TypeScript
- Firebase JS SDK
- Expo Camera
- Expo FileSystem
