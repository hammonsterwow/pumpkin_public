import type { OrderAnalysisResult, RosPipelineStatus } from '../types';

const CONFIGURED_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim();

function resolveApiBaseUrl(): string {
  if (!CONFIGURED_API_BASE_URL) return '';

  const normalized = CONFIGURED_API_BASE_URL.replace(/\/$/, '');
  try {
    const configured = new URL(normalized);
    const configuredIsLocal = ['localhost', '127.0.0.1'].includes(configured.hostname);
    const browserIsRemote = !['localhost', '127.0.0.1'].includes(window.location.hostname);

    if (configuredIsLocal && browserIsRemote) return '';
  } catch {
    // Relative base URLs are valid.
  }
  return normalized;
}

const API_BASE_URL = resolveApiBaseUrl();

function apiUrl(path: string): string {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}

export async function analyzeOrder(text: string): Promise<OrderAnalysisResult> {
  const cleanText = text.trim();
  if (!cleanText) throw new Error('주문 문장을 입력해주세요.');

  const response = await fetch(apiUrl('/api/orders/analyze-step3'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: cleanText }),
  });

  if (!response.ok) {
    const rawBody = await response.text();
    let message = rawBody || `ROS 주문 흐름 요청 실패 (${response.status})`;
    try {
      const parsed = JSON.parse(rawBody) as { detail?: string };
      if (parsed.detail) message = parsed.detail;
    } catch {
      // Keep the raw response body when it is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<OrderAnalysisResult>;
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(apiUrl('/health'));
    if (!response.ok) return false;
    const health = (await response.json()) as {
      status?: string;
      model_name?: string;
      detail?: string;
    };
    if (health.status === 'ok') {
      console.info(`[Pumpkin ROS] connected: ${health.model_name ?? 'unknown'}`);
      return true;
    }
    console.error('[Pumpkin ROS] health error:', health.detail ?? health);
    return false;
  } catch (error) {
    console.error('[Pumpkin ROS] connection failed:', error);
    return false;
  }
}

export async function checkRosPipeline(): Promise<RosPipelineStatus> {
  const response = await fetch(apiUrl('/api/ros/status'));
  if (!response.ok) {
    return { running: false, nodes: [] };
  }
  return response.json() as Promise<RosPipelineStatus>;
}
