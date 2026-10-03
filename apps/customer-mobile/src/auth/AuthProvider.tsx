import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  User,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
} from 'firebase/auth';
import { doc, serverTimestamp, setDoc } from 'firebase/firestore';

import { auth, firebaseConfigured, firestore } from '../firebase/config';

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  configured: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOutUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!firebaseConfigured) {
      setLoading(false);
      return undefined;
    }

    return onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser);
      setLoading(false);
    });
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    configured: firebaseConfigured,
    signIn: async (email, password) => {
      await signInWithEmailAndPassword(auth, email.trim(), password);
    },
    signUp: async (name, email, password) => {
      const trimmedName = name.trim();
      const credential = await createUserWithEmailAndPassword(auth, email.trim(), password);

      await updateProfile(credential.user, { displayName: trimmedName });
      await setDoc(doc(firestore, 'users', credential.user.uid), {
        uid: credential.user.uid,
        name: trimmedName,
        email: credential.user.email,
        preferredMenu: '아메리카노',
        preferredTemperature: 'ICE',
        preferredQuantity: 1,
        faceEnrollmentStatus: 'not_started',
        createdAt: serverTimestamp(),
        updatedAt: serverTimestamp(),
      });

      // 계정 생성 직후 onAuthStateChanged가 displayName 갱신보다 먼저 실행될 수 있다.
      // 새 객체로 상태를 갱신해 앱과 Jetson 고객 DB가 이메일 앞부분이 아니라
      // 회원가입 화면에서 입력한 닉네임을 즉시 사용하도록 한다.
      setUser({ ...credential.user, displayName: trimmedName } as User);
    },
    signOutUser: async () => {
      await signOut(auth);
    },
  }), [loading, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth는 AuthProvider 안에서 사용해야 합니다.');
  return context;
}
