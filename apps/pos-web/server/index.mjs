import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { applicationDefault, getApps, initializeApp } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(appRoot, '../..');
const distDir = path.join(appRoot, 'dist');
const menuCatalogPath = path.join(repoRoot, 'config', 'menu_catalog.json');
const app = express();

const port = Number(process.env.POS_PORT || 4174);
const bindHost = String(process.env.POS_BIND_HOST || '127.0.0.1');
const relayBaseUrl = String(process.env.POS_RELAY_BASE_URL || '').replace(/\/$/, '');
const relayToken = String(process.env.JETSON_RELAY_TOKEN || '');
const firebaseProjectId = String(process.env.PUMPKIN_FIREBASE_PROJECT_ID || '').trim();
const customerNameCache = new Map();
const CUSTOMER_NAME_CACHE_MS = 60_000;
let customerFirestore = null;
const demoStatePath = process.env.POS_DEMO_STATE_FILE
  ? path.resolve(String(process.env.POS_DEMO_STATE_FILE))
  : path.join(appRoot, '.runtime', 'demo-mode.json');

const ALLOWED_STATUSES = new Set([
  'RECEIVED',
  'PREPARING',
  'READY',
  'PICKED_UP',
  'CANCELLED',
]);

const DEMO_DELAYS_MS = Object.freeze({
  RECEIVED: 1000,
  PREPARING: 5000,
  ROBOT_READY: 3000,
});

function loadDemoModeEnabled() {
  try {
    const payload = JSON.parse(fs.readFileSync(demoStatePath, 'utf8'));
    return payload?.enabled === true;
  } catch (error) {
    if (error?.code !== 'ENOENT') {
      console.warn(`[POS DEMO] Failed to restore mode: ${error?.message}`);
    }
    return false;
  }
}

function persistDemoModeEnabled(enabled) {
  const directory = path.dirname(demoStatePath);
  const temporaryPath = `${demoStatePath}.tmp`;
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(
    temporaryPath,
    `${JSON.stringify({ enabled: Boolean(enabled) }, null, 2)}\n`,
    'utf8',
  );
  fs.renameSync(temporaryPath, demoStatePath);
}

let demoModeEnabled = loadDemoModeEnabled();
let demoWorkerBusy = false;

function assertServerConfig() {
  const missing = [];
  if (!relayBaseUrl) missing.push('POS_RELAY_BASE_URL');
  if (!relayToken) missing.push('JETSON_RELAY_TOKEN');
  if (missing.length) {
    console.warn(`[POS] Missing environment variables: ${missing.join(', ')}`);
  }
  if (bindHost !== '127.0.0.1' && bindHost !== 'localhost' && bindHost !== '::1') {
    console.warn(
      `[POS] POS_BIND_HOST=${bindHost}. Password login is disabled, so only expose this server on a trusted store network or behind an authenticated reverse proxy.`,
    );
  }
}

function getCustomerFirestore() {
  if (!firebaseProjectId) return null;
  if (customerFirestore) return customerFirestore;

  const appName = 'pumpkin-pos-firestore';
  const firebaseApp = getApps().find((item) => item.name === appName)
    || initializeApp(
      {
        credential: applicationDefault(),
        projectId: firebaseProjectId,
      },
      appName,
    );

  customerFirestore = getFirestore(firebaseApp);
  return customerFirestore;
}

async function enrichOrderCustomerNames(orders) {
  if (!Array.isArray(orders)) return orders;

  const db = getCustomerFirestore();
  if (!db) return orders;

  const now = Date.now();
  const customerIds = [...new Set(
    orders
      .map((order) => String(order?.customer_id || '').trim())
      .filter(Boolean),
  )];

  const staleIds = customerIds.filter((uid) => {
    const cached = customerNameCache.get(uid);
    return !cached || now - cached.loadedAt >= CUSTOMER_NAME_CACHE_MS;
  });

  if (staleIds.length > 0) {
    try {
      const snapshots = await db.getAll(
        ...staleIds.map((uid) => db.collection('users').doc(uid)),
      );

      snapshots.forEach((snapshot) => {
        const data = snapshot.data() || {};
        const name = typeof data.name === 'string' ? data.name.trim() : '';
        customerNameCache.set(snapshot.id, {
          name: name || null,
          loadedAt: now,
        });
      });
    } catch (error) {
      console.warn(`[POS] Firestore customer name lookup failed: ${error?.message}`);
      return orders;
    }
  }

  return orders.map((order) => {
    const uid = String(order?.customer_id || '').trim();
    const name = uid ? customerNameCache.get(uid)?.name : null;
    if (!name) return order;

    return {
      ...order,
      metadata: {
        ...(order.metadata || {}),
        customer_name: name,
      },
    };
  });
}

