import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';

const AUTO_CAPTURE_SECONDS = 3;
const MAX_AUTO_ATTEMPTS = 3;

export default function FaceCameraView({
  captureKey,
  disabled = false,
  poseLabel,
  onCaptured,
}: {
  captureKey: string;
  disabled?: boolean;
  poseLabel: string;
  onCaptured: (imageData: string) => Promise<boolean>;
}) {
  const cameraRef = useRef<CameraView | null>(null);
  const onCapturedRef = useRef(onCaptured);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [waitingForNextPose, setWaitingForNextPose] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [retryNonce, setRetryNonce] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    onCapturedRef.current = onCaptured;
  }, [onCaptured]);

  useEffect(() => {
    setAttempts(0);
    setWaitingForNextPose(false);
    setCountdown(null);
    setError('');
  }, [captureKey]);

  useEffect(() => () => {
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
  }, []);

  const takePicture = useCallback(async () => {
    if (!cameraRef.current || !cameraReady || capturing || disabled || waitingForNextPose) return;

    setCapturing(true);
    setCountdown(null);
    setError('');

    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.55,
        skipProcessing: false,
      });

      if (!photo?.uri) {
        throw new Error('촬영 이미지의 파일 경로를 가져오지 못했습니다.');
      }

      const accepted = await onCapturedRef.current(photo.uri);

      if (accepted) {
        setWaitingForNextPose(true);
        return;
      }

      const nextAttempts = attempts + 1;
      setAttempts(nextAttempts);
      if (nextAttempts < MAX_AUTO_ATTEMPTS) {
        retryTimerRef.current = setTimeout(
          () => setRetryNonce((value) => value + 1),
          900,
        );
      }
    } catch (caughtError) {
      setAttempts(MAX_AUTO_ATTEMPTS);
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : '사진 촬영에 실패했습니다.',
      );
    } finally {
      setCapturing(false);
    }
  }, [attempts, cameraReady, capturing, disabled, waitingForNextPose]);

  useEffect(() => {
    if (
      !permission?.granted
      || !cameraReady
      || disabled
      || capturing
      || waitingForNextPose
      || attempts >= MAX_AUTO_ATTEMPTS
    ) {
      setCountdown(null);
      return undefined;
    }

    let remaining = AUTO_CAPTURE_SECONDS;
    setCountdown(remaining);

    const timer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(timer);
        setCountdown(0);
        void takePicture();
        return;
      }
      setCountdown(remaining);
    }, 1000);

    return () => clearInterval(timer);
  }, [
    attempts,
    cameraReady,
    captureKey,
    capturing,
    disabled,
    permission?.granted,
    retryNonce,
    takePicture,
    waitingForNextPose,
  ]);

  const restartAutoCapture = () => {
    setAttempts(0);
    setError('');
    setWaitingForNextPose(false);
    setRetryNonce((value) => value + 1);
  };

  if (!permission) {
    return (
      <View style={styles.messageBox}>
        <Text style={styles.message}>카메라 권한을 확인하고 있습니다.</Text>
      </View>
    );
  }

  if (!permission.granted) {
    const canAskAgain = permission.canAskAgain !== false;
    return (
      <View style={styles.messageBox}>
        <Text style={styles.message}>
          얼굴 등록을 위해 카메라 권한이 필요합니다.
        </Text>
        <Pressable
          style={styles.permissionButton}
          onPress={() => {
            if (canAskAgain) {
              void requestPermission();
            } else {
              void Linking.openSettings();
            }
          }}
        >
          <Text style={styles.permissionButtonText}>
            {canAskAgain ? '카메라 권한 허용' : '설정에서 권한 열기'}
          </Text>
        </Pressable>
      </View>
    );
  }

  const statusText = capturing
    ? '촬영 중'
    : waitingForNextPose
      ? '다음 자세 확인 중'
      : countdown === null
        ? '카메라 준비 중'
        : countdown > 0
          ? `${countdown}`
          : '찰칵';

  return (
    <View>
      <View style={styles.cameraContainer}>
        <CameraView
          ref={cameraRef}
          style={styles.camera}
          facing="front"
          mode="picture"
          mirror={false}
          onCameraReady={() => {
            setCameraReady(true);
            setError('');
          }}
          onMountError={(event) => {
            setCameraReady(false);
            setAttempts(MAX_AUTO_ATTEMPTS);
            setError(`카메라를 시작하지 못했습니다: ${event.message}`);
          }}
        />

        <View pointerEvents="none" style={styles.guideLayer}>
          <View style={styles.faceOval} />
          <Text style={styles.guideLabel}>{poseLabel}</Text>
          <Text style={styles.guideText}>
            얼굴을 타원 안에 유지하면 자동으로 촬영됩니다.
          </Text>
          <View style={styles.countdownBadge}>
            <Text style={styles.countdownText}>{statusText}</Text>
          </View>
        </View>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {attempts >= MAX_AUTO_ATTEMPTS ? (
        <Pressable style={styles.retryButton} onPress={restartAutoCapture} disabled={disabled}>
          <Text style={styles.retryButtonText}>자동 촬영 다시 시작</Text>
        </Pressable>
      ) : (
        <Text style={styles.autoNotice}>
          촬영 버튼을 누를 필요가 없습니다. 안내에 맞춰 고개만 움직여주세요.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  cameraContainer: {
    height: 430,
    borderRadius: 28,
    overflow: 'hidden',
    backgroundColor: '#09090B',
  },
  camera: { flex: 1 },
  guideLayer: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: 'rgba(0,0,0,0.08)',
  },
  faceOval: {
    width: 190,
    height: 250,
    borderRadius: 95,
    borderWidth: 5,
    borderColor: '#E09D00',
  },
  guideLabel: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '900',
    marginTop: 18,
    textShadowColor: 'rgba(0,0,0,0.75)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  guideText: {
    color: '#FFFFFF',
    fontSize: 13,
    lineHeight: 20,
    textAlign: 'center',
    marginTop: 6,
    textShadowColor: 'rgba(0,0,0,0.75)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  countdownBadge: {
    minWidth: 78,
    minHeight: 52,
    borderRadius: 26,
    paddingHorizontal: 18,
    marginTop: 16,
    backgroundColor: 'rgba(9,9,11,0.72)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  countdownText: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '900',
  },
  messageBox: {
    minHeight: 330,
    borderRadius: 28,
    backgroundColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  message: {
    color: '#52525B',
    fontSize: 15,
    lineHeight: 23,
    textAlign: 'center',
  },
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
  autoNotice: {
    color: '#71717A',
    fontSize: 13,
    lineHeight: 20,
    textAlign: 'center',
    marginTop: 12,
  },
  retryButton: {
    height: 54,
    borderRadius: 18,
    backgroundColor: '#1E3826',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 14,
  },
  retryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '900' },
  error: { color: '#B91C1C', fontSize: 13, lineHeight: 20, marginTop: 12 },
});
