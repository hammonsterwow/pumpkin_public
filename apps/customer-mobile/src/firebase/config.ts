import { getApp, getApps, initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
};

const missingKeys = Object.entries(firebaseConfig)
  .filter(([, value]) => !value)
  .map(([key]) => key);

export const firebaseConfigured = missingKeys.length === 0;
export const firebaseConfigurationError = firebaseConfigured
  ? null
  : `Firebase 환경변수가 없습니다: ${missingKeys.join(', ')}`;

const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);

// Firebase v12의 현재 Expo 타입 정의에서는 getReactNativePersistence가
// firebase/auth에서 노출되지 않으므로 SDK 기본 Auth 인스턴스를 사용한다.
export const auth = getAuth(app);
export const firestore = getFirestore(app);
export const storage = getStorage(app);
