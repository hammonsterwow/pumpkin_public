import {
  CreateCustomerRequest,
  Customer,
  FaceEnrollmentFinalizeResponse,
  FaceEnrollmentFrameRequest,
  FaceEnrollmentFrameResponse,
  FaceEnrollmentStatus,
} from '../types/faceProfile';
import { validateFaceImageData } from '../utils/imageValidation';

const API_BASE_URL = (
  process.env.EXPO_PUBLIC_FACE_API_BASE_URL
  || process.env.EXPO_PUBLIC_API_BASE_URL
)?.replace(/\/$/, '');

export class FaceEnrollmentApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'FaceEnrollmentApiError';
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string };
    return payload.detail || `요청에 실패했습니다. (${response.status})`;
  } catch {
    return `요청에 실패했습니다. (${response.status})`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('EXPO_PUBLIC_API_BASE_URL이 설정되지 않았습니다.');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    throw new FaceEnrollmentApiError(await parseError(response), response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function customerPath(customerId: string): string {
  return `/api/customers/${encodeURIComponent(customerId)}`;
}

export async function getCustomer(customerId: string): Promise<Customer> {
  return request<Customer>(customerPath(customerId));
}

export async function createCustomer(input: CreateCustomerRequest): Promise<Customer> {
  return request<Customer>('/api/customers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      visit_count: 0,
      face_registered: false,
      ...input,
    }),
  });
}

export async function updateCustomer(
  customerId: string,
  input: Partial<CreateCustomerRequest>,
): Promise<Customer> {
  return request<Customer>(customerPath(customerId), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export async function ensureCustomer(input: CreateCustomerRequest): Promise<Customer> {
  if (!input.customer_id) return createCustomer(input);

  try {
    return await getCustomer(input.customer_id);
  } catch (error) {
    if (error instanceof FaceEnrollmentApiError && error.status === 404) {
      return createCustomer(input);
    }
    throw error;
  }
}

export async function getFaceEnrollment(
  customerId: string,
): Promise<FaceEnrollmentStatus> {
  return request<FaceEnrollmentStatus>(`${customerPath(customerId)}/face-enrollment`);
}

export async function sendFaceEnrollmentFrame(
  customerId: string,
  payload: FaceEnrollmentFrameRequest,
): Promise<FaceEnrollmentFrameResponse> {
  const validationErrors = validateFaceImageData(payload.image_data);
  if (validationErrors.length > 0) {
    throw new Error(validationErrors.join('\n'));
  }

  return request<FaceEnrollmentFrameResponse>(
    `${customerPath(customerId)}/face-enrollment/frames`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  );
}

export async function finalizeFaceEnrollment(
  customerId: string,
): Promise<FaceEnrollmentFinalizeResponse> {
  return request<FaceEnrollmentFinalizeResponse>(
    `${customerPath(customerId)}/face-enrollment/finalize`,
    { method: 'POST' },
  );
}

export async function resetFaceEnrollment(customerId: string): Promise<void> {
  await request<void>(`${customerPath(customerId)}/face-enrollment`, {
    method: 'DELETE',
  });
}
