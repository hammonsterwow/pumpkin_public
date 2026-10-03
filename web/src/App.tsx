import { useEffect, useMemo, useState } from 'react';
import { BarChart3, CheckCircle2, ClipboardList, Coffee, Mic, RefreshCw, Trash2 } from 'lucide-react';
import { analyzeOrder, checkApiHealth, checkRosPipeline } from './api/orderAnalysisApi';
import { getRobotSttLatest, triggerRobotStt } from './api/robotSttApi';
import Step3Confirmation from './components/Step3Confirmation';
import type { Order, OrderAnalysisResult, OrderStatus, RosPipelineStatus, Temperature } from './types';

const STORAGE_KEY = 'pumpkin_pos_orders_v1';
const STT_TIMEOUT_MS = 20000;
const MENU_PRICES: Record<string, number> = {
  아메리카노: 3000,
  카페라떼: 4000,
  바닐라라떼: 4500,
  레몬에이드: 4500,
  딸기스무디: 5000,
};

const MENU_ALIASES: Record<string, string> = {
  카페라테: '카페라떼',
  카페라떼: '카페라떼',
  바닐라라테: '바닐라라떼',
  바닐라라떼: '바닐라라떼',
  아메리카노커피: '아메리카노',
  딸기스무디: '딸기스무디',
  레몬에이드: '레몬에이드',
};

const statusLabel: Record<OrderStatus, string> = {
  RECEIVED: '주문 접수',
  PREPARING: '제조 중',
  READY: '제조 완료',
  PICKED_UP: '수령 완료',
  CANCELLED: '주문 취소',
};

type Tab = 'input' | 'orders' | 'sales';

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function loadOrders(): Order[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Order[]) : [];
  } catch {
    return [];
  }
}

function saveOrders(orders: Order[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(orders));
  } catch (error) {
    console.error('주문 저장 실패:', error);
  }
}

function formatWon(value: number): string {
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(value);
}

function nextOrderSequence(orders: Order[]): number {
  return orders.reduce(
    (result, order) => Math.max(result, Number(order.orderNumber.replace('#', '')) || 0),
    0,
  ) + 1;
}

