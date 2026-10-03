import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './manufacturing-board.css';

type OrderSource = 'APP' | 'ROBOT' | 'POS';
type OrderStatus = 'RECEIVED' | 'PREPARING' | 'READY' | 'PICKED_UP' | 'CANCELLED';
type Temperature = 'HOT' | 'ICE' | 'NONE';
type Page = 'dashboard' | 'orders' | 'menus' | 'customers';

type OrderItem = {
  id: string;
  menu_id: number;
  menu_name: string;
  temperature: Temperature;
  size: 'SMALL' | 'MEDIUM' | 'LARGE' | 'NONE';
  quantity: number;
  options: string[];
  unit_price: number;
};

type Order = {
  order_id: string;
  order_number: string;
  request_id: string;
  source: OrderSource;
  customer_id: string | null;
  status: OrderStatus;
  items: OrderItem[];
  original_text: string | null;
  metadata: Record<string, unknown>;
  total_price: number;
  created_at: string;
  updated_at: string;
};

type Menu = {
  menu_id: number;
  name: string;
  eng_name: string;
  aliases: string[];
  category: string;
  price: number;
  available_temperatures: Temperature[];
  is_available: boolean;
  image: string | null;
  description: string;
};

type MenuResponse = {
  schema_version: string;
  read_only: boolean;
  menus: Menu[];
};

type DemoMode = {
  enabled: boolean;
  rules: Record<string, Array<{ from: string; to: string | null; delay_ms?: number; reason?: string }>>;
};

type CustomerSummary = {
  customer_id: string;
  name: string | null;
  orderCount: number;
  appOrderCount: number;
  totalSpend: number;
  lastOrderAt: string;
  favoriteMenu: string | null;
  favoriteTemperature: Temperature | null;
  latestOrder: Order;
  orders: Order[];
};

const STATUS_LABEL: Record<OrderStatus, string> = {
  RECEIVED: '주문 접수',
  PREPARING: '제조 중',
  READY: '픽업 대기',
  PICKED_UP: '완료',
  CANCELLED: '취소',
};

const SOURCE_LABEL: Record<OrderSource, string> = {
  APP: 'APP PREORDER',
  ROBOT: 'ROBOT ORDER',
  POS: 'POS ORDER',
};

const PAGE_META: Record<Page, { eyebrow: string; title: string; description: string }> = {
  dashboard: { eyebrow: 'OVERVIEW', title: '대시보드', description: '오늘 매장 주문과 진행 상태를 확인합니다.' },
  orders: { eyebrow: 'ORDERS', title: '주문 관리', description: '전체 주문을 조회하고 허용된 상태 전이를 처리합니다.' },
  menus: { eyebrow: 'MENU MANAGEMENT', title: '메뉴 관리', description: '공식 메뉴 카탈로그를 조회합니다.' },
  customers: { eyebrow: 'CUSTOMERS', title: '고객 관리', description: '주문 이력 기준 고객 현황을 확인합니다.' },
};

const ACTIVE_STATUSES = new Set<OrderStatus>(['RECEIVED', 'PREPARING', 'READY']);
const BOARD_STAGES: Array<{ status: Extract<OrderStatus, 'RECEIVED' | 'PREPARING' | 'READY'>; eyebrow: string; title: string; description: string }> = [
  { status: 'RECEIVED', eyebrow: '01 RECEIVED', title: '주문 접수', description: '새 주문 · 제조 시작 대기' },
  { status: 'PREPARING', eyebrow: '02 PREPARING', title: '제조 중', description: '현재 음료를 제조하고 있습니다' },
  { status: 'READY', eyebrow: '03 READY', title: '준비 완료', description: '픽업 안내 또는 수령 대기' },
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail || `HTTP ${response.status}`);
  return body as T;
}

function formatWon(value: number) {
  return `${new Intl.NumberFormat('ko-KR').format(value)}원`;
}

function formatTime(value: string, includeSeconds = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    ...(includeSeconds ? { second: '2-digit' as const } : {}),
  }).format(date);
}

function isToday(value: string) {
  const date = new Date(value);
  const now = new Date();
  return date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate();
}

