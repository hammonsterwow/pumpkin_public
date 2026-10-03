import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import RegistrationStatusBadge from '../components/RegistrationStatusBadge';
import {
  FaceEnrollmentFinalizeResponse,
  getFaceRegistrationStatus,
} from '../types/faceProfile';

export default function FaceRegistrationResultScreen({
  result,
  onDone,
  onRetry,
}: {
  result: FaceEnrollmentFinalizeResponse;
  onDone: () => void;
  onRetry: () => void;
}) {
  const registrationStatus = getFaceRegistrationStatus(result.status);

  return (
    <View style={styles.root}>
      <View style={styles.icon}><Text style={styles.iconText}>{result.embedding_ready ? '✓' : '…'}</Text></View>
      <RegistrationStatusBadge status={registrationStatus} />
      <Text style={styles.title}>{result.embedding_ready ? '얼굴 등록이 완료되었습니다' : '촬영 데이터 저장이 완료되었습니다'}</Text>
      <Text style={styles.body}>Jetson 서버가 5개 자세를 최종화했습니다. 현재 Phase 1에서는 임베딩 모델이 연결되지 않아 embedding_ready가 false일 수 있습니다.</Text>
      <View style={styles.card}>
        <Text style={styles.label}>촬영 샘플</Text>
        <Text style={styles.value}>{result.status.sample_count}/{result.status.required_count}</Text>
        <Text style={styles.label}>임베딩 준비</Text>
        <Text style={styles.value}>{result.embedding_ready ? '완료' : 'Phase 2 연결 대기'}</Text>
        <Text style={styles.label}>모델</Text>
        <Text style={styles.value}>{result.model ?? '미연결'}</Text>
        <Text style={styles.caption}>API 엔드포인트는 Phase 2에서도 유지되므로 앱 코드를 바꾸지 않고 서버의 얼굴 인식 모델을 연결할 수 있습니다.</Text>
      </View>
      <Pressable style={styles.primary} onPress={onDone}><Text style={styles.primaryText}>마이페이지로 이동</Text></Pressable>
      <Pressable style={styles.secondary} onPress={onRetry}><Text style={styles.secondaryText}>처음부터 다시 촬영</Text></Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4F4F5', padding: 24, alignItems: 'center', justifyContent: 'center' },
  icon: { width: 88, height: 88, borderRadius: 44, backgroundColor: '#1E3826', alignItems: 'center', justifyContent: 'center', marginBottom: 18 },
  iconText: { color: '#FFFFFF', fontSize: 42, fontWeight: '900' },
  title: { color: '#18181B', fontSize: 27, lineHeight: 36, textAlign: 'center', fontWeight: '900', marginTop: 18 },
  body: { color: '#71717A', fontSize: 15, lineHeight: 23, textAlign: 'center', marginTop: 12 },
  card: { width: '100%', backgroundColor: '#FFFFFF', borderRadius: 24, padding: 22, marginTop: 24 },
  label: { color: '#A1A1AA', fontSize: 12, fontWeight: '800', marginTop: 8 },
  value: { color: '#18181B', fontSize: 16, fontWeight: '900', marginTop: 4 },
  caption: { color: '#71717A', fontSize: 13, lineHeight: 20, marginTop: 18 },
  primary: { width: '100%', height: 58, borderRadius: 18, backgroundColor: '#E09D00', alignItems: 'center', justifyContent: 'center', marginTop: 22 },
  primaryText: { color: '#FFFFFF', fontSize: 17, fontWeight: '900' },
  secondary: { width: '100%', height: 54, borderRadius: 18, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', marginTop: 10 },
  secondaryText: { color: '#1E3826', fontSize: 15, fontWeight: '900' },
});
