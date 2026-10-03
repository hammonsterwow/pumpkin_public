import React, { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import FaceCameraView from '../components/FaceCameraView';
import {
  FaceEnrollmentFrameResponse,
  FaceEnrollmentStatus,
  FacePose,
} from '../types/faceProfile';

const POSE_ORDER: FacePose[] = ['front', 'left', 'right', 'up', 'down'];

const POSE_GUIDES: Record<FacePose, string> = {
  front: '카메라를 정면으로 바라봐 주세요.',
  left: '고개를 사용자 기준 왼쪽으로 천천히 돌려주세요.',
  right: '고개를 사용자 기준 오른쪽으로 천천히 돌려주세요.',
  up: '턱을 살짝 올려 위쪽을 바라봐 주세요.',
  down: '턱을 살짝 내려 아래쪽을 바라봐 주세요.',
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '얼굴 프레임 저장에 실패했습니다.';
}

export default function FaceCaptureScreen({
  status,
  lastFrame,
  submitting,
  error,
  onBack,
  onCaptureImage,
  onFinalize,
  onReset,
}: {
  status: FaceEnrollmentStatus;
  lastFrame: FaceEnrollmentFrameResponse | null;
  submitting: boolean;
  error: string;
  onBack: () => void;
  onCaptureImage: (pose: FacePose, imageData: string) => Promise<FaceEnrollmentFrameResponse>;
  onFinalize: () => Promise<void>;
  onReset: () => Promise<void>;
}) {
  const [liveStatus, setLiveStatus] = useState(status);
  const [liveFrame, setLiveFrame] = useState(lastFrame);
  const [localBusy, setLocalBusy] = useState(false);
  const [localError, setLocalError] = useState('');

  useEffect(() => setLiveStatus(status), [status]);
  useEffect(() => setLiveFrame(lastFrame), [lastFrame]);

  const busy = submitting || localBusy;
  const pose = liveStatus.next_pose ?? 'front';
  const poseLabel = liveStatus.next_pose_label ?? pose;
  const progress = `${liveStatus.sample_count}/${liveStatus.required_count}`;
  const captureKey = `${liveStatus.customer_id}:${pose}:${liveStatus.sample_count}`;

  const captureAndSend = async (imageData: string): Promise<boolean> => {
    setLocalBusy(true);
    setLocalError('');
    try {
      const response = await onCaptureImage(pose, imageData);
      setLiveFrame(response);
      setLiveStatus(response.status);
      if (!response.accepted) setLocalError(`프레임이 거절되었습니다: ${response.reason}`);
      return response.accepted;
    } catch (caughtError) {
      const message = errorMessage(caughtError);
      setLocalError(message);
      throw new Error(message);
    } finally {
      setLocalBusy(false);
    }
  };

  const resetCapture = async () => {
    setLocalBusy(true);
    setLocalError('');
    try {
      await onReset();
      setLiveFrame(null);
    } catch (caughtError) {
      setLocalError(errorMessage(caughtError));
    } finally {
      setLocalBusy(false);
    }
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Pressable style={styles.back} onPress={onBack} disabled={busy}><Text style={styles.backText}>‹</Text></Pressable>
        <View style={styles.headerText}>
          <Text style={styles.kicker}>AUTOMATIC FACE SCAN</Text>
          <Text style={styles.title}>얼굴 자동 등록</Text>
        </View>
        <Text style={styles.progress}>{progress}</Text>
      </View>

      <View style={styles.poseRow}>
        {POSE_ORDER.map((item) => {
          const registered = liveStatus.poses.some((poseStatus) => poseStatus.pose === item && poseStatus.registered);
          const current = item === pose && !liveStatus.complete;
          return (
            <View key={item} style={[styles.poseDot, current && styles.poseDotCurrent, registered && styles.poseDotDone]}>
              <Text style={[styles.poseDotText, (current || registered) && styles.poseDotTextActive]}>{registered ? '✓' : POSE_ORDER.indexOf(item) + 1}</Text>
            </View>
          );
        })}
      </View>

      {liveStatus.complete ? (
        <View style={styles.completeBox}>
          <Text style={styles.completeIcon}>✓</Text>
          <Text style={styles.completeTitle}>필수 5개 자세 촬영 완료</Text>
          <Text style={styles.completeBody}>Firebase Storage에 임시 사진이 모두 저장되었습니다. 최종화를 누르면 백엔드에서 임베딩을 생성하고 성공한 뒤 원본 사진을 삭제합니다.</Text>
        </View>
      ) : (
        <>
          <View style={styles.guideBox}>
            <Text style={styles.nextLabel}>{poseLabel}</Text>
            <Text style={styles.poseGuide}>{POSE_GUIDES[pose]}</Text>
          </View>
          <FaceCameraView captureKey={captureKey} disabled={busy} poseLabel={poseLabel} onCaptured={captureAndSend} />
          <View style={styles.phaseNotice}>
            <Text style={styles.phaseTitle}>현재 저장 방식</Text>
            <Text style={styles.phaseText}>앱이 자세별 안내와 자동 촬영을 담당하고, 각 사진은 Firebase Storage의 사용자 전용 임시 경로에 저장됩니다.</Text>
          </View>
        </>
      )}

      {liveFrame ? (
        <View style={[styles.result, liveFrame.accepted ? styles.resultAccepted : styles.resultRejected]}>
          <Text style={styles.resultTitle}>{liveFrame.accepted ? '임시 저장 완료' : '자동 재촬영 예정'}</Text>
          <Text style={styles.resultText}>상태: {liveFrame.reason}</Text>
        </View>
      ) : null}

      {localError || error ? <Text style={styles.error}>{localError || error}</Text> : null}

      {liveStatus.complete ? (
        <Pressable disabled={busy} style={[styles.finalizeButton, busy && styles.disabled]} onPress={() => void onFinalize()}>
          <Text style={styles.finalizeButtonText}>{busy ? '임베딩 생성 중...' : '얼굴 등록 최종화'}</Text>
        </Pressable>
      ) : null}

      <Pressable disabled={busy} style={styles.resetButton} onPress={() => void resetCapture()}>
        <Text style={styles.resetButtonText}>처음부터 다시 촬영</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4F4F5' },
  content: { padding: 20, paddingBottom: 120 },
  header: { flexDirection: 'row', alignItems: 'center' },
  back: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  backText: { color: '#18181B', fontSize: 34, lineHeight: 38 },
  headerText: { flex: 1, marginLeft: 14 },
  kicker: { color: '#E09D00', fontSize: 11, fontWeight: '900', letterSpacing: 1.6 },
  title: { color: '#18181B', fontSize: 23, fontWeight: '900', marginTop: 3 },
  progress: { color: '#1E3826', fontSize: 16, fontWeight: '900' },
  poseRow: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 22 },
  poseDot: { width: 42, height: 42, borderRadius: 21, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D4D4D8', alignItems: 'center', justifyContent: 'center' },
  poseDotCurrent: { backgroundColor: '#E09D00', borderColor: '#E09D00' },
  poseDotDone: { backgroundColor: '#1E3826', borderColor: '#1E3826' },
  poseDotText: { color: '#71717A', fontSize: 14, fontWeight: '900' },
  poseDotTextActive: { color: '#FFFFFF' },
  guideBox: { marginBottom: 14, alignItems: 'center' },
  nextLabel: { color: '#18181B', fontSize: 20, fontWeight: '900', textAlign: 'center' },
  poseGuide: { color: '#71717A', fontSize: 14, lineHeight: 21, textAlign: 'center', marginTop: 6 },
  phaseNotice: { borderRadius: 18, backgroundColor: '#FFF7E0', padding: 16, marginTop: 14 },
  phaseTitle: { color: '#8A5A00', fontSize: 13, fontWeight: '900' },
  phaseText: { color: '#71500A', fontSize: 12, lineHeight: 19, marginTop: 6 },
  completeBox: { minHeight: 300, borderRadius: 28, backgroundColor: '#1E3826', alignItems: 'center', justifyContent: 'center', padding: 26 },
  completeIcon: { color: '#FFFFFF', fontSize: 52, fontWeight: '900' },
  completeTitle: { color: '#FFFFFF', fontSize: 22, fontWeight: '900', marginTop: 18 },
  completeBody: { color: '#D4D4D8', fontSize: 14, lineHeight: 22, textAlign: 'center', marginTop: 12 },
  result: { borderRadius: 18, padding: 16, marginTop: 16 },
  resultAccepted: { backgroundColor: '#ECFDF3' },
  resultRejected: { backgroundColor: '#FEF2F2' },
  resultTitle: { color: '#18181B', fontSize: 15, fontWeight: '900' },
  resultText: { color: '#52525B', fontSize: 13, marginTop: 5 },
  error: { color: '#B91C1C', fontSize: 13, lineHeight: 20, marginTop: 14 },
  finalizeButton: { height: 58, borderRadius: 18, backgroundColor: '#E09D00', alignItems: 'center', justifyContent: 'center', marginTop: 20 },
  finalizeButtonText: { color: '#FFFFFF', fontSize: 17, fontWeight: '900' },
  resetButton: { height: 52, borderRadius: 18, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', marginTop: 10 },
  resetButtonText: { color: '#1E3826', fontSize: 15, fontWeight: '900' },
  disabled: { opacity: 0.55 },
});