function nextActions(status: OrderStatus) {
  if (status === 'RECEIVED') return [
    { label: '제조 시작', status: 'PREPARING' as OrderStatus, kind: 'primary' },
    { label: '주문 취소', status: 'CANCELLED' as OrderStatus, kind: 'danger' },
  ];
  if (status === 'PREPARING') return [
    { label: '준비 완료', status: 'READY' as OrderStatus, kind: 'primary' },
    { label: '주문 취소', status: 'CANCELLED' as OrderStatus, kind: 'danger' },
  ];
  if (status === 'READY') return [
    { label: '픽업 완료', status: 'PICKED_UP' as OrderStatus, kind: 'primary' },
  ];
  return [];
}

function routeToPage(pathname: string): Page {
  if (pathname.startsWith('/orders')) return 'orders';
  if (pathname.startsWith('/menus')) return 'menus';
  if (pathname.startsWith('/customers')) return 'customers';
  return 'dashboard';
}

function customerDisplayName(order: Order) {
  const metadataName = typeof order.metadata?.customer_name === 'string' ? order.metadata.customer_name.trim() : '';
  return metadataName || null;
}

function buildCustomers(orders: Order[]): CustomerSummary[] {
  const grouped = new Map<string, Order[]>();
  for (const order of orders) {
    if (!order.customer_id) continue;
    const list = grouped.get(order.customer_id) || [];
    list.push(order);
    grouped.set(order.customer_id, list);
  }

  return [...grouped.entries()].map(([customerId, customerOrders]) => {
    const sorted = [...customerOrders].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
    const menuCounts = new Map<string, number>();
    const tempCounts = new Map<Temperature, number>();
    for (const order of sorted) {
      if (order.status === 'CANCELLED') continue;
      for (const item of order.items) {
        menuCounts.set(item.menu_name, (menuCounts.get(item.menu_name) || 0) + item.quantity);
        tempCounts.set(item.temperature, (tempCounts.get(item.temperature) || 0) + item.quantity);
      }
    }
    const favoriteMenu = [...menuCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || null;
    const favoriteTemperature = [...tempCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || null;
    return {
      customer_id: customerId,
      name: sorted.map(customerDisplayName).find(Boolean) || null,
      orderCount: sorted.length,
      appOrderCount: sorted.filter((order) => order.source === 'APP').length,
      totalSpend: sorted.filter((order) => order.status !== 'CANCELLED').reduce((sum, order) => sum + order.total_price, 0),
      lastOrderAt: sorted[0].created_at,
      favoriteMenu,
      favoriteTemperature,
      latestOrder: sorted[0],
      orders: sorted,
    };
  }).sort((a, b) => Date.parse(b.lastOrderAt) - Date.parse(a.lastOrderAt));
}

function Status({ status }: { status: OrderStatus }) {
  return <span className={`status-text status-${status.toLowerCase()}`}><i />{STATUS_LABEL[status]}</span>;
}

function Source({ source }: { source: OrderSource }) {
  return <span className="source-label">{SOURCE_LABEL[source]}</span>;
}

function DemoProgress({ order, enabled, now }: { order: Order; enabled: boolean; now: number }) {
  if (!enabled || !['APP', 'ROBOT'].includes(order.source)) return null;
  if (order.status === 'READY' && order.source === 'APP') {
    return <span className="demo-progress">AUTO FLOW · 얼굴인식 픽업 대기</span>;
  }
  let delay = 0;
  let next = '';
  if (order.status === 'RECEIVED') {
    delay = 1000;
    next = 'PREPARING';
  } else if (order.status === 'PREPARING') {
    delay = 5000;
    next = 'READY';
  } else if (order.status === 'READY' && order.source === 'ROBOT') {
    delay = 3000;
    next = 'PICKED_UP';
  } else {
    return null;
  }
  const updatedAt = Date.parse(order.updated_at || order.created_at);
  const remaining = Number.isFinite(updatedAt) ? Math.max(0, delay - (now - updatedAt)) : delay;
  return <span className="demo-progress">AUTO FLOW · {next} 약 {(remaining / 1000).toFixed(1)}초 후</span>;
}

function manufacturingMessage(order: Order, demoEnabled: boolean) {
  if (order.status === 'RECEIVED') return '접수됨 · 제조 시작 대기';
  if (order.status === 'PREPARING') return '음료 제조 중';
  if (order.status === 'READY' && order.source === 'APP') return '준비 완료 · 얼굴인식 픽업 대기';
  if (order.status === 'READY' && order.source === 'ROBOT' && demoEnabled) return '준비 완료 · 자동 픽업 처리 중';
  if (order.status === 'READY') return '준비 완료 · 픽업 대기';
  return STATUS_LABEL[order.status];
}

function ManufacturingProgress({ status }: { status: OrderStatus }) {
  const currentIndex = status === 'RECEIVED' ? 0 : status === 'PREPARING' ? 1 : 2;
  const labels = ['접수', '제조 중', '준비 완료'];
  return <div className="manufacturing-progress" aria-label={`제조 진행: ${labels[currentIndex]}`}>
    {labels.map((label, index) => <div key={label} className={`manufacturing-step ${index <= currentIndex ? 'done' : ''} ${index === currentIndex ? 'current' : ''}`}>
      <i />
      <span>{label}</span>
    </div>)}
  </div>;
}

function ManufacturingCard({ order, onOpen, onStatus, busy, demoEnabled, now }: {
  order: Order;
  onOpen: (order: Order) => void;
  onStatus: (order: Order, status: OrderStatus) => void;
  busy: boolean;
  demoEnabled: boolean;
  now: number;
}) {
  const actions = nextActions(order.status);
  return <article className={`manufacturing-card manufacturing-card-${order.status.toLowerCase()}`}>
    <button className="manufacturing-card-body" onClick={() => onOpen(order)}>
      <div className="manufacturing-card-head">
        <div>
          <span className="order-number">{order.order_number}</span>
          <Source source={order.source} />
        </div>
        <span className="manufacturing-time">{formatTime(order.created_at, true)}</span>
      </div>
      <div className="manufacturing-items">
        {order.items.slice(0, 3).map((item) => <div key={item.id}>
          <strong>{item.menu_name}</strong>
          <span>{item.temperature === 'NONE' ? '온도 없음' : item.temperature} · {item.quantity}잔</span>
        </div>)}
        {order.items.length > 3 && <span className="more-items">외 {order.items.length - 3}개 품목</span>}
      </div>
      <ManufacturingProgress status={order.status} />
      <div className="manufacturing-card-foot">
        <span className="manufacturing-message">{manufacturingMessage(order, demoEnabled)}</span>
        <strong>{formatWon(order.total_price)}</strong>
      </div>
      <DemoProgress order={order} enabled={demoEnabled} now={now} />
    </button>
    {actions.length > 0 && <div className="manufacturing-card-actions">
      {actions.map((action) => <button
        key={action.status}
        className={`button ${action.kind}`}
        disabled={busy}
        onClick={() => onStatus(order, action.status)}
      >{busy ? '처리 중…' : action.label}</button>)}
    </div>}
  </article>;
}

function ManufacturingBoard({ orders, onOpen, onStatus, busyOrder, demoEnabled, now, relayHealthy }: {
  orders: Order[];
  onOpen: (order: Order) => void;
  onStatus: (order: Order, status: OrderStatus) => void;
  busyOrder: string | null;
  demoEnabled: boolean;
  now: number;
  relayHealthy: boolean | null;
}) {
  const active = orders
    .filter((order) => ACTIVE_STATUSES.has(order.status))
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const recentCompleted = orders
    .filter((order) => order.status === 'PICKED_UP' && isToday(order.updated_at || order.created_at))
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
    .slice(0, 4);

  return <section className="content-section manufacturing-section">
    <div className="section-heading manufacturing-heading">
      <div><span className="eyebrow">LIVE MANUFACTURING</span><h2>제조 흐름</h2></div>
      <span className={`board-live ${relayHealthy ? 'online' : relayHealthy === false ? 'offline' : ''}`}><i />{relayHealthy ? 'LIVE' : relayHealthy === false ? 'OFFLINE' : 'CONNECTING'}</span>
    </div>

    <div className="manufacturing-board-shell">
      <div className="manufacturing-board">
        {BOARD_STAGES.map((stage) => {
          const stageOrders = active.filter((order) => order.status === stage.status);
          return <section className={`manufacturing-column column-${stage.status.toLowerCase()}`} key={stage.status}>
            <header className="manufacturing-column-head">
              <div>
                <span className="eyebrow">{stage.eyebrow}</span>
                <h3>{stage.title}</h3>
                <p>{stage.description}</p>
              </div>
              <strong>{stageOrders.length}</strong>
            </header>
            <div className="manufacturing-column-list">
              {stageOrders.map((order) => <ManufacturingCard
                key={order.order_id}
                order={order}
                onOpen={onOpen}
                onStatus={onStatus}
                busy={busyOrder === order.order_id}
                demoEnabled={demoEnabled}
                now={now}
              />)}
              {stageOrders.length === 0 && <div className="manufacturing-column-empty">현재 주문 없음</div>}
            </div>
          </section>;
        })}
      </div>
    </div>

    <div className="recent-completed-block">
      <div className="recent-completed-head">
        <div><span className="eyebrow">RECENTLY COMPLETED</span><h3>최근 완료</h3></div>
        <span>상태 전이 결과를 잠시 확인할 수 있습니다.</span>
      </div>
      {recentCompleted.length > 0 ? <div className="recent-completed-list">
        {recentCompleted.map((order) => <button key={order.order_id} className="recent-completed-row" onClick={() => onOpen(order)}>
          <Source source={order.source} />
          <strong>{order.items.map((item) => `${item.menu_name} ×${item.quantity}`).join(', ')}</strong>
          <span>{order.source === 'ROBOT' ? '픽업 완료' : '수령 완료'}</span>
          <time>{formatTime(order.updated_at, true)}</time>
        </button>)}
      </div> : <div className="recent-completed-empty">오늘 완료된 주문이 아직 없습니다.</div>}
    </div>
  </section>;
}

function OrderDrawer({ order, onClose, onStatus, busy }: {
  order: Order;
  onClose: () => void;
  onStatus: (order: Order, status: OrderStatus) => void;
  busy: boolean;
}) {
  const actions = nextActions(order.status);
  return <div className="drawer-backdrop" onMouseDown={onClose}>
    <aside className="drawer" onMouseDown={(event) => event.stopPropagation()}>
      <header className="drawer-header">
        <div><span className="eyebrow">ORDER DETAIL</span><h2>{order.order_number}</h2></div>
        <button className="icon-button" onClick={onClose} aria-label="닫기">×</button>
      </header>
      <div className="drawer-meta">
        <Source source={order.source} />
        <Status status={order.status} />
        <span>{formatTime(order.created_at, true)}</span>
      </div>
      <section className="drawer-section">
        <span className="eyebrow">ITEMS</span>
        {order.items.map((item) => <div className="detail-item" key={item.id}>
          <div className="detail-item-title"><strong>{item.menu_name}</strong><strong>{formatWon(item.unit_price * item.quantity)}</strong></div>
          <dl>
            <div><dt>MENU ID</dt><dd>{item.menu_id}</dd></div>
            <div><dt>TEMPERATURE</dt><dd>{item.temperature}</dd></div>
            <div><dt>QUANTITY</dt><dd>{item.quantity}</dd></div>
            <div><dt>UNIT PRICE</dt><dd>{formatWon(item.unit_price)}</dd></div>
          </dl>
        </div>)}
      </section>
      <section className="drawer-total"><span>TOTAL PRICE</span><strong>{formatWon(order.total_price)}</strong></section>
      <section className="drawer-section">
        <span className="eyebrow">CUSTOMER</span>
        <p className="mono-line">{order.customer_id || '비회원 / 미지정'}</p>
      </section>
      {actions.length > 0 && <footer className="drawer-actions">
        {actions.map((action) => <button
          key={action.status}
          className={`button ${action.kind}`}
          disabled={busy}
          onClick={() => onStatus(order, action.status)}
        >{busy ? '처리 중…' : action.label}</button>)}
      </footer>}
    </aside>
  </div>;
}

function MenuDrawer({ menu, onClose }: { menu: Menu; onClose: () => void }) {
  return <div className="drawer-backdrop" onMouseDown={onClose}>
    <aside className="drawer" onMouseDown={(event) => event.stopPropagation()}>
      <header className="drawer-header">
        <div><span className="eyebrow">MENU DETAIL</span><h2>{menu.name}</h2></div>
        <button className="icon-button" onClick={onClose} aria-label="닫기">×</button>
      </header>
      <div className="menu-title-block"><strong>{menu.eng_name}</strong><span>MENU ID {menu.menu_id}</span></div>
      <section className="drawer-section">
        <dl className="detail-list">
          <div><dt>CATEGORY</dt><dd>{menu.category}</dd></div>
          <div><dt>PRICE</dt><dd>{formatWon(menu.price)}</dd></div>
          <div><dt>TEMPERATURE</dt><dd>{menu.available_temperatures.join(' / ')}</dd></div>
          <div><dt>SALE</dt><dd>{menu.is_available ? '판매 중' : '판매 중지'}</dd></div>
          <div><dt>ALIASES</dt><dd>{menu.aliases.join(', ')}</dd></div>
        </dl>
      </section>
      <section className="drawer-section">
        <span className="eyebrow">DESCRIPTION</span>
        <p>{menu.description}</p>
      </section>
      <div className="read-only-note">현재 메뉴 페이지는 <code>config/menu_catalog.json</code> 기준 조회 전용입니다.</div>
    </aside>
  </div>;
}

function CustomerDrawer({ customer, onClose }: { customer: CustomerSummary; onClose: () => void }) {
  return <div className="drawer-backdrop" onMouseDown={onClose}>
    <aside className="drawer wide" onMouseDown={(event) => event.stopPropagation()}>
      <header className="drawer-header">
        <div><span className="eyebrow">CUSTOMER DETAIL</span><h2>{customer.name || '고객'}</h2></div>
        <button className="icon-button" onClick={onClose} aria-label="닫기">×</button>
      </header>
      <p className="mono-line customer-uid">{customer.customer_id}</p>
      <section className="customer-stats">
        <div><span>ORDER COUNT</span><strong>{customer.orderCount}</strong></div>
        <div><span>APP PREORDER</span><strong>{customer.appOrderCount}</strong></div>
        <div><span>TOTAL SPEND</span><strong>{formatWon(customer.totalSpend)}</strong></div>
      </section>
      <section className="drawer-section">
        <span className="eyebrow">ORDER-BASED PREFERENCE</span>
        <dl className="detail-list">
          <div><dt>자주 주문한 메뉴</dt><dd>{customer.favoriteMenu || '-'}</dd></div>
          <div><dt>자주 선택한 온도</dt><dd>{customer.favoriteTemperature || '-'}</dd></div>
          <div><dt>최근 주문</dt><dd>{formatTime(customer.lastOrderAt, true)}</dd></div>
        </dl>
      </section>
      <div className="profile-pending">
        <strong>FACE / REGULAR PROFILE</strong>
        <p>실제 얼굴 등록 정보와 앱 선호 정보는 Firestore <code>users/{'{uid}'}</code> 관리자 조회 API가 아직 POS 계약에 없어서 연결하지 않았습니다. 주문 이력과 임의로 합치지 않습니다.</p>
      </div>
      <section className="drawer-section">
        <span className="eyebrow">ORDER HISTORY</span>
        <div className="history-list">
          {customer.orders.slice(0, 12).map((order) => <div className="history-row" key={order.order_id}>
            <div><strong>{order.order_number}</strong><span>{order.items.map((item) => `${item.menu_name} ×${item.quantity}`).join(', ')}</span></div>
            <div><Status status={order.status} /><strong>{formatWon(order.total_price)}</strong></div>
          </div>)}
        </div>
      </section>
    </aside>
  </div>;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [menus, setMenus] = useState<Menu[]>([]);
  const [page, setPage] = useState<Page>(() => routeToPage(window.location.pathname));
  const [sourceFilter, setSourceFilter] = useState<'ALL' | OrderSource>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ACTIVE' | 'ALL' | OrderStatus>('ACTIVE');
  const [searchText, setSearchText] = useState('');
  const [busyOrder, setBusyOrder] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [relayHealthy, setRelayHealthy] = useState<boolean | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [notice, setNotice] = useState('');
  const [demoMode, setDemoMode] = useState<DemoMode | null>(null);
  const [demoBusy, setDemoBusy] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [selectedMenu, setSelectedMenu] = useState<Menu | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null);
  const [now, setNow] = useState(Date.now());
  const knownOrderIds = useRef<Set<string> | null>(null);

  const navigate = useCallback((next: Page) => {
    setPage(next);
    window.history.pushState({}, '', next === 'dashboard' ? '/dashboard' : `/${next}`);
  }, []);

  useEffect(() => {
    const onPopState = () => setPage(routeToPage(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    api<{ authenticated: boolean }>('/api/auth/session')
      .then((result) => setAuthenticated(result.authenticated))
      .catch(() => setAuthenticated(false));
  }, []);

  const loadOrders = useCallback(async (announce = true) => {
    if (!authenticated) return;
    try {
      const next = await api<Order[]>('/api/orders?limit=200');
      if (knownOrderIds.current && announce) {
        const newcomers = next.filter((order) => !knownOrderIds.current!.has(order.order_id));
        if (newcomers.length) {
          setNotice(`NEW ORDER · ${SOURCE_LABEL[newcomers[0].source]} · ${newcomers[0].order_number}`);
          window.setTimeout(() => setNotice(''), 3500);
        }
      }
      knownOrderIds.current = new Set(next.map((order) => order.order_id));
      setOrders(next);
      setSelectedOrder((current) => current ? next.find((order) => order.order_id === current.order_id) || current : null);
      setLastUpdated(new Date());
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '주문을 불러오지 못했습니다.');
    }
  }, [authenticated]);

  const loadMenus = useCallback(async () => {
    if (!authenticated) return;
    try {
      const result = await api<MenuResponse>('/api/menus');
      setMenus(result.menus);
    } catch (err) {
      setError(err instanceof Error ? err.message : '메뉴를 불러오지 못했습니다.');
    }
  }, [authenticated]);

  const loadDemoMode = useCallback(async () => {
    if (!authenticated) return;
    try {
      setDemoMode(await api<DemoMode>('/api/demo-mode'));
    } catch (err) {
      setError(err instanceof Error ? err.message : '시연모드 상태를 불러오지 못했습니다.');
    }
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated) return;
    loadOrders(false);
    loadMenus();
    loadDemoMode();
    const timer = window.setInterval(() => loadOrders(true), 2000);
    return () => window.clearInterval(timer);
  }, [authenticated, loadOrders, loadMenus, loadDemoMode]);

  useEffect(() => {
    if (!authenticated) return;
    const check = () => api('/api/health').then(() => setRelayHealthy(true)).catch(() => setRelayHealthy(false));
    check();
    const timer = window.setInterval(check, 10000);
    return () => window.clearInterval(timer);
  }, [authenticated]);

  useEffect(() => {
    if (!demoMode?.enabled) return;
    const timer = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(timer);
  }, [demoMode?.enabled]);

  const filteredOrders = useMemo(() => orders.filter((order) => {
    if (sourceFilter !== 'ALL' && order.source !== sourceFilter) return false;
    if (statusFilter === 'ACTIVE' && !ACTIVE_STATUSES.has(order.status)) return false;
    if (statusFilter !== 'ALL' && statusFilter !== 'ACTIVE' && order.status !== statusFilter) return false;
    const query = searchText.trim().toLowerCase();
    if (!query) return true;
    return [
      order.order_number,
      order.customer_id || '',
      ...order.items.flatMap((item) => [item.menu_name, String(item.menu_id)]),
    ].some((value) => value.toLowerCase().includes(query));
  }), [orders, sourceFilter, statusFilter, searchText]);

  const customers = useMemo(() => buildCustomers(orders), [orders]);
  const todayOrders = orders.filter((order) => isToday(order.created_at));
  const todayRevenue = todayOrders
    .filter((order) => order.status !== 'CANCELLED')
    .reduce((sum, order) => sum + order.total_price, 0);
  const activeCount = orders.filter((order) => ACTIVE_STATUSES.has(order.status)).length;
  const readyCount = orders.filter((order) => order.status === 'READY').length;
  const completedToday = todayOrders.filter((order) => order.status === 'PICKED_UP').length;

  async function updateStatus(order: Order, status: OrderStatus) {
    setBusyOrder(order.order_id);
    setError('');
    try {
      const updated = await api<Order>(`/api/orders/${encodeURIComponent(order.order_id)}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      });
      setOrders((current) => current.map((item) => item.order_id === updated.order_id ? updated : item));
      setSelectedOrder((current) => current?.order_id === updated.order_id ? updated : current);
      await loadOrders(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : '상태 변경에 실패했습니다.');
    } finally {
      setBusyOrder(null);
    }
  }

  async function toggleDemoMode() {
    if (!demoMode || demoBusy) return;
    setDemoBusy(true);
    try {
      const next = await api<DemoMode>('/api/demo-mode', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !demoMode.enabled }),
      });
      setDemoMode(next);
      setNow(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : '시연모드를 변경하지 못했습니다.');
    } finally {
      setDemoBusy(false);
    }
  }

  if (authenticated === null) return <div className="center-message">POS를 준비하고 있습니다…</div>;
  if (!authenticated) return <div className="center-message">POS 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해주세요.</div>;

  const meta = PAGE_META[page];

  return <div className="pos-shell">
    <header className="global-header">
      <div className="brand-line">
        <div><span className="brand-name">PUMPKIN STORE</span><span className="brand-sub">MANAGER POS</span></div>
        <div className="header-actions">
          <span className={`live-indicator ${relayHealthy ? 'online' : relayHealthy === false ? 'offline' : ''}`}><i />{relayHealthy ? 'LIVE' : relayHealthy === false ? 'OFFLINE' : 'CONNECTING'}</span>
          <button className={`demo-toggle ${demoMode?.enabled ? 'on' : ''}`} onClick={toggleDemoMode} disabled={!demoMode || demoBusy}>
            <span>DEMO MODE</span><b>{demoMode?.enabled ? 'ON' : 'OFF'}</b>
          </button>
        </div>
      </div>
      <nav className="global-nav">
        {(['dashboard', 'orders', 'menus', 'customers'] as Page[]).map((navPage) => <button
          key={navPage}
          className={page === navPage ? 'active' : ''}
          onClick={() => navigate(navPage)}
        >{PAGE_META[navPage].title}</button>)}
      </nav>
    </header>

    <main className="page-shell">
      <div className="page-heading">
        <div><span className="eyebrow">{meta.eyebrow}</span><h1>{meta.title}</h1><p>{meta.description}</p></div>
        <div className="page-heading-right">
          {demoMode?.enabled && <span className="demo-active">AUTO FLOW ACTIVE</span>}
          <span>{lastUpdated ? `최근 갱신 ${lastUpdated.toLocaleTimeString('ko-KR')}` : '동기화 중'}</span>
        </div>
      </div>

      {notice && <div className="notice-banner">{notice}</div>}
      {error && <div className="error-banner"><span>{error}</span><button onClick={() => setError('')}>닫기</button></div>}

      {page === 'dashboard' && <>
        <section className="metrics-strip">
          <div><span>TODAY ORDERS</span><strong>{todayOrders.length}</strong><small>건</small></div>
          <div><span>TODAY SALES</span><strong className="metric-money">{formatWon(todayRevenue)}</strong></div>
          <div><span>ACTIVE</span><strong>{activeCount}</strong><small>건</small></div>
          <div><span>PICKUP READY</span><strong>{readyCount}</strong><small>건</small></div>
        </section>

        <ManufacturingBoard
          orders={orders}
          onOpen={setSelectedOrder}
          onStatus={updateStatus}
          busyOrder={busyOrder}
          demoEnabled={Boolean(demoMode?.enabled)}
          now={now}
          relayHealthy={relayHealthy}
        />

        <div className="dashboard-all-orders-link">
          <button className="text-button" onClick={() => navigate('orders')}>전체 주문 보기 →</button>
        </div>
        <section className="dashboard-foot">
          <div><span>COMPLETED TODAY</span><strong>{completedToday}</strong><small>건</small></div>
          <div><span>APP PREORDER</span><strong>{todayOrders.filter((order) => order.source === 'APP').length}</strong><small>건</small></div>
          <div><span>ROBOT ORDER</span><strong>{todayOrders.filter((order) => order.source === 'ROBOT').length}</strong><small>건</small></div>
        </section>
      </>}

      {page === 'orders' && <section className="content-section flush-top">
        <div className="summary-tabs">
          <span>진행 주문 <strong>{activeCount}</strong></span>
          <span>픽업 완료 <strong>{orders.filter((order) => order.status === 'PICKED_UP').length}</strong></span>
          <span>취소 <strong>{orders.filter((order) => order.status === 'CANCELLED').length}</strong></span>
        </div>
        <div className="filter-bar">
          <label><span>검색</span><input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="주문번호 · 메뉴 · 고객 UID" /></label>
          <label><span>주문 유형</span><select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as 'ALL' | OrderSource)}><option value="ALL">전체</option><option value="APP">APP</option><option value="ROBOT">ROBOT</option><option value="POS">POS</option></select></label>
          <label><span>상태</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}><option value="ACTIVE">진행 주문</option><option value="ALL">전체</option>{Object.keys(STATUS_LABEL).map((status) => <option key={status} value={status}>{STATUS_LABEL[status as OrderStatus]}</option>)}</select></label>
          <button className="button secondary refresh-button" onClick={() => loadOrders(false)}>새로고침</button>
        </div>
        <div className="table-wrap">
          <table className="data-table orders-table">
            <thead><tr><th>주문번호</th><th>유형</th><th>주문 내용</th><th>금액</th><th>상태</th><th>시간</th></tr></thead>
            <tbody>
              {filteredOrders.map((order) => <tr key={order.order_id} onClick={() => setSelectedOrder(order)}>
                <td><strong>{order.order_number}</strong></td>
                <td><Source source={order.source} /></td>
                <td><div className="table-items">{order.items.map((item) => <span key={item.id}>{item.menu_name} {item.temperature !== 'NONE' ? item.temperature : ''} ×{item.quantity}</span>)}</div></td>
                <td>{formatWon(order.total_price)}</td>
                <td><Status status={order.status} /></td>
                <td>{formatTime(order.created_at)}</td>
              </tr>)}
              {filteredOrders.length === 0 && <tr><td colSpan={6} className="table-empty">조건에 맞는 주문이 없습니다.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>}

      {page === 'menus' && <section className="content-section flush-top">
        <div className="menu-summary"><div><span>REGISTERED MENU</span><strong>{menus.length}</strong></div><div><span>ON SALE</span><strong>{menus.filter((menu) => menu.is_available).length}</strong></div><p><code>config/menu_catalog.json</code> · 조회 전용</p></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>ID</th><th>메뉴</th><th>카테고리</th><th>온도</th><th>가격</th><th>판매</th></tr></thead>
            <tbody>{menus.map((menu) => <tr key={menu.menu_id} onClick={() => setSelectedMenu(menu)}>
              <td className="mono-cell">{menu.menu_id}</td>
              <td><strong>{menu.name}</strong><span className="sub-cell">{menu.eng_name}</span></td>
              <td>{menu.category}</td>
              <td>{menu.available_temperatures.join(' / ')}</td>
              <td>{formatWon(menu.price)}</td>
              <td><span className={`availability ${menu.is_available ? 'on' : 'off'}`}><i />{menu.is_available ? '판매 중' : '판매 중지'}</span></td>
            </tr>)}</tbody>
          </table>
        </div>
      </section>}

      {page === 'customers' && <section className="content-section flush-top">
        <div className="customer-note"><strong>주문 이력 기반 고객 화면</strong><span>현재 POS에는 Firestore `users/{'{uid}'}` 관리자 조회 계약이 없어 얼굴등록/단골 프로필은 임의로 표시하지 않습니다.</span></div>
        <div className="customer-summary"><div><span>ORDER CUSTOMERS</span><strong>{customers.length}</strong></div><div><span>APP CUSTOMERS</span><strong>{customers.filter((customer) => customer.appOrderCount > 0).length}</strong></div><div><span>REPEAT CUSTOMERS</span><strong>{customers.filter((customer) => customer.orderCount > 1).length}</strong></div></div>
        <div className="table-wrap">
          <table className="data-table customers-table">
            <thead><tr><th>고객</th><th>최근 방문</th><th>최근 주문</th><th>주문 수</th><th>APP 주문</th><th>누적 주문금액</th></tr></thead>
            <tbody>{customers.map((customer) => <tr key={customer.customer_id} onClick={() => setSelectedCustomer(customer)}>
              <td><strong>{customer.name || '이름 미등록'}</strong><span className="sub-cell uid-cell">{customer.customer_id}</span></td>
              <td>{formatTime(customer.lastOrderAt)}</td>
              <td>{customer.latestOrder.items.map((item) => `${item.menu_name} ×${item.quantity}`).join(', ')}</td>
              <td>{customer.orderCount}</td>
              <td>{customer.appOrderCount}</td>
              <td>{formatWon(customer.totalSpend)}</td>
            </tr>)}
            {customers.length === 0 && <tr><td colSpan={6} className="table-empty">고객 식별자가 포함된 주문이 없습니다.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>}
    </main>

    {selectedOrder && <OrderDrawer order={selectedOrder} onClose={() => setSelectedOrder(null)} onStatus={updateStatus} busy={busyOrder === selectedOrder.order_id} />}
    {selectedMenu && <MenuDrawer menu={selectedMenu} onClose={() => setSelectedMenu(null)} />}
    {selectedCustomer && <CustomerDrawer customer={selectedCustomer} onClose={() => setSelectedCustomer(null)} />}
  </div>;
}
