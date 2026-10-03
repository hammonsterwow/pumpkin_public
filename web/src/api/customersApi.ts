export type CustomerTemperature = 'HOT' | 'ICE' | 'NONE';
export type FacePose = 'front' | 'left' | 'right' | 'up' | 'down';

export interface Customer {
  customer_id: string;
  name: string;
  preferred_menu: string;
  preferred_temperature: CustomerTemperature;
  preferred_quantity: number;
  visit_count: number;
  face_registered: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerInput {
  customer_id?: string;
  name: string;
  preferred_menu: string;
  preferred_temperature: CustomerTemperature;
  preferred_quantity: number;
  visit_count: number;
  face_registered: boolean;
}

export interface FaceEnrollmentPose {
  pose: FacePose;
  label: string;
  registered: boolean;
  captured_at: string | null;
}

export interface FaceEnrollmentStatus {
  customer_id: string;
  required_count: number;
  sample_count: number;
  complete: boolean;
  embedding_ready: boolean;
  model: string | null;
  updated_at: string | null;
  poses: FaceEnrollmentPose[];
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string };
    return payload.detail || `요청에 실패했습니다. (${response.status})`;
  } catch {
    return `요청에 실패했습니다. (${response.status})`;
  }
}

export async function listCustomers(): Promise<Customer[]> {
  const response = await fetch('/api/customers');
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<Customer[]>;
}

export async function createCustomer(input: CustomerInput): Promise<Customer> {
  const response = await fetch('/api/customers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<Customer>;
}

export async function updateCustomer(
  customerId: string,
  input: Partial<CustomerInput>,
): Promise<Customer> {
  const response = await fetch(`/api/customers/${encodeURIComponent(customerId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<Customer>;
}

export async function deleteCustomer(customerId: string): Promise<void> {
  const response = await fetch(`/api/customers/${encodeURIComponent(customerId)}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error(await parseError(response));
}

export async function getFaceEnrollment(customerId: string): Promise<FaceEnrollmentStatus> {
  const response = await fetch(`/api/customers/${encodeURIComponent(customerId)}/face-enrollment`);
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<FaceEnrollmentStatus>;
}

export async function uploadFaceSample(
  customerId: string,
  pose: FacePose,
  imageData: string,
): Promise<FaceEnrollmentStatus> {
  const response = await fetch(`/api/customers/${encodeURIComponent(customerId)}/face-enrollment/samples`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pose, image_data: imageData }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<FaceEnrollmentStatus>;
}

export async function resetFaceEnrollment(customerId: string): Promise<void> {
  const response = await fetch(`/api/customers/${encodeURIComponent(customerId)}/face-enrollment`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error(await parseError(response));
}
