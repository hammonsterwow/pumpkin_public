export type Temperature = 'ICE' | 'HOT';

export type MenuItem = {
  id: number;
  name: string;
  engName: string;
  price: number;
  category: string;
  image: string;
  description: string;
  isIcedOnly?: boolean;
};

export type CartItem = {
  menu: MenuItem;
  temperature: Temperature;
  quantity: number;
};

export type OrderStatus = '접수' | '제조중' | '픽업가능' | '완료' | '취소';

export type Order = {
  id: string;
  orderId: string;
  requestId: string;
  items: CartItem[];
  status: OrderStatus;
  apiStatus: 'RECEIVED' | 'PREPARING' | 'READY' | 'PICKED_UP' | 'CANCELLED';
  totalPrice: number;
  createdAt: string;
};

export type Screen = 'home' | 'menu' | 'detail' | 'cart' | 'orders' | 'admin' | 'profile';