function createOrderId(): string {
  const browserCrypto = globalThis.crypto;

  if (browserCrypto?.randomUUID) {
    return browserCrypto.randomUUID();
  }

  if (browserCrypto?.getRandomValues) {
    const values = new Uint32Array(4);
    browserCrypto.getRandomValues(values);
    return Array.from(values, (value) => value.toString(16).padStart(8, '0')).join('-');
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function normalizeMenuName(rawMenu: string): string {
  const compact = rawMenu.trim().replace(/\s+/g, '');
  return MENU_ALIASES[compact] || compact;
}

export default function App() {
  const [tab, setTab] = useState<Tab>('input');
  const [orders, setOrders] = useState<Order[]>(loadOrders);
  const [text, setText] = useState('');
  const [analysis, setAnalysis] = useState<OrderAnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [message, setMessage] = useState('');
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [rosStatus, setRosStatus] = useState<RosPipelineStatus | null>(null);
  const [listening, setListening] = useState(false);

  useEffect(() => {
    saveOrders(orders);
  }, [orders]);

  useEffect(() => {
    let mounted = true;

    async function refreshRosStatus() {
      const status = await checkRosPipeline();
      if (mounted) setRosStatus(status);
    }

    void refreshRosStatus();
    const timer = window.setInterval(() => void refreshRosStatus(), 5000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    void checkApiHealth().then(setApiOnline);
  }, []);

  const activeOrders = orders.filter(
    (order) => !['PICKED_UP', 'CANCELLED'].includes(order.status),
  ).length;
  const completedOrders = orders.filter((order) => order.status === 'PICKED_UP');
  const totalSales = completedOrders.reduce((sum, order) => sum + order.totalPrice, 0);

  const menuSales = useMemo(() => {
    const map = new Map<string, { quantity: number; amount: number }>();
    for (const order of completedOrders) {
      const previous = map.get(order.menu) || { quantity: 0, amount: 0 };
      map.set(order.menu, {
        quantity: previous.quantity + order.quantity,
        amount: previous.amount + order.totalPrice,
      });
    }
    return [...map.entries()].sort((a, b) => b[1].quantity - a[1].quantity);
  }, [completedOrders]);

  async function handleAnalyze() {
    if (!text.trim()) {
      setMessage('주문 문장을 입력해주세요.');
      return;
    }

    setMessage('입력 문장을 실제 ROS 대화 흐름으로 전송했습니다.');
    setAnalysis(null);
    setIsAnalyzing(true);
    try {
      setAnalysis(await analyzeOrder(text));
      setApiOnline(true);
      setMessage('NLU → Decision → Action 흐름 테스트가 완료되었습니다.');
    } catch (error) {
      setApiOnline(false);
      setMessage(error instanceof Error ? error.message : 'ROS 대화 흐름 테스트에 실패했습니다.');
    } finally {
      setIsAnalyzing(false);
    }
  }

  function registerOrder() {
    try {
      if (!analysis) {
        setMessage('먼저 주문 문장을 분석해주세요.');
        return;
      }

      if (analysis.intent !== 'ORDER') {
        setMessage(`현재 POS 등록은 ORDER 의도만 지원합니다. 감지된 의도: ${analysis.intent}`);
        return;
      }

      if (analysis.order_status !== 'VALID' || analysis.needs_reprompt) {
        setMessage(`주문 상태가 ${analysis.order_status}이므로 먼저 로봇 대화를 완료해야 합니다.`);
        return;
      }

      if (analysis.items.length === 0) {
        setMessage('주문 항목을 인식하지 못했습니다. 다시 말씀해주세요.');
        return;
      }

      const invalidItem = analysis.items.find(
        (item) => !item.menu || !item.temperature || !item.quantity || item.missing_slots.length > 0,
      );
      if (invalidItem) {
        setMessage('메뉴·온도·수량이 모두 확인된 주문만 등록할 수 있습니다.');
        return;
      }

      const unsupportedItem = analysis.items.find(
        (item) => item.menu && MENU_PRICES[normalizeMenuName(item.menu)] === undefined,
      );
      if (unsupportedItem?.menu) {
        setMessage(`가격표에 없는 메뉴입니다: ${unsupportedItem.menu}`);
        return;
      }

      const now = new Date().toISOString();
      const firstSequence = nextOrderSequence(orders);
      const createdOrders: Order[] = analysis.items.map((item, index) => {
        const menu = normalizeMenuName(item.menu as string);
        const quantity = Math.max(1, Math.trunc(item.quantity as number));
        const temperature: Temperature = item.temperature ?? 'NONE';
        const unitPrice = MENU_PRICES[menu];

        return {
          id: createOrderId(),
          orderNumber: `#${String(firstSequence + index).padStart(3, '0')}`,
          originalText: analysis.text || text.trim(),
          intent: analysis.intent,
          menu,
          quantity,
          temperature,
          confidence: analysis.intent_confidence,
          confirmation_text: analysis.confirmation_text,
          model_name: analysis.model_name,
          device: analysis.device,
          unitPrice,
          totalPrice: unitPrice * quantity,
          status: 'RECEIVED',
          createdAt: now,
        };
      });

      setOrders((current) => [...createdOrders, ...current]);
      setText('');
      setAnalysis(null);
      setMessage(`${createdOrders.length}개 주문 항목이 등록되었습니다.`);
      setTab('orders');
    } catch (error) {
      console.error('주문 등록 실패:', error);
      setMessage(
        error instanceof Error
          ? `주문 등록에 실패했습니다: ${error.message}`
          : '주문 등록 중 알 수 없는 오류가 발생했습니다.',
      );
    }
  }

  function changeStatus(id: string, status: OrderStatus) {
    const completedAt = status === 'PICKED_UP' ? new Date().toISOString() : undefined;
    setOrders((current) =>
      current.map((order) => (order.id === id ? { ...order, status, completedAt } : order)),
    );
  }

  async function startSpeech() {
    if (listening) return;

    setMessage('Jetson 마이크로 녹음 중입니다. 말씀해주세요.');
    setText('');
    setAnalysis(null);
    setListening(true);

    try {
      await triggerRobotStt();
      const deadline = Date.now() + STT_TIMEOUT_MS;

      while (Date.now() < deadline) {
        await sleep(300);
        const snapshot = await getRobotSttLatest();

        if (snapshot.text) setText(snapshot.text);
        if (snapshot.error || snapshot.status.startsWith('error:')) {
          throw new Error(snapshot.error || snapshot.status);
        }
        if (snapshot.status === 'too_quiet') {
          throw new Error('마이크 입력이 너무 작습니다. 마이크와 입력 음량을 확인해주세요.');
        }
        if (snapshot.status === 'empty') {
          throw new Error('음성을 인식하지 못했습니다. 다시 말씀해주세요.');
        }
        if (snapshot.status === 'rejected') {
          throw new Error('인식 결과가 불확실합니다. 다시 말씀해주세요.');
        }
        if (snapshot.text && snapshot.analysis && snapshot.action) {
          setAnalysis({
            ...snapshot.analysis,
            confirmation_text: snapshot.response_text,
            decision: snapshot.decision,
            action: snapshot.action,
            flow_status: snapshot.status,
          });
          setApiOnline(true);
          setMessage(`음성 대화 흐름 완료: ${snapshot.text}`);
          return;
        }
      }

      throw new Error('STT, NLU 또는 로봇 행동 응답 시간이 초과되었습니다.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '음성 인식에 실패했습니다.');
    } finally {
      setListening(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><Coffee size={30} /><div><strong>Physical AI Cafe</strong><span>Manager POS</span></div></div>
        <nav>
          <button className={tab === 'input' ? 'active' : ''} onClick={() => setTab('input')}><Coffee />주문 입력</button>
          <button className={tab === 'orders' ? 'active' : ''} onClick={() => setTab('orders')}><ClipboardList />주문 현황</button>
          <button className={tab === 'sales' ? 'active' : ''} onClick={() => setTab('sales')}><BarChart3 />매출 현황</button>
        </nav>
      </aside>

      <main>
        <header className="topbar">
          <div><h1>카페 로봇 관리자 POS</h1><p>실제 ROS2 대화 흐름 모니터링 및 테스트</p></div>
          <div className="status-row">
            <span className={`api-status ${rosStatus?.running ? 'online' : 'offline'}`}>
              {rosStatus === null
                ? 'ROS2 확인 중'
                : rosStatus.running
                  ? `ROS2 전체 실행 (${rosStatus.nodes.length}/5)`
                  : `ROS2 실행 안 됨 (${rosStatus.nodes.length}/5)`}
            </span>
            <span className={`api-status ${apiOnline ? 'online' : 'offline'}`}>{apiOnline === null ? 'API 확인 중' : apiOnline ? 'ROS 연동 API 연결됨' : 'ROS 연동 API 연결 안 됨'}</span>
            <span>진행 주문 <strong>{activeOrders}</strong>건</span>
          </div>
        </header>

        {message && <div className="notice">{message}</div>}

        {tab === 'input' && (
          <section className="page-grid">
            <article className="panel">
              <div className="panel-heading"><div><span>STEP 1</span><h2>대화 흐름 테스트 입력</h2></div></div>
              <textarea value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void handleAnalyze(); } }} placeholder="예: 아이스 아메리카노 두 잔 주세요" />
              <div className="action-row">
                <button className={`secondary ${listening ? 'recording' : ''}`} disabled={listening || isAnalyzing} onClick={() => void startSpeech()}><Mic />{listening ? 'Jetson 듣는 중...' : '로봇 음성 입력'}</button>
                <button className="primary" disabled={isAnalyzing || listening || !text.trim()} onClick={() => void handleAnalyze()}>{isAnalyzing ? <RefreshCw className="spin" /> : <Coffee />}ROS 대화 흐름 테스트</button>
              </div>
              <div className="examples">
                {['아이스 아메리카노 두 잔 주세요', '따뜻한 카페라떼 한 잔 주세요', '바닐라라떼 아이스로 하나 주세요'].map((example) => <button key={example} onClick={() => setText(example)}>{example}</button>)}
              </div>
            </article>

            <article className="panel">
              <div className="panel-heading"><div><span>STEP 2</span><h2>NLU · Decision · Action 결과</h2></div></div>
              {analysis ? (
                <>
                  <pre>{JSON.stringify(analysis, null, 2)}</pre>
                  {analysis.intent_confidence < 0.6 && <p className="warning">NLU 의도 신뢰도가 낮습니다. 주문 문장을 다시 확인해주세요.</p>}
                  <div className="action-row right">
                    <button className="secondary" onClick={() => void handleAnalyze()}><RefreshCw />다시 테스트</button>
                    <button className="success" onClick={registerOrder}><CheckCircle2 />주문 등록</button>
                  </div>
                </>
              ) : <div className="empty">문장을 전송하면 실제 ROS 흐름의 JSON 결과가 여기에 표시됩니다.</div>}
            </article>

            {analysis && <Step3Confirmation text={analysis.confirmation_text} />}
          </section>
        )}

        {tab === 'orders' && (
          <section>
            <div className="section-title"><div><h2>주문 현황</h2><p>접수된 주문을 제조 및 수령 상태로 변경합니다.</p></div>{orders.length > 0 && <button className="danger" onClick={() => { if (confirm('모든 주문을 삭제할까요?')) setOrders([]); }}><Trash2 />전체 삭제</button>}</div>
            <div className="order-list">
              {orders.length === 0 && <div className="panel empty">현재 등록된 주문이 없습니다.</div>}
              {orders.map((order) => (
                <article className="order-card" key={order.id}>
                  <div className="order-card-top"><div><strong>{order.orderNumber}</strong><span className={`badge ${order.status.toLowerCase()}`}>{statusLabel[order.status]}</span></div><time>{new Date(order.createdAt).toLocaleString('ko-KR')}</time></div>
                  <h3>{order.temperature === 'ICE' ? '아이스 ' : order.temperature === 'HOT' ? '따뜻한 ' : ''}{order.menu} × {order.quantity}</h3>
                  <p>{order.originalText}</p>
                  <div className="order-meta"><span>{formatWon(order.totalPrice)}</span><span>신뢰도 {Math.round(order.confidence * 100)}%</span></div>
                  <div className="action-row">
                    {order.status === 'RECEIVED' && <button className="primary" onClick={() => changeStatus(order.id, 'PREPARING')}>제조 시작</button>}
                    {order.status === 'PREPARING' && <button className="primary" onClick={() => changeStatus(order.id, 'READY')}>제조 완료</button>}
                    {order.status === 'READY' && <button className="success" onClick={() => changeStatus(order.id, 'PICKED_UP')}>수령 완료</button>}
                    {['RECEIVED', 'PREPARING'].includes(order.status) && <button className="danger" onClick={() => changeStatus(order.id, 'CANCELLED')}>주문 취소</button>}
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {tab === 'sales' && (
          <section>
            <div className="section-title"><div><h2>매출 현황</h2><p>수령 완료 주문만 매출에 반영됩니다.</p></div></div>
            <div className="metric-grid">
              <div className="metric"><span>오늘 총매출</span><strong>{formatWon(totalSales)}</strong></div>
              <div className="metric"><span>완료 주문</span><strong>{completedOrders.length}건</strong></div>
              <div className="metric"><span>평균 주문 금액</span><strong>{formatWon(completedOrders.length ? totalSales / completedOrders.length : 0)}</strong></div>
              <div className="metric"><span>최다 판매 메뉴</span><strong>{menuSales[0]?.[0] || '-'}</strong></div>
            </div>
            <article className="panel">
              <h2>메뉴별 판매량</h2>
              {menuSales.length === 0 ? <div className="empty">수령 완료 주문이 아직 없습니다.</div> : menuSales.map(([menu, value]) => (
                <div className="sales-row" key={menu}><span>{menu}</span><div className="bar"><i style={{ width: `${Math.max(8, (value.quantity / menuSales[0][1].quantity) * 100)}%` }} /></div><strong>{value.quantity}잔 · {formatWon(value.amount)}</strong></div>
              ))}
            </article>
          </section>
        )}
      </main>
    </div>
  );
}