async function relay(pathname, init = {}) {
  if (!relayBaseUrl || !relayToken) {
    const error = new Error('POS Relay 환경 변수가 설정되지 않았습니다.');
    error.status = 503;
    throw error;
  }
  const response = await fetch(`${relayBaseUrl}${pathname}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Relay-Token': relayToken,
      ...(init.headers || {}),
    },
  });
  const raw = await response.text();
  let body = null;
  try {
    body = raw ? JSON.parse(raw) : null;
  } catch {
    body = { detail: raw || `Relay HTTP ${response.status}` };
  }
  if (!response.ok) {
    const error = new Error(body?.detail || `Relay HTTP ${response.status}`);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

function sendApiError(res, error) {
  const status = Number(error?.status || 500);
  res.status(status).json(error?.body || { detail: error?.message || 'POS 서버 오류' });
}

function demoModePayload() {
  return {
    enabled: demoModeEnabled,
    persistent: true,
    rules: {
      APP: [
        { from: 'RECEIVED', to: 'PREPARING', delay_ms: DEMO_DELAYS_MS.RECEIVED },
        { from: 'PREPARING', to: 'READY', delay_ms: DEMO_DELAYS_MS.PREPARING },
        { from: 'READY', to: null, reason: 'WAIT_FACE_PICKUP' },
      ],
      ROBOT: [
        { from: 'RECEIVED', to: 'PREPARING', delay_ms: DEMO_DELAYS_MS.RECEIVED },
        { from: 'PREPARING', to: 'READY', delay_ms: DEMO_DELAYS_MS.PREPARING },
        { from: 'READY', to: 'PICKED_UP', delay_ms: DEMO_DELAYS_MS.ROBOT_READY },
      ],
    },
  };
}

function nextDemoStatus(order) {
  if (!order || !['APP', 'ROBOT'].includes(order.source)) return null;
  if (order.status === 'RECEIVED') {
    return { status: 'PREPARING', delayMs: DEMO_DELAYS_MS.RECEIVED };
  }
  if (order.status === 'PREPARING') {
    return { status: 'READY', delayMs: DEMO_DELAYS_MS.PREPARING };
  }
  if (order.status === 'READY' && order.source === 'ROBOT') {
    return { status: 'PICKED_UP', delayMs: DEMO_DELAYS_MS.ROBOT_READY };
  }
  return null;
}

async function runDemoFlow() {
  if (!demoModeEnabled || demoWorkerBusy || !relayBaseUrl || !relayToken) return;
  demoWorkerBusy = true;
  try {
    const orders = await relay('/api/v1/orders?limit=200');
    const now = Date.now();
    for (const order of Array.isArray(orders) ? orders : []) {
      if (!demoModeEnabled) break;
      const transition = nextDemoStatus(order);
      if (!transition) continue;
      const updatedAt = Date.parse(order.updated_at || order.created_at || '');
      if (!Number.isFinite(updatedAt) || now - updatedAt < transition.delayMs) continue;
      try {
        await relay(`/api/v1/orders/${encodeURIComponent(order.order_id)}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ status: transition.status }),
        });
        console.log(
          `[POS DEMO] ${order.order_number || order.order_id}: ${order.status} -> ${transition.status}`,
        );
      } catch (error) {
        if (Number(error?.status) !== 409) {
          console.warn(
            `[POS DEMO] Failed ${order.order_id} ${order.status} -> ${transition.status}: ${error?.message}`,
          );
        }
      }
    }
  } catch (error) {
    console.warn(`[POS DEMO] Poll failed: ${error?.message}`);
  } finally {
    demoWorkerBusy = false;
  }
}

