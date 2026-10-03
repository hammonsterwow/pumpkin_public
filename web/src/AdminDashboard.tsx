import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Bot,
  Camera,
  CircleAlert,
  Cpu,
  FileClock,
  Gauge,
  LayoutDashboard,
  MessageSquareText,
  RefreshCw,
  Settings,
  Users,
} from 'lucide-react';
import { getAdminSnapshot, type AdminSnapshot } from './api/adminApi';
import CustomerManagement from './CustomerManagement';
import './admin.css';

const POLL_INTERVAL_MS = 1500;

type AdminTab = 'dashboard' | 'face' | 'customers' | 'conversation' | 'events' | 'system';

type EventItem = {
  id: string;
  timestamp: number;
  category: string;
  message: string;
};

const tabs: Array<{ id: AdminTab; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'dashboard', label: '대시보드', icon: LayoutDashboard },
  { id: 'face', label: '얼굴 인식', icon: Camera },
  { id: 'customers', label: '고객 관리', icon: Users },
  { id: 'conversation', label: '대화 모니터', icon: MessageSquareText },
  { id: 'events', label: '이벤트 로그', icon: FileClock },
  { id: 'system', label: '시스템 상태', icon: Settings },
];

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

function StatusDot({ online }: { online: boolean }) {
  return <span className={`admin-status-dot ${online ? 'online' : 'offline'}`} />;
}

