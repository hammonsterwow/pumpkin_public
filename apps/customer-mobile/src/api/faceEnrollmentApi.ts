export type FacePose = 'front' | 'left' | 'right' | 'up' | 'down';

export type FacePoseStatus = {
  pose: FacePose;
  label: string;
  registered: boolean;
  captured_at: string | null;
  sequence: number | null;
  size_bytes: number | null;
};

export type FaceEnrollmentStatus = {
  customer_id: string;
  session_id: string;
  status: 'collecting' | 'samples_complete';
  required_count: number;
  sample_count: number;
  complete: boolean;
  embedding_ready: boolean;
  model: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string | null;
  next_pose: FacePose | null;
  poses: FacePoseStatus[];
};

export type StartFaceEnrollmentOptions = {
  resetExisting?: boolean;
};

export type UploadFaceSampleInput = {
  sessionId: string;
  customerId: string;
  pose: FacePose;
  imageData: string;
  capturedAt?: string;
  sequence?: number;
};

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('EXPO_PUBLIC_API_BASE_URL이 설정되지 않았습니다.');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    let detail = '';
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? JSON.stringify(payload);
    } catch {
      detail = await response.text();
    }
    throw new Error(`얼굴 등록 API 오류 ${response.status}: ${detail}`);
  }

  return response.json() as Promise<T>;
}

export async function startFaceEnrollment(
  customerId: string,
  options: StartFaceEnrollmentOptions = {},
): Promise<FaceEnrollmentStatus> {
  return request<FaceEnrollmentStatus>('/api/faces/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customer_id: customerId,
      reset_existing: options.resetExisting ?? true,
    }),
  });
}

export async function uploadFaceSample(
  input: UploadFaceSampleInput,
): Promise<FaceEnrollmentStatus> {
  return request<FaceEnrollmentStatus>('/api/faces/upload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: input.sessionId,
      customer_id: input.customerId,
      pose: input.pose,
      image_data: input.imageData,
      captured_at: input.capturedAt ?? new Date().toISOString(),
      sequence: input.sequence,
    }),
  });
}

export async function finalizeFaceEnrollment(
  customerId: string,
  sessionId: string,
): Promise<FaceEnrollmentStatus> {
  return request<FaceEnrollmentStatus>('/api/faces/finalize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customer_id: customerId,
      session_id: sessionId,
    }),
  });
}

export async function getFaceEnrollmentStatus(
  customerId: string,
): Promise<FaceEnrollmentStatus> {
  return request<FaceEnrollmentStatus>(`/api/customers/${encodeURIComponent(customerId)}/face-enrollment`);
}