app.disable('x-powered-by');
app.use(express.json({ limit: '64kb' }));

// Compatibility endpoints for the current frontend. The 2026 demo/internal POS
// intentionally has no administrator password screen. Relay credentials still
// remain server-only and are never returned to the browser.
app.get('/api/auth/session', (_req, res) => {
  res.json({ authenticated: true, mode: 'passwordless-local' });
});

app.post('/api/auth/login', (_req, res) => {
  res.json({ authenticated: true, mode: 'passwordless-local' });
});

app.post('/api/auth/logout', (_req, res) => {
  res.json({ authenticated: true, mode: 'passwordless-local' });
});

app.get('/api/orders', async (req, res) => {
  try {
    const params = new URLSearchParams();
    const source = String(req.query.source || '').toUpperCase();
    const status = String(req.query.status || '').toUpperCase();
    const limit = Math.min(200, Math.max(1, Number(req.query.limit || 100)));
    if (source && ['APP', 'ROBOT', 'POS'].includes(source)) params.set('source', source);
    if (status && ALLOWED_STATUSES.has(status)) params.set('status', status);
    params.set('limit', String(limit));
    const orders = await relay(`/api/v1/orders?${params.toString()}`);
    res.json(await enrichOrderCustomerNames(orders));
  } catch (error) {
    sendApiError(res, error);
  }
});

app.patch('/api/orders/:orderId/status', async (req, res) => {
  try {
    const status = String(req.body?.status || '').toUpperCase();
    if (!ALLOWED_STATUSES.has(status)) {
      return res.status(400).json({ detail: '지원하지 않는 주문 상태입니다.' });
    }
    const order = await relay(`/api/v1/orders/${encodeURIComponent(req.params.orderId)}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    res.json(order);
  } catch (error) {
    sendApiError(res, error);
  }
});

app.get('/api/demo-mode', (_req, res) => {
  res.json(demoModePayload());
});

app.patch('/api/demo-mode', (req, res) => {
  if (typeof req.body?.enabled !== 'boolean') {
    return res.status(400).json({ detail: 'enabled는 boolean이어야 합니다.' });
  }
  try {
    demoModeEnabled = req.body.enabled;
    persistDemoModeEnabled(demoModeEnabled);
  } catch (error) {
    return res.status(500).json({ detail: `DEMO MODE 상태 저장 실패: ${error?.message}` });
  }
  console.log(`[POS DEMO] mode ${demoModeEnabled ? 'ON' : 'OFF'} (persisted)`);
  if (demoModeEnabled) void runDemoFlow();
  res.json(demoModePayload());
});

app.get('/api/menus', (_req, res) => {
  try {
    const catalog = JSON.parse(fs.readFileSync(menuCatalogPath, 'utf8'));
    res.json({
      schema_version: catalog.schema_version,
      read_only: true,
      menus: Array.isArray(catalog.menus) ? catalog.menus : [],
    });
  } catch (error) {
    sendApiError(res, error);
  }
});

app.get('/api/health', async (_req, res) => {
  try {
    if (!relayBaseUrl) {
      return res.status(503).json({ detail: 'POS_RELAY_BASE_URL이 설정되지 않았습니다.' });
    }
    const response = await fetch(`${relayBaseUrl}/health`, { headers: { Accept: 'application/json' } });
    const body = await response.json();
    res.status(response.ok ? 200 : response.status).json(body);
  } catch (error) {
    sendApiError(res, error);
  }
});

if (fs.existsSync(distDir)) {
  app.use(express.static(distDir));
  app.get('*', (_req, res) => res.sendFile(path.join(distDir, 'index.html')));
}

assertServerConfig();
console.log(`[POS DEMO] restored mode ${demoModeEnabled ? 'ON' : 'OFF'}`);
setInterval(() => void runDemoFlow(), 500);
app.listen(port, bindHost, () => {
  console.log(`[POS] server listening on http://${bindHost}:${port} (passwordless local mode)`);
});
