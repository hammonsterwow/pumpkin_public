import { auth } from './config';
import { deleteTemporaryFaceFrames, markFaceEnrollmentProcessing, saveFaceEmbeddingResult } from './faceEnrollment';

const FACE_EMBEDDING_API_BASE_URL = process.env.EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL?.replace(/\/$/, '');

export type FaceEmbeddingBackendResponse = {
  uid: string;
  embedding_ready: boolean;
  model: string;
  embedding_dimension: number;
  centroid: number[];
  generated_at?: string;
  temporary_frames_deleted?: boolean;
};

export async function requestFaceEmbedding(uid: string): Promise<FaceEmbeddingBackendResponse> {
  if (!FACE_EMBEDDING_API_BASE_URL) {
    throw new Error('EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL이 설정되지 않았습니다.');
  }

  const currentUser = auth.currentUser;
  if (!currentUser || currentUser.uid !== uid) {
    throw new Error('얼굴을 등록하려면 본인 계정으로 다시 로그인해주세요.');
  }

  await markFaceEnrollmentProcessing(uid);
  const idToken = await currentUser.getIdToken();

  const response = await fetch(`${FACE_EMBEDDING_API_BASE_URL}/api/face-enrollment/${encodeURIComponent(uid)}/generate`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${idToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ uid }),
  });

  if (!response.ok) {
    let message = `얼굴 임베딩 생성에 실패했습니다. (${response.status})`;
    try {
      const payload = await response.json() as { detail?: string; message?: string };
      message = payload.detail || payload.message || message;
    } catch {
      // keep default message
    }
    throw new Error(message);
  }

  const result = await response.json() as FaceEmbeddingBackendResponse;
  if (!result.embedding_ready || !Array.isArray(result.centroid) || result.centroid.length === 0) {
    throw new Error('백엔드가 유효한 얼굴 임베딩을 반환하지 않았습니다.');
  }

  // 백엔드가 먼저 저장·삭제한다. 아래 작업은 네트워크 단절이나 이전 백엔드와의
  // 호환성을 위한 멱등성 보강이며, 이미 삭제된 파일은 정상 처리된다.
  await saveFaceEmbeddingResult(uid, {
    model: result.model,
    dimension: result.embedding_dimension,
    centroid: result.centroid,
  });
  await deleteTemporaryFaceFrames(uid);
  return result;
}
