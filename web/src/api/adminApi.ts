export interface AdminSystemStatus {
  running: boolean;
  state?: string;
  nodes: string[];
  expected_nodes: string[];
  missing_nodes: string[];
  stt_connected?: boolean;
  nlu_connected?: boolean;
  detail?: string;
}

export interface AdminPipelineSnapshot {
  status: string;
  text: string;
  analysis: Record<string, unknown> | null;
  decision: Record<string, unknown> | null;
  response_text: string;
  action: Record<string, unknown> | null;
  error: string | null;
  updated_at?: number;
}

export interface AdminFaceSnapshot {
  detected: boolean;
  matched: boolean;
  customer_id: string | null;
  similarity?: number | null;
  quality?: number | null;
  model?: string | null;
  latency_ms?: number | null;
  reason?: string | null;
  updated_at?: number;
}

export interface AdminSnapshot {
  system: AdminSystemStatus;
  fsm_state: string;
  pipeline: AdminPipelineSnapshot;
  face: AdminFaceSnapshot;
  updated_at: number;
}

export async function getAdminSnapshot(): Promise<AdminSnapshot> {
  const response = await fetch('/api/admin/snapshot');
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `관리자 상태 조회 실패 (${response.status})`);
  }
  return response.json() as Promise<AdminSnapshot>;
}
