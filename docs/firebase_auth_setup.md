# Firebase Authentication setup for customer-mobile

## 목표

무료 Spark 요금제에서 Firebase Authentication과 Firestore를 사용해 앱 사용자별 UID를 발급한다. 얼굴 원본과 InsightFace 임베딩은 계속 Jetson 로컬에 저장한다.

## Firebase 콘솔 설정

1. Firebase 프로젝트를 생성한다.
2. Authentication > Sign-in method에서 이메일/비밀번호 로그인을 활성화한다.
3. Firestore Database를 생성한다.
4. Project settings > Your apps에서 Web app을 등록한다.
5. 발급된 Firebase config 값을 `apps/customer-mobile/.env`에 입력한다.

```env
EXPO_PUBLIC_API_BASE_URL=http://JETSON_IP:8000
EXPO_PUBLIC_FIREBASE_API_KEY=...
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=...
EXPO_PUBLIC_FIREBASE_PROJECT_ID=...
EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET=...
EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
EXPO_PUBLIC_FIREBASE_APP_ID=...
```

## 앱 의존성 설치

```bash
cd apps/customer-mobile
npx expo install firebase @react-native-async-storage/async-storage
```

이 명령은 `package-lock.json`도 현재 Expo SDK에 맞게 갱신한다.

## Firestore 데이터 구조

회원가입 성공 시 아래 문서가 생성된다.

```text
users/{firebaseUid}
```

기본 필드:

```json
{
  "uid": "Firebase UID",
  "name": "사용자 이름",
  "email": "user@example.com",
  "preferredMenu": "아메리카노",
  "preferredTemperature": "ICE",
  "preferredQuantity": 1,
  "faceEnrollmentStatus": "not_started"
}
```

## 권장 Firestore Rules 초안

로그인한 사용자는 자기 문서만 읽고 쓸 수 있도록 제한한다.

```text
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, create, update: if request.auth != null
        && request.auth.uid == userId;
      allow delete: if false;
    }
  }
}
```

## 이번 단계 범위

- 이메일 회원가입
- 이메일 로그인
- 로그인 상태 유지
- Firebase UID 생성
- Firestore 사용자 프로필 생성
- 로그인 전 앱 접근 차단

## 다음 단계

현재 `CustomerMobileApp` 내부에는 아직 데모 고객 ID가 남아 있다. 다음 PR에서 `user.uid`를 Jetson의 `customer_id`로 주입하고, Firestore 프로필과 Jetson SQLite 고객 레코드를 동기화한다.
