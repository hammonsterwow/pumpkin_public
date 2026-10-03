import { useEffect, useMemo, useState } from 'react';
import { Database, Pencil, Plus, RefreshCw, Save, Trash2, UserRound } from 'lucide-react';
import {
  createCustomer,
  deleteCustomer,
  listCustomers,
  updateCustomer,
  type Customer,
  type CustomerInput,
  type CustomerTemperature,
} from './api/customersApi';
import FaceEnrollment from './FaceEnrollment';
import './customerManagement.css';

const MENU_OPTIONS = [
  '아메리카노',
  '카페라떼',
  '바닐라라떼',
  '레몬에이드',
  '딸기스무디',
] as const;

const EMPTY_FORM: CustomerInput = {
  customer_id: '',
  name: '',
  preferred_menu: '',
  preferred_temperature: 'NONE',
  preferred_quantity: 1,
  visit_count: 0,
  face_registered: false,
};

function temperatureLabel(value: CustomerTemperature): string {
  if (value === 'ICE') return '아이스';
  if (value === 'HOT') return '핫';
  return '미지정';
}

export default function CustomerManagement() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<CustomerInput>(EMPTY_FORM);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const selected = useMemo(
    () => customers.find((customer) => customer.customer_id === selectedId) ?? null,
    [customers, selectedId],
  );

  async function refreshCustomers(preferredId?: string) {
    setLoading(true);
    try {
      const next = await listCustomers();
      setCustomers(next);
      const nextId = preferredId ?? selectedId;
      if (nextId && next.some((customer) => customer.customer_id === nextId)) {
        setSelectedId(nextId);
      } else {
        setSelectedId(next[0]?.customer_id ?? null);
      }
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '고객 목록을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshCustomers();
  }, []);

  function beginCreate() {
    setEditing(true);
    setSelectedId(null);
    setForm(EMPTY_FORM);
    setMessage('');
    setError('');
  }

  function beginEdit(customer: Customer) {
    setEditing(true);
    setSelectedId(customer.customer_id);
    setForm({
      customer_id: customer.customer_id,
      name: customer.name,
      preferred_menu: customer.preferred_menu,
      preferred_temperature: customer.preferred_temperature,
      preferred_quantity: customer.preferred_quantity,
      visit_count: customer.visit_count,
      face_registered: customer.face_registered,
    });
    setMessage('');
    setError('');
  }

  async function saveCustomer() {
    if (!form.name.trim()) {
      setError('고객 이름을 입력해주세요.');
      return;
    }

    setSaving(true);
    setMessage('');
    setError('');
    try {
      const saved = selectedId
        ? await updateCustomer(selectedId, {
            name: form.name.trim(),
            preferred_menu: form.preferred_menu.trim(),
            preferred_temperature: form.preferred_temperature,
            preferred_quantity: Number(form.preferred_quantity) || 1,
            visit_count: Number(form.visit_count) || 0,
            face_registered: form.face_registered,
          })
        : await createCustomer({
            ...form,
            customer_id: form.customer_id?.trim() || undefined,
            name: form.name.trim(),
            preferred_menu: form.preferred_menu.trim(),
            preferred_quantity: Number(form.preferred_quantity) || 1,
            visit_count: Number(form.visit_count) || 0,
          });

      setEditing(false);
      setMessage(selectedId ? '고객 정보를 수정했습니다.' : '고객을 등록했습니다.');
      await refreshCustomers(saved.customer_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '고객 저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  }

  async function removeCustomer(customer: Customer) {
    if (!window.confirm(`${customer.name} 고객 정보를 삭제할까요?`)) return;
    try {
      await deleteCustomer(customer.customer_id);
      setMessage('고객 정보를 삭제했습니다.');
      setError('');
      setEditing(false);
      await refreshCustomers();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '고객 삭제에 실패했습니다.');
    }
  }

  return (
    <section className="customer-layout">
      <article className="admin-panel customer-list-panel">
        <div className="admin-panel-title customer-title-row">
          <Database size={19} />
          <div><h2>고객 목록</h2><p>공통 백엔드에 저장된 고객 정보입니다.</p></div>
          <button className="customer-icon-button" onClick={() => void refreshCustomers()} disabled={loading} title="새로고침">
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
          </button>
        </div>
        <button className="customer-primary-button" onClick={beginCreate}><Plus size={16} />새 고객 등록</button>
        <div className="customer-list">
          {loading && <div className="admin-empty">고객 목록을 불러오는 중입니다.</div>}
          {!loading && customers.length === 0 && <div className="admin-empty">등록된 고객이 없습니다.</div>}
          {customers.map((customer) => (
            <button
              key={customer.customer_id}
              className={`customer-list-item ${selectedId === customer.customer_id && !editing ? 'active' : ''}`}
              onClick={() => { setSelectedId(customer.customer_id); setEditing(false); setMessage(''); setError(''); }}
            >
              <UserRound size={18} />
              <span><strong>{customer.name}</strong><small>{customer.customer_id}</small></span>
              <em>{customer.face_registered ? '사진 5장 완료' : '얼굴 미등록'}</em>
            </button>
          ))}
        </div>
      </article>

      <article className="admin-panel customer-detail-panel">
        {message && <div className="customer-message success">{message}</div>}
        {error && <div className="customer-message error">{error}</div>}

        {editing ? (
          <>
            <div className="admin-panel-title"><Pencil size={19} /><div><h2>{selectedId ? '고객 정보 수정' : '새 고객 등록'}</h2><p>고객 저장 후 다각도 얼굴 사진을 등록할 수 있습니다.</p></div></div>
            <div className="customer-form-grid">
              <label>고객 ID<input value={form.customer_id || ''} disabled={Boolean(selectedId)} onChange={(event) => setForm({ ...form, customer_id: event.target.value })} placeholder="비워두면 자동 생성" /></label>
              <label>이름<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="고객 이름" /></label>
              <label>선호 메뉴<select value={form.preferred_menu} onChange={(event) => setForm({ ...form, preferred_menu: event.target.value })}><option value="">미지정</option>{MENU_OPTIONS.map((menu) => <option key={menu} value={menu}>{menu}</option>)}</select></label>
              <label>선호 온도<select value={form.preferred_temperature} onChange={(event) => setForm({ ...form, preferred_temperature: event.target.value as CustomerTemperature })}><option value="NONE">미지정</option><option value="ICE">아이스</option><option value="HOT">핫</option></select></label>
              <label>선호 수량<input type="number" min="1" max="20" value={form.preferred_quantity} onChange={(event) => setForm({ ...form, preferred_quantity: Number(event.target.value) })} /></label>
              <label>방문 횟수<input type="number" min="0" value={form.visit_count} onChange={(event) => setForm({ ...form, visit_count: Number(event.target.value) })} /></label>
            </div>
            <div className="customer-form-actions">
              <button className="customer-secondary-button" onClick={() => setEditing(false)}>취소</button>
              <button className="customer-primary-button" onClick={() => void saveCustomer()} disabled={saving}><Save size={16} />{saving ? '저장 중...' : '저장'}</button>
            </div>
          </>
        ) : selected ? (
          <>
            <div className="admin-panel-title"><UserRound size={19} /><div><h2>{selected.name}</h2><p>{selected.customer_id}</p></div></div>
            <dl className="admin-detail-list customer-detail-list">
              <div><dt>선호 메뉴</dt><dd>{selected.preferred_menu || '-'}</dd></div>
              <div><dt>선호 온도</dt><dd>{temperatureLabel(selected.preferred_temperature)}</dd></div>
              <div><dt>선호 수량</dt><dd>{selected.preferred_quantity}잔</dd></div>
              <div><dt>방문 횟수</dt><dd>{selected.visit_count}회</dd></div>
              <div><dt>얼굴 등록 사진</dt><dd>{selected.face_registered ? '5장 등록 완료' : '미완료'}</dd></div>
              <div><dt>얼굴 임베딩</dt><dd>모델 연결 후 생성</dd></div>
              <div><dt>최근 수정</dt><dd>{new Date(selected.updated_at).toLocaleString('ko-KR')}</dd></div>
            </dl>
            <div className="customer-form-actions">
              <button className="customer-secondary-button" onClick={() => beginEdit(selected)}><Pencil size={16} />수정</button>
              <button className="customer-danger-button" onClick={() => void removeCustomer(selected)}><Trash2 size={16} />삭제</button>
            </div>
            <FaceEnrollment
              customerId={selected.customer_id}
              onEnrollmentChanged={() => void refreshCustomers(selected.customer_id)}
            />
          </>
        ) : (
          <div className="admin-coming-soon"><UserRound size={40} /><strong>고객을 선택하거나 새로 등록하세요.</strong><p>고객 저장 후 정면·좌·우·위·아래 얼굴 사진 5장을 등록할 수 있습니다.</p></div>
        )}
      </article>
    </section>
  );
}
