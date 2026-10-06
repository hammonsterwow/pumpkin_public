import { CartItem } from '../native/types';

export type OrderSource = 'APP' | 'ROBOT' | 'POS';
export type ApiOrderStatus =
  | 'RECEIVED'
  | 'PREPARING'
  | 'READY'
  | 'PICKED_UP'
  | 'CANCELLED';

export type CreateOrderRequest = {
  schema_version: '1.0';
  request_id: string;
  source: OrderSource;
  customer_id: string | null;
  items: Array<{
    menu_id: number;
    menu_name: string;
    temperature: 'ICE' | 'HOT' | 'NONE';
    size: 'SMALL' | 'MEDIUM' | 'LARGE' | 'NONE';
    quantity: number;
    options: string[];
    unit_price: number;
  }>;
  original_text: string | null;
  metadata: Record<string, unknown>;
};

export type OrderResponse = {
  order_id: string;
  order_number: string;
  request_id: string;
  source: OrderSource;
  customer_id: string | null;
  status: ApiOrderStatus;
  items: Array<CreateOrderRequest['items'][number] & { id: string }>;
  original_text: string | null;
  metadata: Record<string, unknown>;
  total_price: number;
  created_at: string;
  updated_at: string;
};

const API_BASE_URL = (
  process.env.EXPO_PUBLIC_ORDER_API_BASE_URL
  || process.env.EXPO_PUBLIC_API_BASE_URL
)?.replace(/\/$/, '');

function createRequestId(): string {
  const random = Math.random().toString(36).slice(2);
  return `app-${Date.now()}-${random}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error('EXPO_PUBLIC_API_BASE_URL이 설정되지 않았습니다.');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`주문 API 오류 ${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

export async function createOrder(payload: CreateOrderRequest): Promise<OrderResponse> {
  return request<OrderResponse>('/api/v1/orders', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': payload.request_id,
    },
    body: JSON.stringify(payload),
  });
}

export async function submitAppOrder(
  cart: CartItem[],
  customerId: string | null = null,
): Promise<OrderResponse> {
  const requestId = createRequestId();
  return createOrder({
    schema_version: '1.0',
    request_id: requestId,
    source: 'APP',
    customer_id: customerId,
    items: cart.map((item) => ({
      menu_id: item.menu.id,
      menu_name: item.menu.name,
      temperature: item.temperature,
      size: 'NONE',
      quantity: item.quantity,
      options: [],
      unit_price: item.menu.price,
    })),
    original_text: null,
    metadata: {},
  });
}

export async function listOrders(): Promise<OrderResponse[]> {
  return request<OrderResponse[]>('/api/v1/orders');
}

export async function getPublicOrderStatus(
  orderId: string,
  requestId: string,
): Promise<OrderResponse> {
  const query = new URLSearchParams({ request_id: requestId }).toString();
  return request<OrderResponse>(
    `/api/v1/public/orders/${encodeURIComponent(orderId)}?${query}`,
  );
}

export async function updateOrderStatus(
  orderId: string,
  status: ApiOrderStatus,
): Promise<OrderResponse> {
  return request<OrderResponse>(`/api/v1/orders/${orderId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
}
