import { auth } from './config';
import { deleteTemporaryFaceFrames, markFaceEnrollmentProcessing } from './faceEnrollment';

const FACE_EMBEDDING_API_BASE_URL = process.env.EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL?.replace(/\/$/, '');

export type FaceEmbeddingBackendResponse = {
  uid: string;
  embedding_ready: boolean;
  model: string;
  embedding_dimension: number;
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
  if (!result.embedding_ready || result.embedding_dimension <= 0) {
    throw new Error('백엔드가 유효한 얼굴 임베딩 생성 결과를 반환하지 않았습니다.');
  }

  // 임베딩은 백엔드가 Firestore에 직접 저장한다. 클라이언트에는 원본 벡터를
  // 반환하지 않으며, 임시 프레임 삭제가 일부 실패한 경우에만 한 번 더 정리한다.
  if (result.temporary_frames_deleted === false) {
    await deleteTemporaryFaceFrames(uid);
  }
  return result;
}
