import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { StatusBar } from 'expo-status-bar';

import {
  FaceEnrollmentStatus,
  FacePose,
  finalizeFaceEnrollment,
  startFaceEnrollment,
  uploadFaceSample,
} from './src/api/faceEnrollmentApi';

const CUSTOMER_ID =
  process.env.EXPO_PUBLIC_FACE_CUSTOMER_ID ?? 'customer_e8b78f61';

const POSE_GUIDE: Record<FacePose, string> = {
  front: '정면을 바라봐 주세요',
  left: '고개를 천천히 왼쪽으로 돌려 주세요',
  right: '고개를 천천히 오른쪽으로 돌려 주세요',
  up: '고개를 조금 위로 들어 주세요',
  down: '고개를 조금 아래로 내려 주세요',
};

const POSE_ORDER: FacePose[] = ['front', 'left', 'right', 'up', 'down'];

export default function FaceEnrollmentDemoApp() {
  const cameraRef = useRef<CameraView | null>(null);
  const captureTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [permission, requestPermission] = useCameraPermissions();
  const [status, setStatus] = useState<FaceEnrollmentStatus | null>(null);
  const [currentPoseIndex, setCurrentPoseIndex] = useState(0);
  const [countdown, setCountdown] = useState(3);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('얼굴 등록 시작을 눌러 주세요.');

  const currentPose = POSE_ORDER[currentPoseIndex] ?? null;

  useEffect(() => {
    return () => {
      if (captureTimerRef.current) clearTimeout(captureTimerRef.current);
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!running || !currentPose || busy) return;

    setCountdown(3);
    setMessage(POSE_GUIDE[currentPose]);

    let remaining = 3;
    countdownTimerRef.current = setInterval(() => {
      remaining -= 1;
      setCountdown(Math.max(remaining, 0));
    }, 1000);

    captureTimerRef.current = setTimeout(() => {
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
      void captureCurrentPose(currentPose);
    }, 3200);

    return () => {
      if (captureTimerRef.current) clearTimeout(captureTimerRef.current);
      if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    };
  }, [running, currentPoseIndex, busy]);

  const startEnrollment = async () => {
    if (!permission?.granted) {
      const result = await requestPermission();
      if (!result.granted) {
        Alert.alert('카메라 권한 필요', '얼굴 등록을 위해 카메라 권한을 허용해 주세요.');
        return;
      }
    }

    try {
      setBusy(true);
      setMessage('등록 세션을 준비하고 있습니다.');
      const nextStatus = await startFaceEnrollment(CUSTOMER_ID, {
        resetExisting: true,
      });
      setStatus(nextStatus);
      setCurrentPoseIndex(0);
      setRunning(true);
    } catch (error) {
      const detail = error instanceof Error ? error.message : '등록 세션 생성에 실패했습니다.';
      Alert.alert('얼굴 등록 시작 실패', detail);
      setMessage(detail);
    } finally {
      setBusy(false);
    }
  };

  const captureCurrentPose = async (pose: FacePose) => {
    if (!cameraRef.current || !status?.session_id) return;

    try {
      setBusy(true);
      setMessage('사진을 저장하고 있습니다.');

      const photo = await cameraRef.current.takePictureAsync({
        base64: true,
        quality: 0.65,
        skipProcessing: false,
      });

      if (!photo?.base64) {
        throw new Error('촬영 이미지 데이터를 만들지 못했습니다.');
      }

      const uploaded = await uploadFaceSample({
        sessionId: status.session_id,
        customerId: CUSTOMER_ID,
        pose,
        imageData: `data:image/jpeg;base64,${photo.base64}`,
        sequence: currentPoseIndex + 1,
      });

      setStatus(uploaded);

      if (currentPoseIndex >= POSE_ORDER.length - 1) {
        const finalized = await finalizeFaceEnrollment(
          CUSTOMER_ID,
          status.session_id,
        );
        setStatus(finalized);
        setRunning(false);
        setMessage('다섯 방향 촬영이 완료되었습니다.');
        Alert.alert(
          '촬영 완료',
          '얼굴 사진 수집이 완료되었습니다. 임베딩 생성 기능은 다음 단계에서 연결됩니다.',
        );
        return;
      }

      setMessage(`${POSE_GUIDE[pose]} 촬영 완료`);
      setCurrentPoseIndex((previous) => previous + 1);
    } catch (error) {
      const detail = error instanceof Error ? error.message : '사진 촬영 또는 업로드에 실패했습니다.';
      setRunning(false);
      setMessage(detail);
      Alert.alert('촬영 실패', `${detail}\n다시 시작해 주세요.`);
    } finally {
      setBusy(false);
    }
  };

  if (!permission) {
    return (
      <SafeAreaView style={styles.centered}>
        <ActivityIndicator size="large" />
        <Text style={styles.loadingText}>카메라 권한을 확인하고 있습니다.</Text>
      </SafeAreaView>
    );
  }

  if (!permission.granted) {
    return (
      <SafeAreaView style={styles.centered}>
        <Text style={styles.permissionTitle}>카메라 권한이 필요합니다</Text>
        <Text style={styles.permissionBody}>
          얼굴 등록을 위해 전면 카메라 사용을 허용해 주세요.
        </Text>
        <Pressable style={styles.primaryButton} onPress={requestPermission}>
          <Text style={styles.primaryButtonText}>카메라 권한 허용</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  const progress = status?.sample_count ?? 0;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <View style={styles.container}>
        <CameraView
          ref={cameraRef}
          style={styles.camera}
          facing="front"
          mirror
        />

        <View pointerEvents="none" style={styles.overlay}>
          <View style={styles.header}>
            <Text style={styles.title}>얼굴 등록</Text>
            <Text style={styles.progress}>{progress} / 5</Text>
          </View>

          <View style={styles.faceGuide} />

          <View style={styles.guideCard}>
            <Text style={styles.guideText}>{message}</Text>
            {running && !busy ? (
              <Text style={styles.countdown}>{countdown || '찰칵'}</Text>
            ) : null}
            {busy ? <ActivityIndicator color="#FFFFFF" /> : null}
          </View>
        </View>

        {!running ? (
          <View style={styles.bottomArea}>
            <Text style={styles.notice}>
              버튼을 한 번 누르면 안내에 따라 정면·좌·우·위·아래를 자동으로 촬영합니다.
            </Text>
            <Pressable
              disabled={busy}
              style={[styles.primaryButton, busy && styles.disabledButton]}
              onPress={startEnrollment}
            >
              <Text style={styles.primaryButtonText}>
                {progress === 5 ? '다시 등록하기' : '얼굴 등록 시작'}
              </Text>
            </Pressable>
          </View>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#111827' },
  container: { flex: 1, backgroundColor: '#111827' },
  camera: { flex: 1 },
  overlay: {
    ...StyleSheet.absoluteFill,
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 30,
    paddingBottom: 150,
  },
  header: {
    width: '100%',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: { color: '#FFFFFF', fontSize: 24, fontWeight: '800' },
  progress: { color: '#FFFFFF', fontSize: 18, fontWeight: '700' },
  faceGuide: {
    width: 250,
    height: 330,
    borderRadius: 140,
    borderWidth: 4,
    borderColor: '#FBBF24',
    backgroundColor: 'transparent',
  },
  guideCard: {
    minWidth: 280,
    paddingHorizontal: 24,
    paddingVertical: 18,
    borderRadius: 20,
    alignItems: 'center',
    backgroundColor: 'rgba(17, 24, 39, 0.78)',
  },
  guideText: {
    color: '#FFFFFF',
    fontSize: 18,
    lineHeight: 26,
    fontWeight: '700',
    textAlign: 'center',
  },
  countdown: {
    marginTop: 10,
    color: '#FBBF24',
    fontSize: 42,
    fontWeight: '900',
  },
  bottomArea: {
    position: 'absolute',
    right: 20,
    bottom: 28,
    left: 20,
    borderRadius: 22,
    backgroundColor: '#FFFFFF',
    padding: 18,
  },
  notice: {
    color: '#4B5563',
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
    marginBottom: 14,
  },
  primaryButton: {
    minHeight: 54,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
    backgroundColor: '#E09D00',
  },
  primaryButtonText: { color: '#FFFFFF', fontSize: 17, fontWeight: '800' },
  disabledButton: { opacity: 0.55 },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 28,
    backgroundColor: '#F4F4F5',
  },
  loadingText: { marginTop: 16, color: '#52525B', fontSize: 16 },
  permissionTitle: { color: '#18181B', fontSize: 24, fontWeight: '800' },
  permissionBody: {
    marginTop: 12,
    marginBottom: 24,
    color: '#71717A',
    fontSize: 16,
    lineHeight: 24,
    textAlign: 'center',
  },
});
