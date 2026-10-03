import type { RobotSttSnapshot } from '../types';

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
    // Relative URLs are allowed.
  }
  return normalized;
}

const API_BASE_URL = resolveApiBaseUrl();

function apiUrl(path: string): string {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}

async function errorMessage(response: Response, fallback: string): Promise<string> {
  const raw = await response.text();
  try {
    const parsed = JSON.parse(raw) as { detail?: string };
    return parsed.detail || raw || fallback;
  } catch {
    return raw || fallback;
  }
}

export async function triggerRobotStt(): Promise<void> {
  const response = await fetch(apiUrl('/api/stt/trigger'), { method: 'POST' });
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'STT 시작 요청에 실패했습니다.'));
  }
}

export async function getRobotSttLatest(): Promise<RobotSttSnapshot> {
  const response = await fetch(apiUrl('/api/stt/latest'));
  if (!response.ok) {
    throw new Error(await errorMessage(response, 'STT 결과 조회에 실패했습니다.'));
  }
  return response.json() as Promise<RobotSttSnapshot>;
}
