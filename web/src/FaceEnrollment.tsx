import { useEffect, useState } from 'react';
import { Camera, CheckCircle2, RotateCcw, Upload } from 'lucide-react';
import {
  getFaceEnrollment,
  resetFaceEnrollment,
  uploadFaceSample,
  type FaceEnrollmentStatus,
  type FacePose,
} from './api/customersApi';
import './faceEnrollment.css';

const POSE_GUIDE: Record<FacePose, string> = {
  front: '카메라를 정면으로 바라보세요.',
  left: '얼굴을 왼쪽으로 약간 돌리세요.',
  right: '얼굴을 오른쪽으로 약간 돌리세요.',
  up: '턱을 조금 들어 위쪽을 바라보세요.',
  down: '턱을 조금 내려 아래쪽을 바라보세요.',
};

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('이미지를 읽지 못했습니다.'));
    reader.readAsDataURL(file);
  });
}

export default function FaceEnrollment({
  customerId,
  onEnrollmentChanged,
}: {
  customerId: string;
  onEnrollmentChanged: () => void;
}) {
  const [status, setStatus] = useState<FaceEnrollmentStatus | null>(null);
  const [uploadingPose, setUploadingPose] = useState<FacePose | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh() {
    try {
      setStatus(await getFaceEnrollment(customerId));
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '얼굴 등록 상태를 불러오지 못했습니다.');
    }
  }

  useEffect(() => {
    void refresh();
  }, [customerId]);

  async function handleFile(pose: FacePose, file: File | undefined) {
    if (!file) return;
    setUploadingPose(pose);
    setMessage('');
    setError('');
    try {
      const imageData = await fileToDataUrl(file);
      const next = await uploadFaceSample(customerId, pose, imageData);
      setStatus(next);
      setMessage(`${next.poses.find((item) => item.pose === pose)?.label ?? pose} 사진을 저장했습니다.`);
      onEnrollmentChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '얼굴 사진 저장에 실패했습니다.');
    } finally {
      setUploadingPose(null);
    }
  }

  async function reset() {
    if (!window.confirm('저장된 얼굴 등록 사진 5장을 모두 삭제할까요?')) return;
    try {
      await resetFaceEnrollment(customerId);
      await refresh();
      setMessage('얼굴 등록 정보를 초기화했습니다.');
      setError('');
      onEnrollmentChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '초기화에 실패했습니다.');
    }
  }

  return (
    <div className="face-enrollment">
      <div className="face-enrollment-header">
        <div>
          <h3><Camera size={18} /> 다각도 얼굴 등록</h3>
          <p>정면·좌·우·위·아래 5장을 저장합니다. 다음 단계에서 각 사진의 임베딩을 생성합니다.</p>
        </div>
        <strong>{status ? `${status.sample_count}/${status.required_count}` : '-'}</strong>
      </div>

      {message && <div className="customer-message success">{message}</div>}
      {error && <div className="customer-message error">{error}</div>}

      <div className="face-pose-grid">
        {(status?.poses ?? []).map((item) => (
          <label className={`face-pose-card ${item.registered ? 'complete' : ''}`} key={item.pose}>
            <div className="face-pose-icon">
              {item.registered ? <CheckCircle2 size={26} /> : <Camera size={26} />}
            </div>
            <strong>{item.label}</strong>
            <span>{POSE_GUIDE[item.pose]}</span>
            <em>{item.registered ? '저장 완료 · 다시 선택 가능' : '사진 선택 또는 촬영'}</em>
            <div className="face-upload-button"><Upload size={15} />{uploadingPose === item.pose ? '저장 중...' : '이미지 선택'}</div>
            <input
              type="file"
              accept="image/jpeg,image/png"
              capture="user"
              disabled={uploadingPose !== null}
              onChange={(event) => {
                void handleFile(item.pose, event.target.files?.[0]);
                event.currentTarget.value = '';
              }}
            />
          </label>
        ))}
      </div>

      <div className="face-enrollment-summary">
        <div>
          <span>사진 등록</span>
          <strong>{status?.complete ? '5장 완료' : '진행 중'}</strong>
        </div>
        <div>
          <span>임베딩</span>
          <strong>{status?.embedding_ready ? '생성 완료' : '다음 단계'}</strong>
        </div>
        <button className="customer-secondary-button" onClick={() => void reset()} disabled={!status || status.sample_count === 0}>
          <RotateCcw size={15} /> 전체 초기화
        </button>
      </div>
    </div>
  );
}
