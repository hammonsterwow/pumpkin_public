import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { FaceRegistrationStatus } from '../types/faceProfile';

const LABELS: Record<FaceRegistrationStatus, string> = {
  UNREGISTERED: '미등록',
  CAPTURING: '촬영 진행 중',
  SAMPLES_COMPLETE: '임베딩 생성 대기',
  REGISTERED: '등록 완료',
  ERROR: '등록 오류',
};

export default function RegistrationStatusBadge({ status }: { status: FaceRegistrationStatus }) {
  const active = status === 'REGISTERED';
  const warning = status === 'CAPTURING' || status === 'SAMPLES_COMPLETE';
  const error = status === 'ERROR';

  return (
    <View style={[styles.badge, active && styles.active, warning && styles.warning, error && styles.error]}>
      <Text style={[styles.text, active && styles.activeText, warning && styles.warningText, error && styles.errorText]}>
        {LABELS[status]}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', borderRadius: 999, backgroundColor: '#F4F4F5', paddingHorizontal: 12, paddingVertical: 6 },
  active: { backgroundColor: '#ECFDF3' },
  warning: { backgroundColor: '#FFF7E0' },
  error: { backgroundColor: '#FEF2F2' },
  text: { color: '#52525B', fontSize: 12, fontWeight: '800' },
  activeText: { color: '#15803D' },
  warningText: { color: '#B77900' },
  errorText: { color: '#B91C1C' },
});
