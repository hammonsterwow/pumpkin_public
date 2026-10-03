export type OrderIntent = 'ORDER' | 'PAYMENT' | 'CANCEL' | 'MODIFY' | 'GUIDE' | 'AFFIRM' | 'DENY' | 'UNKNOWN';
export type Temperature = 'HOT' | 'ICE' | 'NONE';
export type NLUOrderStatus = 'NONE' | 'VALID' | 'INCOMPLETE' | 'CONFLICT' | 'OUT_OF_POLICY' | 'UNPARSABLE';
export type OrderStatus = 'RECEIVED' | 'PREPARING' | 'READY' | 'PICKED_UP' | 'CANCELLED';

export interface NLUItemConfidence {
  active: number;
  menu: number;
  temperature: number;
  quantity: number;
}

export interface NLUOrderItem {
  item_id: number;
  menu: string | null;
  temperature: 'HOT' | 'ICE' | null;
  quantity: number | null;
  confidence: NLUItemConfidence;
  missing_slots: string[];
}

export interface OrderAnalysisResult {
  schema_version?: string;
  model_name?: string;
  text?: string;
  intent: OrderIntent;
  intent_confidence: number;
  confidence?: number;
  order_status: NLUOrderStatus;
  order_status_confidence: number;
  items: NLUOrderItem[];
  needs_reprompt: boolean;
  device?: string;
  latency_ms?: number;
  confirmation_text?: string;
  decision?: Record<string, unknown> | null;
  action?: Record<string, unknown> | null;
  flow_status?: string;
}

export interface RobotSttSnapshot {
  request_id?: number;
  status: string;
  text: string;
  analysis: OrderAnalysisResult | null;
  decision?: Record<string, unknown> | null;
  response_text?: string;
  action?: Record<string, unknown> | null;
  error?: string | null;
  updated_at?: number;
}

export interface Order {
  id: string;
  orderNumber: string;
  originalText: string;
  intent: OrderIntent;
  menu: string;
  quantity: number;
  temperature: Temperature;
  confidence: number;
  confirmation_text?: string;
  model_name?: string;
  device?: string;
  unitPrice: number;
  totalPrice: number;
  status: OrderStatus;
  createdAt: string;
  completedAt?: string;
}

export interface RosPipelineStatus {
  running: boolean;
  nodes: string[];
  state?: string;
  stt_connected?: boolean;
  nlu_connected?: boolean;
  detail?: string;
}
