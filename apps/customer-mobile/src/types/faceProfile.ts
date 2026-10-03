export type CustomerTemperature = 'HOT' | 'ICE' | 'NONE';
export type FacePose = 'front' | 'left' | 'right' | 'up' | 'down';
export type RequestedFacePose = FacePose | 'unknown';

export type Customer = {
  customer_id: string;
  name: string;
  preferred_menu: string;
  preferred_temperature: CustomerTemperature;
  preferred_quantity: number;
  visit_count: number;
  face_registered: boolean;
  created_at: string;
  updated_at: string;
};

export type CreateCustomerRequest = {
  customer_id?: string;
  name: string;
  preferred_menu: string;
  preferred_temperature: CustomerTemperature;
  preferred_quantity: number;
  visit_count?: number;
  face_registered?: boolean;
};

export type FaceEnrollmentPose = {
  pose: FacePose;
  label: string;
  registered: boolean;
  captured_at: string | null;
  quality: number | null;
};

export type FaceEnrollmentStatus = {
  customer_id: string;
  required_count: number;
  sample_count: number;
  complete: boolean;
  embedding_ready: boolean;
  model: string | null;
  pipeline_backend: string;
  next_pose: FacePose | null;
  next_pose_label: string | null;
  updated_at: string | null;
  poses: FaceEnrollmentPose[];
};

export type FaceEnrollmentFrameRequest = {
  requested_pose: RequestedFacePose;
  image_data: string;
};

export type FaceEnrollmentFrameResponse = {
  accepted: boolean;
  detected_pose: RequestedFacePose | null;
  quality: number | null;
  reason: string;
  face_count: number;
  next_pose: FacePose | null;
  next_pose_label?: string | null;
  complete: boolean;
  status: FaceEnrollmentStatus;
};

export type FaceEnrollmentFinalizeResponse = {
  embedding_ready: boolean;
  model: string | null;
  status: FaceEnrollmentStatus;
  [key: string]: unknown;
};

export type FaceRegistrationStatus =
  | 'UNREGISTERED'
  | 'CAPTURING'
  | 'SAMPLES_COMPLETE'
  | 'REGISTERED'
  | 'ERROR';

export function getFaceRegistrationStatus(
  enrollment: FaceEnrollmentStatus | null,
): FaceRegistrationStatus {
  if (!enrollment || enrollment.sample_count === 0) return 'UNREGISTERED';
  if (enrollment.embedding_ready) return 'REGISTERED';
  if (enrollment.complete) return 'SAMPLES_COMPLETE';
  return 'CAPTURING';
}
