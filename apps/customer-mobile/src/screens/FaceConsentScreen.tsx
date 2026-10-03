import React, { useState } from 'react';
import {
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';

export default function FaceConsentScreen({
  onBack,
  onAgree,
  busy = false,
  error = '',
}: {
  onBack: () => void;
  onAgree: () => void;
  busy?: boolean;
  error?: string;
}) {
  const [agreed, setAgreed] = useState(false);
  const [cameraCheckStarted, setCameraCheckStarted] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [permission, requestPermission] = useCameraPermissions();

  const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '');

  const beginCameraCheck = async () => {
    setCameraCheckStarted(true);
    setCameraError('');

    if (!permission?.granted) {
      const result = await requestPermission();
      if (!result.granted) return;
    }

    // 카메라 화면을 먼저 렌더링한 뒤 Jetson 고객/등록 상태 조회를 시작합니다.
    // 서버 연결 실패 때문에 카메라 화면 자체가 가려지지 않도록 분리한 흐름입니다.
    requestAnimationFrame(onAgree);
  };

  if (cameraCheckStarted) {
    const permissionDenied = permission && !permission.granted;
    const canAskAgain = permission?.canAskAgain !== false;

    return (
      <ScrollView style={styles.root} contentContainerStyle={styles.cameraContent}>
        <View style={styles.cameraHeader}>
          <Pressable style={styles.back} onPress={onBack} disabled={busy}>
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <View style={styles.cameraHeaderText}>
            <Text style={styles.kicker}>CAMERA CHECK</Text>
            <Text style={styles.cameraTitle}>카메라 연결 확인</Text>
          </View>
        </View>

        {!permission ? (
          <View style={styles.messageBox}>
            <Text style={styles.message}>카메라 권한 상태를 확인하고 있습니다.</Text>
          </View>
        ) : permissionDenied ? (
          <View style={styles.messageBox}>
            <Text style={styles.message}>
              얼굴 자동 등록을 위해 카메라 권한이 필요합니다.
            </Text>
            <Pressable
              style={styles.permissionButton}
              onPress={() => {
                if (canAskAgain) {
                  void requestPermission().then((result) => {
                    if (result.granted) requestAnimationFrame(onAgree);
                  });
                } else {
                  void Linking.openSettings();
                }
              }}
            >
              <Text style={styles.permissionButtonText}>
                {canAskAgain ? '카메라 권한 허용' : '휴대폰 설정 열기'}
              </Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.cameraFrame}>
            <CameraView
              style={styles.camera}
              facing="front"
              mode="picture"
              mirror
              onCameraReady={() => {
                setCameraReady(true);
                setCameraError('');
              }}
              onMountError={(event) => {
                setCameraReady(false);
                setCameraError(`카메라 시작 실패: ${event.message}`);
              }}
            />
            <View pointerEvents="none" style={styles.cameraOverlay}>
              <View style={[styles.faceOval, cameraReady && styles.faceOvalReady]} />
              <Text style={styles.cameraStatus}>
                {cameraReady ? '카메라 준비 완료' : '카메라를 시작하고 있습니다'}
              </Text>
            </View>
          </View>
        )}

        <View style={styles.diagnosticCard}>
          <Text style={styles.diagnosticTitle}>연결 상태</Text>
          <Text style={styles.diagnosticItem}>
            • 실행 환경: {Platform.OS === 'web' ? '웹 브라우저' : '실제 모바일 앱'}
          </Text>
          <Text style={styles.diagnosticItem}>
            • 카메라: {cameraReady ? '정상' : '확인 중'}
          </Text>
          <Text style={styles.diagnosticItem}>
            • Jetson API: {apiBaseUrl ?? 'EXPO_PUBLIC_API_BASE_URL 미설정'}
          </Text>
          <Text style={styles.diagnosticHelp}>
            카메라 영상은 Jetson 연결보다 먼저 표시됩니다. 영상은 보이지만 다음 촬영 화면으로 넘어가지 않으면 Jetson IP, 포트, 서버 실행 상태를 확인하세요.
          </Text>
        </View>

        {cameraError ? <Text style={styles.error}>{cameraError}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}

        {!apiBaseUrl ? (
          <View style={styles.warningBox}>
            <Text style={styles.warningTitle}>Jetson 주소가 설정되지 않았습니다.</Text>
            <Text style={styles.warningText}>
              앱 실행 전에 EXPO_PUBLIC_API_BASE_URL=http://Jetson-IP:8000 을 설정해야 실제 얼굴 프레임을 전송할 수 있습니다.
            </Text>
          </View>
        ) : null}

        <Pressable
          style={[styles.retryButton, busy && styles.buttonDisabled]}
          disabled={busy}
          onPress={onAgree}
        >
          <Text style={styles.retryButtonText}>
            {busy ? 'Jetson 연결 확인 중...' : 'Jetson 연결 다시 시도'}
          </Text>
        </Pressable>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <Pressable style={styles.back} onPress={onBack} disabled={busy}>
        <Text style={styles.backText}>‹</Text>
      </Pressable>
      <Text style={styles.kicker}>REGULAR CUSTOMER</Text>
      <Text style={styles.title}>얼굴 정보 이용 동의</Text>
      <Text style={styles.description}>
        등록 고객 식별과 선호 메뉴 기반 응대를 위해 얼굴 정보를 사용합니다.
      </Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>수집·이용 안내</Text>
        <Text style={styles.item}>• 목적: 등록 고객 식별 및 개인화 응대</Text>
        <Text style={styles.item}>• 수집 항목: 5개 자세 얼굴 이미지와 서버에서 생성한 얼굴 특징 벡터</Text>
        <Text style={styles.item}>• 앱 역할: 카메라 미리보기, 자세 안내, 프레임 전송</Text>
        <Text style={styles.item}>• Jetson 역할: 이미지 검증, 자세·품질 분석, 저장, 임베딩 생성 및 인식</Text>
        <Text style={styles.item}>• 거부 권리: 동의하지 않아도 일반 주문 기능은 이용할 수 있습니다.</Text>
        <Text style={styles.item}>• 삭제: 마이페이지에서 서버의 얼굴 등록 데이터를 초기화할 수 있습니다.</Text>
      </View>

      <Pressable
        style={styles.checkRow}
        onPress={() => setAgreed((value) => !value)}
        disabled={busy}
      >
        <View style={[styles.check, agreed && styles.checkActive]}>
          <Text style={styles.checkText}>{agreed ? '✓' : ''}</Text>
        </View>
        <Text style={styles.checkLabel}>얼굴 정보 수집 및 이용에 동의합니다.</Text>
      </Pressable>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable
        disabled={!agreed || busy}
        style={[styles.button, (!agreed || busy) && styles.buttonDisabled]}
        onPress={() => void beginCameraCheck()}
      >
        <Text style={styles.buttonText}>
          {busy ? '준비 중...' : '동의하고 카메라 열기'}
        </Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4F4F5' },
  content: { padding: 20, paddingBottom: 120 },
  cameraContent: { padding: 20, paddingBottom: 80 },
  back: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  backText: { color: '#18181B', fontSize: 34, lineHeight: 38 },
  kicker: { color: '#E09D00', fontSize: 12, fontWeight: '900', letterSpacing: 3, marginTop: 28 },
  title: { color: '#18181B', fontSize: 30, fontWeight: '900', marginTop: 8 },
  description: { color: '#71717A', fontSize: 15, lineHeight: 23, marginTop: 12 },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 22,
    marginTop: 24,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  cardTitle: { color: '#18181B', fontSize: 19, fontWeight: '900', marginBottom: 14 },
  item: { color: '#52525B', fontSize: 14, lineHeight: 23, marginBottom: 7 },
  checkRow: { flexDirection: 'row', alignItems: 'center', marginTop: 24 },
  check: {
    width: 26,
    height: 26,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#D4D4D8',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkActive: { backgroundColor: '#E09D00', borderColor: '#E09D00' },
  checkText: { color: '#FFFFFF', fontWeight: '900' },
  checkLabel: { flex: 1, color: '#18181B', fontSize: 14, fontWeight: '700', marginLeft: 12 },
  error: { color: '#B91C1C', fontSize: 13, lineHeight: 20, marginTop: 16 },
  button: {
    height: 58,
    borderRadius: 18,
    backgroundColor: '#E09D00',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 28,
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: '#FFFFFF', fontSize: 17, fontWeight: '900' },
  cameraHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 20 },
  cameraHeaderText: { flex: 1, marginLeft: 14 },
  cameraTitle: { color: '#18181B', fontSize: 24, fontWeight: '900', marginTop: 3 },
  cameraFrame: {
    width: '100%',
    height: 470,
    borderRadius: 28,
    overflow: 'hidden',
    backgroundColor: '#09090B',
  },
  camera: { width: '100%', height: '100%' },
  cameraOverlay: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  faceOval: {
    width: 205,
    height: 270,
    borderRadius: 105,
    borderWidth: 5,
    borderColor: '#FFFFFF',
    opacity: 0.65,
  },
  faceOvalReady: { borderColor: '#E09D00', opacity: 1 },
  cameraStatus: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '900',
    marginTop: 18,
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 9,
  },
  messageBox: {
    minHeight: 360,
    borderRadius: 28,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  message: { color: '#52525B', fontSize: 15, lineHeight: 23, textAlign: 'center' },
  permissionButton: {
    minHeight: 52,
    borderRadius: 16,
    backgroundColor: '#1E3826',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
    marginTop: 20,
  },
  permissionButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '900' },
  diagnosticCard: { backgroundColor: '#FFFFFF', borderRadius: 20, padding: 18, marginTop: 16 },
  diagnosticTitle: { color: '#18181B', fontSize: 16, fontWeight: '900', marginBottom: 8 },
  diagnosticItem: { color: '#52525B', fontSize: 13, lineHeight: 21 },
  diagnosticHelp: { color: '#71717A', fontSize: 12, lineHeight: 19, marginTop: 9 },
  warningBox: { backgroundColor: '#FFF7E0', borderRadius: 18, padding: 16, marginTop: 14 },
  warningTitle: { color: '#8A5A00', fontSize: 14, fontWeight: '900' },
  warningText: { color: '#71500A', fontSize: 12, lineHeight: 19, marginTop: 6 },
  retryButton: {
    height: 56,
    borderRadius: 18,
    backgroundColor: '#1E3826',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
  },
  retryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '900' },
});