function formatClock(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function buildEventMessages(previous: AdminSnapshot | null, next: AdminSnapshot): EventItem[] {
  const items: EventItem[] = [];
  const now = next.updated_at || Date.now() / 1000;
  const add = (category: string, message: string) => {
    items.push({ id: `${now}-${category}-${message}`, timestamp: now, category, message });
  };

  if (!previous) {
    add('SYSTEM', `관리자 웹 연결 · ROS 노드 ${next.system.nodes.length}/${next.system.expected_nodes.length}`);
    return items;
  }

  for (const node of next.system.expected_nodes) {
    const wasOnline = previous.system.nodes.includes(node);
    const isOnline = next.system.nodes.includes(node);
    if (wasOnline !== isOnline) add('NODE', `${node} ${isOnline ? '연결됨' : '연결 끊김'}`);
  }

  if (previous.fsm_state !== next.fsm_state) add('FSM', `${previous.fsm_state || 'UNKNOWN'} → ${next.fsm_state || 'UNKNOWN'}`);
  if (previous.pipeline.text !== next.pipeline.text && next.pipeline.text) add('STT', next.pipeline.text);
  if (previous.pipeline.response_text !== next.pipeline.response_text && next.pipeline.response_text) add('TTS', next.pipeline.response_text);
  if (previous.face.detected !== next.face.detected) add('FACE', next.face.detected ? '얼굴 감지됨' : '얼굴 감지 해제');
  if (previous.face.customer_id !== next.face.customer_id && next.face.customer_id) {
    add('FACE', `고객 식별: ${next.face.customer_id} · 유사도 ${formatValue(next.face.similarity)}`);
  }

  return items;
}

export default function AdminDashboard() {
  const [tab, setTab] = useState<AdminTab>('dashboard');
  const [snapshot, setSnapshot] = useState<AdminSnapshot | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const snapshotRef = useRef<AdminSnapshot | null>(null);

  async function refresh() {
    try {
      const next = await getAdminSnapshot();
      const newEvents = buildEventMessages(snapshotRef.current, next);
      if (newEvents.length > 0) setEvents((current) => [...newEvents, ...current].slice(0, 100));
      snapshotRef.current = next;
      setSnapshot(next);
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '관리자 상태를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, []);

  const action = snapshot?.pipeline.action ?? null;
  const expression = useMemo(() => {
    if (!action) return '-';
    return formatValue(action.expression ?? action.face ?? action.emotion);
  }, [action]);
  const gesture = useMemo(() => {
    if (!action) return '-';
    return formatValue(action.gesture ?? action.motion);
  }, [action]);

  const connectedNodes = snapshot?.system.nodes.length ?? 0;
  const totalNodes = snapshot?.system.expected_nodes.length ?? 0;
  const faceStatus = snapshot?.face.matched
    ? '등록 고객 식별'
    : snapshot?.face.detected
      ? '얼굴 감지'
      : '대기 중';

  const renderNodePanel = () => (
    <article className="admin-panel admin-panel-wide">
      <div className="admin-panel-title"><Cpu size={19} /><div><h2>노드 연결 상태</h2><p>필수 ROS 노드의 실행 여부를 확인합니다.</p></div></div>
      <div className="admin-node-grid">
        {(snapshot?.system.expected_nodes ?? []).map((node) => {
          const online = snapshot?.system.nodes.includes(node) ?? false;
          return <div className="admin-node" key={node}><StatusDot online={online} /><span>{node}</span><strong>{online ? '연결됨' : '연결 안 됨'}</strong></div>;
        })}
        {!snapshot && <div className="admin-empty">노드 상태를 확인하고 있습니다.</div>}
      </div>
    </article>
  );

  const renderFacePanel = (wide = false) => (
    <article className={`admin-panel ${wide ? 'admin-panel-wide' : ''}`}>
      <div className="admin-panel-title"><Camera size={19} /><div><h2>얼굴 인식 상세</h2><p>최근 감지 및 식별 결과</p></div></div>
      <div className="admin-face-layout">
        <div className="admin-camera-placeholder">
          <Camera size={42} />
          <strong>{snapshot?.face.detected ? '얼굴 감지 중' : '카메라 영상 준비 중'}</strong>
          <span>실시간 영상 스트림은 얼굴 인식 노드 연결 후 표시됩니다.</span>
        </div>
        <dl className="admin-detail-list">
          <div><dt>얼굴 감지</dt><dd>{snapshot?.face.detected ? '예' : '아니오'}</dd></div>
          <div><dt>등록 고객 일치</dt><dd>{snapshot?.face.matched ? '예' : '아니오'}</dd></div>
          <div><dt>고객 ID</dt><dd>{formatValue(snapshot?.face.customer_id)}</dd></div>
          <div><dt>유사도</dt><dd>{formatValue(snapshot?.face.similarity)}</dd></div>
          <div><dt>품질 점수</dt><dd>{formatValue(snapshot?.face.quality)}</dd></div>
          <div><dt>모델</dt><dd>{formatValue(snapshot?.face.model)}</dd></div>
          <div><dt>처리 시간</dt><dd>{snapshot?.face.latency_ms == null ? '-' : `${snapshot.face.latency_ms} ms`}</dd></div>
          <div><dt>상태 설명</dt><dd>{formatValue(snapshot?.face.reason)}</dd></div>
        </dl>
      </div>
    </article>
  );

  const renderConversationPanel = (wide = false) => (
    <article className={`admin-panel ${wide ? 'admin-panel-wide' : ''}`}>
      <div className="admin-panel-title"><MessageSquareText size={19} /><div><h2>대화 흐름</h2><p>STT부터 로봇 출력까지 단계별로 확인합니다.</p></div></div>
      <div className="admin-flow">
        <div><span>STT</span><p>{snapshot?.pipeline.text || '입력 대기 중'}</p></div>
        <div><span>NLU</span><pre>{snapshot?.pipeline.analysis ? JSON.stringify(snapshot.pipeline.analysis, null, 2) : '분석 결과 없음'}</pre></div>
        <div><span>FSM</span><p>{snapshot?.fsm_state || 'UNKNOWN'}</p></div>
        <div><span>TTS</span><p>{snapshot?.pipeline.response_text || '출력 대기 중'}</p></div>
        <div><span>표정</span><p>{expression}</p></div>
        <div><span>제스처</span><p>{gesture}</p></div>
      </div>
    </article>
  );

  const renderEventPanel = (wide = false) => (
    <article className={`admin-panel ${wide ? 'admin-panel-wide' : ''}`}>
      <div className="admin-panel-title"><FileClock size={19} /><div><h2>이벤트 로그</h2><p>관리자 웹을 연 뒤 발생한 상태 변화를 기록합니다.</p></div></div>
      <div className="admin-event-list">
        {events.length === 0 && <div className="admin-empty">아직 기록된 상태 변화가 없습니다.</div>}
        {events.map((event) => (
          <div className="admin-event" key={event.id}>
            <time>{formatClock(event.timestamp)}</time>
            <strong>{event.category}</strong>
            <span>{event.message}</span>
          </div>
        ))}
      </div>
    </article>
  );

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-brand"><Bot size={26} /><div><strong>카페 로봇</strong><span>관리자 웹</span></div></div>
        <nav>
          {tabs.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}><Icon size={18} />{item.label}</button>;
          })}
        </nav>
        <a className="admin-pos-link" href="/">주문 관리로 이동</a>
      </aside>

      <main className="admin-page">
        <header className="admin-header">
          <div>
            <p className="admin-eyebrow">카페 로봇</p>
            <h1>{tabs.find((item) => item.id === tab)?.label ?? '관리자 웹'}</h1>
            <p>ROS 노드, 대화 흐름, 얼굴 인식 결과를 한 화면에서 확인합니다.</p>
          </div>
          <div className="admin-header-actions">
            <button onClick={() => void refresh()} disabled={loading}>
              <RefreshCw className={loading ? 'spin' : ''} size={17} /> 새로고침
            </button>
          </div>
        </header>

        {error && <div className="admin-error"><CircleAlert size={18} />{error}</div>}

        {tab === 'dashboard' && (
          <>
            <section className="admin-summary-grid">
              <article className="admin-summary-card"><Activity /><div><span>전체 시스템</span><strong>{snapshot?.system.running ? '정상 실행' : '확인 필요'}</strong></div></article>
              <article className="admin-summary-card"><Cpu /><div><span>연결 노드</span><strong>{snapshot ? `${connectedNodes}/${totalNodes}` : '-'}</strong></div></article>
              <article className="admin-summary-card"><Bot /><div><span>현재 FSM</span><strong>{snapshot?.fsm_state || 'UNKNOWN'}</strong></div></article>
              <article className="admin-summary-card"><Camera /><div><span>얼굴 인식</span><strong>{faceStatus}</strong></div></article>
            </section>
            <section className="admin-grid">
              {renderNodePanel()}
              {renderFacePanel()}
              {renderConversationPanel()}
              {renderEventPanel(true)}
            </section>
          </>
        )}

        {tab === 'face' && <section className="admin-grid">{renderFacePanel(true)}<article className="admin-panel"><div className="admin-panel-title"><Gauge size={19} /><div><h2>인식 기준</h2><p>모델 연결 후 기준값을 조정합니다.</p></div></div><dl className="admin-detail-list"><div><dt>현재 임계값</dt><dd>연동 준비 중</dd></div><div><dt>다중 프레임 확인</dt><dd>연동 준비 중</dd></div><div><dt>최근 처리 속도</dt><dd>{snapshot?.face.latency_ms == null ? '-' : `${snapshot.face.latency_ms} ms`}</dd></div></dl></article>{renderEventPanel()}</section>}

        {tab === 'customers' && <CustomerManagement />}

        {tab === 'conversation' && <section className="admin-grid">{renderConversationPanel(true)}<article className="admin-panel admin-panel-wide"><div className="admin-panel-title"><Activity size={19} /><div><h2>최근 입출력 원본</h2><p>노드 간 전달값을 그대로 확인합니다.</p></div></div><pre className="admin-raw">{snapshot ? JSON.stringify(snapshot.pipeline, null, 2) : '데이터를 불러오는 중입니다.'}</pre></article></section>}

        {tab === 'events' && <section className="admin-grid">{renderEventPanel(true)}</section>}

        {tab === 'system' && (
          <section className="admin-grid">
            {renderNodePanel()}
            <article className="admin-panel admin-panel-wide"><div className="admin-panel-title"><Activity size={19} /><div><h2>전체 상태 원본</h2><p>백엔드에서 받은 관리자 스냅샷입니다.</p></div></div><pre className="admin-raw">{snapshot ? JSON.stringify(snapshot, null, 2) : '데이터를 불러오는 중입니다.'}</pre></article>
          </section>
        )}

        <footer className="admin-footer">
          마지막 갱신: {snapshot?.updated_at ? new Date(snapshot.updated_at * 1000).toLocaleString('ko-KR') : '-'} · 1.5초마다 자동 갱신
        </footer>
      </main>
    </div>
  );
}
