import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { firebaseConfigurationError } from '../firebase/config';
import { useAuth } from '../auth/AuthProvider';

function messageFromError(error: unknown): string {
  if (!(error instanceof Error)) return '로그인 처리 중 오류가 발생했습니다.';
  if (error.message.includes('invalid-credential')) return '이메일 또는 비밀번호를 확인해주세요.';
  if (error.message.includes('email-already-in-use')) return '이미 가입된 이메일입니다.';
  if (error.message.includes('weak-password')) return '비밀번호는 6자 이상 입력해주세요.';
  if (error.message.includes('invalid-email')) return '이메일 형식을 확인해주세요.';
  return error.message;
}

export default function AuthScreen() {
  const { configured, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    if (!configured) {
      setError(firebaseConfigurationError ?? 'Firebase 설정이 필요합니다.');
      return;
    }
    if (mode === 'signup' && !name.trim()) {
      setError('이름을 입력해주세요.');
      return;
    }
    if (!email.trim() || !password) {
      setError('이메일과 비밀번호를 입력해주세요.');
      return;
    }

    setBusy(true);
    try {
      if (mode === 'signup') await signUp(name, email, password);
      else await signIn(email, password);
    } catch (submitError) {
      setError(messageFromError(submitError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.root}
      >
        <View style={styles.card}>
          <Text style={styles.brand}>PUMPKIN</Text>
          <Text style={styles.title}>{mode === 'login' ? '로그인' : '회원가입'}</Text>
          <Text style={styles.description}>
            로그인한 계정의 Firebase UID가 Jetson 고객 ID로 연결됩니다.
          </Text>

          {mode === 'signup' ? (
            <TextInput
              autoCapitalize="words"
              placeholder="이름"
              style={styles.input}
              value={name}
              onChangeText={setName}
            />
          ) : null}
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            placeholder="이메일"
            style={styles.input}
            value={email}
            onChangeText={setEmail}
          />
          <TextInput
            placeholder="비밀번호 (6자 이상)"
            secureTextEntry
            style={styles.input}
            value={password}
            onChangeText={setPassword}
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable disabled={busy} style={[styles.primary, busy && styles.disabled]} onPress={() => void submit()}>
            {busy ? <ActivityIndicator color="#FFFFFF" /> : (
              <Text style={styles.primaryText}>{mode === 'login' ? '로그인' : '가입하기'}</Text>
            )}
          </Pressable>

          <Pressable
            disabled={busy}
            style={styles.switchButton}
            onPress={() => {
              setError('');
              setMode((current) => current === 'login' ? 'signup' : 'login');
            }}
          >
            <Text style={styles.switchText}>
              {mode === 'login' ? '처음이신가요? 회원가입' : '이미 계정이 있나요? 로그인'}
            </Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F4F4F5' },
  root: { flex: 1, justifyContent: 'center', padding: 22 },
  card: { backgroundColor: '#FFFFFF', borderRadius: 24, padding: 24, elevation: 3 },
  brand: { color: '#E09D00', fontSize: 14, fontWeight: '900', letterSpacing: 2 },
  title: { color: '#18181B', fontSize: 32, fontWeight: '900', marginTop: 10 },
  description: { color: '#71717A', fontSize: 14, lineHeight: 21, marginTop: 8, marginBottom: 24 },
  input: { borderWidth: 1, borderColor: '#D4D4D8', borderRadius: 14, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, marginBottom: 12, backgroundColor: '#FAFAFA' },
  error: { color: '#B91C1C', fontSize: 13, lineHeight: 19, marginBottom: 12 },
  primary: { minHeight: 52, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: '#1E3826', marginTop: 4 },
  disabled: { opacity: 0.55 },
  primaryText: { color: '#FFFFFF', fontSize: 16, fontWeight: '900' },
  switchButton: { paddingVertical: 16, alignItems: 'center' },
  switchText: { color: '#71717A', fontWeight: '800' },
});
