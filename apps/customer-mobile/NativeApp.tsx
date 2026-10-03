import React, { useMemo, useState } from 'react';
import {
  Alert,
  Image,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { MENU_DATA } from './src/native/menuData';
import { CartItem, MenuItem, Order, OrderStatus, Screen, Temperature } from './src/native/types';

const C = {
  bg: '#F4F4F5',
  white: '#FFFFFF',
  text: '#18181B',
  muted: '#71717A',
  icon: '#A1A1AA',
  line: '#E5E7EB',
  input: '#F4F4F5',
  yellow: '#E09D00',
  yellowDark: '#D69500',
  green: '#1E3826',
  green2: '#2D5036',
  red: '#EF4444',
};

const ORDER_STATUSES: OrderStatus[] = ['접수', '제조중', '완료'];
const CATEGORIES = ['전체', 'Espresso', 'Frappuccino', 'Teavana', 'Beverage'];
const won = (value: number) => `${value.toLocaleString('ko-KR')}원`;

const cardShadow = {
  shadowColor: '#000',
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.08,
  shadowRadius: 7,
  elevation: 2,
};

export default function NativeApp() {
  const [screen, setScreen] = useState<Screen>('home');
  const [selectedMenu, setSelectedMenu] = useState<MenuItem | null>(null);
  const [temperature, setTemperature] = useState<Temperature>('ICE');
  const [quantity, setQuantity] = useState(1);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);

  const cartTotal = useMemo(
    () => cart.reduce((sum, item) => sum + item.menu.price * item.quantity, 0),
    [cart],
  );

  const openDetail = (menu: MenuItem) => {
    setSelectedMenu(menu);
    setTemperature('ICE');
    setQuantity(1);
    setScreen('detail');
  };

  const addToCart = () => {
    if (!selectedMenu) return;
    setCart((prev) => [...prev, { menu: selectedMenu, temperature, quantity }]);
    Alert.alert('장바구니 추가', `${selectedMenu.name} ${quantity}잔을 담았습니다.`);
    setScreen('cart');
  };

  const placeOrder = () => {
    if (cart.length === 0) {
      Alert.alert('주문 불가', '장바구니에 메뉴를 먼저 담아주세요.');
      return;
    }

    const order: Order = {
      id: `ORD-${Date.now().toString().slice(-6)}`,
      items: cart,
      status: '접수',
      totalPrice: cartTotal,
      createdAt: new Date().toLocaleString('ko-KR'),
    };

    setOrders((prev) => [order, ...prev]);
    setCart([]);
    Alert.alert('주문 완료', '주문 정보가 접수되었습니다.');
    setScreen('orders');
  };

  const updateOrderStatus = (orderId: string) => {
    setOrders((prev) =>
      prev.map((order) => {
        if (order.id !== orderId) return order;
        const currentIndex = ORDER_STATUSES.indexOf(order.status);
        return { ...order, status: ORDER_STATUSES[(currentIndex + 1) % ORDER_STATUSES.length] };
      }),
    );
  };

  const renderScreen = () => {
    if (screen === 'home') return <HomeScreen go={setScreen} openDetail={openDetail} />;
    if (screen === 'menu') return <OrderScreen openDetail={openDetail} />;
    if (screen === 'detail' && selectedMenu) {
      return (
        <DetailScreen
          menu={selectedMenu}
          temperature={temperature}
          quantity={quantity}
          setTemperature={setTemperature}
          setQuantity={setQuantity}
          addToCart={addToCart}
        />
      );
    }
    if (screen === 'cart') return <CartScreen cart={cart} setCart={setCart} total={cartTotal} placeOrder={placeOrder} />;
    if (screen === 'orders') return <OrdersScreen orders={orders} goAdmin={() => setScreen('admin')} />;
    if (screen === 'admin') return <AdminScreen orders={orders} updateStatus={updateOrderStatus} />;
    if (screen === 'profile') return <ProfileScreen goAdmin={() => setScreen('admin')} />;
    return <HomeScreen go={setScreen} openDetail={openDetail} />;
  };

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <View style={styles.appRoot}>
        <View style={styles.content}>{renderScreen()}</View>
        <BottomNav screen={screen} setScreen={setScreen} cartCount={cart.length} />
      </View>
    </SafeAreaView>
  );
}

function HomeScreen({ go, openDetail }: { go: (screen: Screen) => void; openDetail: (menu: MenuItem) => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.homePad} showsVerticalScrollIndicator={false}>
      <View style={styles.homeHeader}>
        <View>
          <Text style={styles.hello}>안녕하세요, <Text style={styles.yellowText}>단호박 </Text>님</Text>
          <View style={styles.locationRow}>
            <Text style={styles.pin}>⌖</Text>
            <Text style={styles.location}>이화여대 점</Text>
            <Text style={styles.arrow}>›</Text>
          </View>
        </View>
        <View style={styles.bellWrap}>
          <Text style={styles.bell}>♧</Text>
          <View style={styles.dot} />
        </View>
      </View>

      <Pressable style={styles.quickCard} onPress={() => go('menu')}>
        <View style={styles.quickBlur1} />
        <View style={styles.quickBlur2} />
        <Text style={styles.quickTitle}>다이렉트 오더로{`\n`}빠르게 주문하세요</Text>
        <Text style={styles.quickSub}>줄 서지 않고 미리 주문하고 픽업!</Text>
        <View style={styles.quickBtn}><Text style={styles.quickBtnText}>주문하기</Text></View>
      </Pressable>

      <Pressable style={styles.faceCard} onPress={() => go('profile')}>
        <View style={styles.faceBlur1} />
        <View style={styles.faceTop}>
          <View style={{ flex: 1 }}>
            <View style={styles.newBadge}><Text style={styles.newText}>NEW</Text></View>
            <Text style={styles.faceTitle}>단골 맞춤 서비스 등록</Text>
            <Text style={styles.faceBody}>페이스 이미지를 등록하고{`\n`}매장에서 얼굴 인식으로 특별한 서비스를 경험하세요!</Text>
          </View>
          <View style={styles.scanCircle}><Text style={styles.scanText}>⌗</Text></View>
        </View>
        <View style={styles.faceBtn}><Text style={styles.faceBtnText}>⌗  지금 얼굴 등록하기</Text></View>
      </Pressable>

      <View style={styles.sectionRow}>
        <Text style={styles.sectionTitle}>추천 메뉴</Text>
        <Pressable onPress={() => go('menu')}><Text style={styles.viewAll}>전체보기</Text></Pressable>
      </View>

      <View style={styles.recommendGrid}>
        {MENU_DATA.slice(0, 4).map((item) => (
          <Pressable key={item.id} style={styles.recommendCard} onPress={() => openDetail(item)}>
            <Image source={{ uri: item.image }} style={styles.recommendImg} />
            <View style={styles.recommendInfo}>
              <Text numberOfLines={1} style={styles.recommendName}>{item.name}</Text>
              <Text style={styles.recommendPrice}>{won(item.price)}</Text>
            </View>
          </Pressable>
        ))}
      </View>
    </ScrollView>
  );
}

function OrderScreen({ openDetail }: { openDetail: (menu: MenuItem) => void }) {
  const [category, setCategory] = useState('전체');
  const filtered = category === '전체' ? MENU_DATA : MENU_DATA.filter((item) => item.category === category);

  return (
    <View style={styles.orderRoot}>
      <View style={styles.orderTop}>
        <Text style={styles.orderTitle}>Order</Text>
        <View style={styles.searchBar}>
          <Text style={styles.searchIcon}>⌕</Text>
          <TextInput
            placeholder="메뉴명 검색"
            placeholderTextColor={C.icon}
            style={styles.searchInput}
            editable={false}
          />
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {CATEGORIES.map((item) => {
            const active = item === category;
            return (
              <Pressable key={item} style={[styles.chip, active && styles.chipActive]} onPress={() => setCategory(item)}>
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{item}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      <ScrollView style={styles.orderList} contentContainerStyle={styles.orderListContent} showsVerticalScrollIndicator={false}>
        {filtered.map((menu) => (
          <Pressable key={menu.id} style={styles.orderItemCard} onPress={() => openDetail(menu)}>
            <Image source={{ uri: menu.image }} style={styles.orderItemImage} />
            <View style={styles.orderItemInfo}>
              <Text style={styles.orderItemName}>{menu.name}</Text>
              <Text style={styles.orderItemEng}>{menu.engName}</Text>
              <Text style={styles.orderItemPrice}>{won(menu.price)}</Text>
            </View>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

function DetailScreen({
  menu,
  temperature,
  quantity,
  setTemperature,
  setQuantity,
  addToCart,
}: {
  menu: MenuItem;
  temperature: Temperature;
  quantity: number;
  setTemperature: (value: Temperature) => void;
  setQuantity: (value: number) => void;
  addToCart: () => void;
}) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.pagePad} showsVerticalScrollIndicator={false}>
      <Image source={{ uri: menu.image }} style={styles.detailImg} />
      <View style={styles.whiteCard}>
        <Text style={styles.menuCategory}>{menu.category}</Text>
        <Text style={styles.detailName}>{menu.name}</Text>
        <Text style={styles.detailEng}>{menu.engName}</Text>
        <Text style={styles.detailDesc}>{menu.description}</Text>
        <Text style={styles.detailPrice}>{won(menu.price)}</Text>
      </View>

      <View style={styles.whiteCard}>
        <Text style={styles.optionTitle}>온도 선택</Text>
        <View style={styles.optionRow}>
          <OptionButton label="ICE" active={temperature === 'ICE'} onPress={() => setTemperature('ICE')} />
          <OptionButton label="HOT" active={temperature === 'HOT'} disabled={menu.isIcedOnly} onPress={() => setTemperature('HOT')} />
        </View>
      </View>

      <View style={styles.whiteCard}>
        <Text style={styles.optionTitle}>수량</Text>
        <View style={styles.qtyRow}>
          <Pressable style={styles.qtyBtn} onPress={() => setQuantity(Math.max(1, quantity - 1))}><Text style={styles.qtyBtnText}>-</Text></Pressable>
          <Text style={styles.qty}>{quantity}</Text>
          <Pressable style={styles.qtyBtn} onPress={() => setQuantity(quantity + 1)}><Text style={styles.qtyBtnText}>+</Text></Pressable>
        </View>
      </View>

      <Pressable style={styles.mainAction} onPress={addToCart}>
        <Text style={styles.mainActionText}>장바구니 담기 · {won(menu.price * quantity)}</Text>
      </Pressable>
    </ScrollView>
  );
}

function OptionButton({ label, active, disabled, onPress }: { label: string; active: boolean; disabled?: boolean; onPress: () => void }) {
  return (
    <Pressable disabled={disabled} onPress={onPress} style={[styles.optionButton, active && styles.optionActive, disabled && styles.optionDisabled]}>
      <Text style={[styles.optionText, active && styles.optionTextActive]}>{label}</Text>
    </Pressable>
  );
}

function CartScreen({ cart, setCart, total, placeOrder }: { cart: CartItem[]; setCart: React.Dispatch<React.SetStateAction<CartItem[]>>; total: number; placeOrder: () => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.pagePad} showsVerticalScrollIndicator={false}>
      <Text style={styles.pageTitle}>장바구니</Text>
      {cart.length === 0 ? <EmptyState title="장바구니가 비어있어요" body="오더 화면에서 메뉴를 먼저 담아주세요." /> : null}
      {cart.map((item, index) => (
        <View key={`${item.menu.id}-${index}`} style={styles.cartCard}>
          <View>
            <Text style={styles.cartName}>{item.menu.name}</Text>
            <Text style={styles.cartMeta}>{item.temperature} · {item.quantity}잔</Text>
            <Text style={styles.cartPrice}>{won(item.menu.price * item.quantity)}</Text>
          </View>
          <Pressable onPress={() => setCart((prev) => prev.filter((_, i) => i !== index))} style={styles.deleteBtn}>
            <Text style={styles.deleteText}>삭제</Text>
          </Pressable>
        </View>
      ))}
      <View style={styles.totalCard}>
        <Text style={styles.totalLabel}>총 결제 예정 금액</Text>
        <Text style={styles.total}>{won(total)}</Text>
      </View>
      <Pressable disabled={cart.length === 0} style={[styles.mainAction, cart.length === 0 && { opacity: 0.4 }]} onPress={placeOrder}>
        <Text style={styles.mainActionText}>주문 접수하기</Text>
      </Pressable>
    </ScrollView>
  );
}

function OrdersScreen({ orders, goAdmin }: { orders: Order[]; goAdmin: () => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.pagePad} showsVerticalScrollIndicator={false}>
      <View style={styles.titleRow}>
        <Text style={styles.pageTitle}>주문 내역</Text>
        <Pressable style={styles.adminBtn} onPress={goAdmin}><Text style={styles.adminText}>관리</Text></Pressable>
      </View>
      {orders.length === 0 ? <EmptyState title="주문 내역이 없습니다" body="주문을 생성하면 이곳에 표시됩니다." /> : null}
      {orders.map((order) => <OrderCard key={order.id} order={order} />)}
    </ScrollView>
  );
}

function AdminScreen({ orders, updateStatus }: { orders: Order[]; updateStatus: (orderId: string) => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.pagePad} showsVerticalScrollIndicator={false}>
      <Text style={styles.pageTitle}>관리자 화면</Text>
      {orders.length === 0 ? <EmptyState title="관리할 주문이 없습니다" body="주문이 들어오면 상태 변경 버튼이 표시됩니다." /> : null}
      {orders.map((order) => (
        <View key={order.id} style={styles.adminCard}>
          <OrderCard order={order} />
          <Pressable style={styles.greenAction} onPress={() => updateStatus(order.id)}><Text style={styles.greenActionText}>다음 상태로 변경</Text></Pressable>
        </View>
      ))}
    </ScrollView>
  );
}

function ProfileScreen({ goAdmin }: { goAdmin: () => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.pagePad} showsVerticalScrollIndicator={false}>
      <View style={styles.profileCard}>
        <View style={styles.avatar}><Text style={styles.avatarText}>단</Text></View>
        <Text style={styles.profileName}>단호박 님</Text>
        <Text style={styles.profileBody}>얼굴 등록과 단골 추천 기능을 연결할 예정입니다.</Text>
      </View>
      <Pressable style={styles.greenAction} onPress={goAdmin}><Text style={styles.greenActionText}>관리자 화면 열기</Text></Pressable>
    </ScrollView>
  );
}

function OrderCard({ order }: { order: Order }) {
  return (
    <View style={styles.historyCard}>
      <View style={styles.titleRow}>
        <Text style={styles.orderId}>{order.id}</Text>
        <StatusPill status={order.status} />
      </View>
      <Text style={styles.orderDate}>{order.createdAt}</Text>
      {order.items.map((item, index) => <Text key={index} style={styles.orderLine}>{item.menu.name} · {item.temperature} · {item.quantity}잔</Text>)}
      <Text style={styles.historyPrice}>{won(order.totalPrice)}</Text>
    </View>
  );
}

function StatusPill({ status }: { status: OrderStatus }) {
  const color = status === '완료' ? '#15803D' : status === '제조중' ? C.yellowDark : C.green;
  const bg = status === '완료' ? '#ECFDF3' : status === '제조중' ? '#FFF7E0' : '#F4F4F5';
  return <View style={[styles.statusPill, { backgroundColor: bg }]}><Text style={[styles.statusText, { color }]}>{status}</Text></View>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return <View style={styles.empty}><Text style={styles.emptyIcon}>🧾</Text><Text style={styles.emptyTitle}>{title}</Text><Text style={styles.emptyBody}>{body}</Text></View>;
}

function BottomNav({ screen, setScreen, cartCount }: { screen: Screen; setScreen: (screen: Screen) => void; cartCount: number }) {
  const tabs: { key: Screen; label: string; icon: string }[] = [
    { key: 'home', label: '홈', icon: '⌂' },
    { key: 'menu', label: '오더', icon: '☕' },
    { key: 'cart', label: cartCount ? `장바구니 ${cartCount}` : '장바구니', icon: '▱' },
    { key: 'profile', label: '마이페이지', icon: '○' },
  ];
  return (
    <View style={styles.nav}>
      {tabs.map((tab) => {
        const active = screen === tab.key || (tab.key === 'menu' && screen === 'detail');
        return <Pressable key={tab.key} style={styles.navItem} onPress={() => setScreen(tab.key)}><Text style={[styles.navIcon, active && styles.navActive]}>{tab.icon}</Text><Text style={[styles.navLabel, active && styles.navActive]}>{tab.label}</Text></Pressable>;
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  appRoot: { flex: 1, backgroundColor: C.bg },
  content: { flex: 1 },
  scroll: { flex: 1, backgroundColor: C.bg },
  homePad: { paddingBottom: 112 },
  pagePad: { padding: 20, paddingBottom: 112 },

  homeHeader: { backgroundColor: C.white, paddingHorizontal: 20, paddingTop: 28, paddingBottom: 22, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  hello: { fontSize: 26, lineHeight: 34, fontWeight: '900', color: C.text, letterSpacing: -0.4 },
  yellowText: { color: C.yellow },
  locationRow: { flexDirection: 'row', alignItems: 'center', marginTop: 6 },
  pin: { color: C.yellow, fontWeight: '900', marginRight: 5 },
  location: { color: C.muted, fontSize: 14, fontWeight: '600' },
  arrow: { color: C.muted, fontSize: 20, marginLeft: 6, marginTop: -2 },
  bellWrap: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center' },
  bell: { fontSize: 28, color: C.text },
  dot: { position: 'absolute', top: 8, right: 8, width: 9, height: 9, borderRadius: 5, backgroundColor: C.red, borderWidth: 1, borderColor: C.white },

  quickCard: { marginHorizontal: 20, marginTop: 20, backgroundColor: C.yellow, borderRadius: 22, padding: 26, minHeight: 178, overflow: 'hidden', justifyContent: 'center', ...cardShadow },
  quickBlur1: { position: 'absolute', right: -30, bottom: -26, width: 140, height: 140, borderRadius: 70, backgroundColor: 'rgba(255,255,255,0.12)' },
  quickBlur2: { position: 'absolute', right: -18, top: 55, width: 110, height: 110, borderRadius: 55, backgroundColor: 'rgba(0,0,0,0.08)' },
  quickTitle: { color: C.white, fontSize: 28, lineHeight: 36, fontWeight: '900', letterSpacing: -0.4 },
  quickSub: { color: 'rgba(255,255,255,0.84)', fontSize: 15, marginTop: 10, fontWeight: '700' },
  quickBtn: { alignSelf: 'flex-start', backgroundColor: C.green, paddingHorizontal: 19, paddingVertical: 11, borderRadius: 24, marginTop: 22 },
  quickBtnText: { color: C.white, fontWeight: '900', fontSize: 14 },

  faceCard: { marginHorizontal: 20, marginTop: 18, backgroundColor: C.green, borderRadius: 22, padding: 22, minHeight: 205, overflow: 'hidden', ...cardShadow },
  faceBlur1: { position: 'absolute', right: -40, bottom: -40, width: 150, height: 150, borderRadius: 75, backgroundColor: 'rgba(224,157,0,0.18)' },
  faceTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  newBadge: { alignSelf: 'flex-start', backgroundColor: 'rgba(224,157,0,0.2)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, marginBottom: 12 },
  newText: { color: C.yellow, fontWeight: '900', fontSize: 12 },
  faceTitle: { color: C.white, fontSize: 21, fontWeight: '900', marginBottom: 8 },
  faceBody: { color: '#D4D4D8', fontSize: 14, lineHeight: 22, fontWeight: '500' },
  scanCircle: { width: 58, height: 58, borderRadius: 29, backgroundColor: 'rgba(255,255,255,0.12)', alignItems: 'center', justifyContent: 'center' },
  scanText: { color: C.yellow, fontSize: 28, fontWeight: '900' },
  faceBtn: { alignSelf: 'flex-start', backgroundColor: C.yellow, paddingHorizontal: 18, paddingVertical: 12, borderRadius: 16, marginTop: 28 },
  faceBtnText: { color: C.white, fontSize: 14, fontWeight: '900' },

  sectionRow: { marginHorizontal: 20, marginTop: 30, marginBottom: 16, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  sectionTitle: { color: C.text, fontSize: 19, fontWeight: '900' },
  viewAll: { color: C.muted, fontSize: 14, fontWeight: '700' },
  recommendGrid: { paddingHorizontal: 20, flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  recommendCard: { width: '48%', backgroundColor: C.white, borderRadius: 16, overflow: 'hidden', borderWidth: 1, borderColor: C.line, marginBottom: 16, ...cardShadow },
  recommendImg: { width: '100%', height: 128, backgroundColor: C.line },
  recommendInfo: { padding: 13 },
  recommendName: { color: C.text, fontSize: 15, fontWeight: '900' },
  recommendPrice: { color: C.muted, fontSize: 13, fontWeight: '800', marginTop: 8 },

  orderRoot: { flex: 1, backgroundColor: C.white },
  orderTop: { backgroundColor: C.white, paddingHorizontal: 24, paddingTop: 86, paddingBottom: 22 },
  orderTitle: { fontSize: 30, fontWeight: '900', color: C.text, letterSpacing: -0.8, marginBottom: 20 },
  searchBar: { height: 50, borderRadius: 25, backgroundColor: C.input, paddingHorizontal: 18, flexDirection: 'row', alignItems: 'center', marginBottom: 20 },
  searchIcon: { fontSize: 28, color: C.icon, marginRight: 9, marginTop: -2 },
  searchInput: { flex: 1, color: C.text, fontSize: 16, fontWeight: '600', padding: 0 },
  chipRow: { gap: 10, paddingRight: 24 },
  chip: { backgroundColor: C.input, borderRadius: 20, paddingHorizontal: 20, paddingVertical: 11 },
  chipActive: { backgroundColor: C.yellow },
  chipText: { color: '#52525B', fontSize: 15, fontWeight: '800' },
  chipTextActive: { color: C.white },
  orderList: { flex: 1, backgroundColor: C.white },
  orderListContent: { paddingHorizontal: 24, paddingTop: 14, paddingBottom: 118 },
  orderItemCard: { minHeight: 112, borderRadius: 20, backgroundColor: C.white, borderWidth: 1, borderColor: C.line, padding: 16, marginBottom: 18, flexDirection: 'row', alignItems: 'center', ...cardShadow },
  orderItemImage: { width: 78, height: 78, borderRadius: 16, backgroundColor: C.line },
  orderItemInfo: { flex: 1, marginLeft: 18 },
  orderItemName: { color: C.text, fontSize: 19, fontWeight: '900', letterSpacing: -0.2 },
  orderItemEng: { color: C.muted, fontSize: 14, fontWeight: '700', marginTop: 5 },
  orderItemPrice: { color: C.text, fontSize: 20, fontWeight: '900', marginTop: 12 },

  pageTitle: { color: C.text, fontSize: 28, fontWeight: '900', marginBottom: 16 },
  whiteCard: { backgroundColor: C.white, borderRadius: 20, padding: 18, borderWidth: 1, borderColor: C.line, marginTop: 16, ...cardShadow },
  detailImg: { width: '100%', height: 270, borderRadius: 22, backgroundColor: C.line },
  menuCategory: { color: C.yellow, fontSize: 12, fontWeight: '900' },
  detailName: { color: C.text, fontSize: 30, fontWeight: '900', marginTop: 4 },
  detailEng: { color: C.muted, fontSize: 14, marginTop: 2 },
  detailDesc: { color: C.muted, fontSize: 14, lineHeight: 22, marginTop: 12 },
  detailPrice: { color: C.green, fontSize: 22, fontWeight: '900', marginTop: 16 },
  optionTitle: { color: C.text, fontSize: 18, fontWeight: '900', marginBottom: 12 },
  optionRow: { flexDirection: 'row', gap: 10 },
  optionButton: { flex: 1, borderRadius: 14, paddingVertical: 15, alignItems: 'center', backgroundColor: '#FAFAFA', borderWidth: 1, borderColor: C.line },
  optionActive: { backgroundColor: C.yellow, borderColor: C.yellow },
  optionDisabled: { opacity: 0.38 },
  optionText: { color: C.green, fontSize: 15, fontWeight: '900' },
  optionTextActive: { color: C.white },
  qtyRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 24 },
  qtyBtn: { width: 52, height: 52, borderRadius: 26, backgroundColor: C.green, alignItems: 'center', justifyContent: 'center' },
  qtyBtnText: { color: C.white, fontSize: 26, fontWeight: '900' },
  qty: { color: C.text, fontSize: 28, fontWeight: '900', minWidth: 40, textAlign: 'center' },
  mainAction: { backgroundColor: C.yellow, borderRadius: 16, paddingVertical: 16, alignItems: 'center', marginTop: 18 },
  mainActionText: { color: C.white, fontSize: 16, fontWeight: '900' },

  cartCard: { backgroundColor: C.white, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: C.line, marginBottom: 12, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cartName: { color: C.text, fontSize: 18, fontWeight: '900' },
  cartMeta: { color: C.muted, marginTop: 6, fontWeight: '600' },
  cartPrice: { color: C.green, fontSize: 16, fontWeight: '900', marginTop: 8 },
  deleteBtn: { borderWidth: 1, borderColor: C.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 9 },
  deleteText: { color: C.muted, fontWeight: '800' },
  totalCard: { backgroundColor: C.green, borderRadius: 22, padding: 20, marginTop: 10 },
  totalLabel: { color: '#D4D4D8', fontWeight: '700' },
  total: { color: C.white, fontSize: 28, fontWeight: '900', marginTop: 6 },

  titleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  adminBtn: { backgroundColor: C.green, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 9 },
  adminText: { color: C.white, fontWeight: '900' },
  adminCard: { backgroundColor: C.white, borderRadius: 20, padding: 12, marginBottom: 14, borderWidth: 1, borderColor: C.line },
  greenAction: { backgroundColor: C.green, borderRadius: 16, paddingVertical: 14, alignItems: 'center', marginTop: 12 },
  greenActionText: { color: C.white, fontWeight: '900' },
  historyCard: { backgroundColor: C.white, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: C.line, marginBottom: 14 },
  orderId: { color: C.text, fontSize: 17, fontWeight: '900' },
  orderDate: { color: C.muted, fontSize: 13, marginTop: 6 },
  orderLine: { color: C.text, fontSize: 15, marginTop: 8, fontWeight: '600' },
  historyPrice: { color: C.green, fontSize: 18, fontWeight: '900', marginTop: 10 },
  statusPill: { borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6 },
  statusText: { fontSize: 12, fontWeight: '900' },

  profileCard: { backgroundColor: C.white, borderRadius: 24, padding: 24, alignItems: 'center', borderWidth: 1, borderColor: C.line, ...cardShadow },
  avatar: { width: 78, height: 78, borderRadius: 39, backgroundColor: C.yellow, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: C.white, fontSize: 30, fontWeight: '900' },
  profileName: { color: C.text, fontSize: 24, fontWeight: '900', marginTop: 14 },
  profileBody: { color: C.muted, fontSize: 14, textAlign: 'center', lineHeight: 21, marginTop: 8 },

  empty: { backgroundColor: C.white, borderRadius: 22, padding: 30, alignItems: 'center', borderWidth: 1, borderColor: C.line },
  emptyIcon: { fontSize: 40 },
  emptyTitle: { color: C.text, fontSize: 19, fontWeight: '900', marginTop: 12 },
  emptyBody: { color: C.muted, fontSize: 14, lineHeight: 21, textAlign: 'center', marginTop: 6 },

  nav: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 86, backgroundColor: C.white, borderTopWidth: 1, borderTopColor: C.line, flexDirection: 'row', justifyContent: 'space-around', paddingTop: 10 },
  navItem: { flex: 1, alignItems: 'center' },
  navIcon: { color: C.icon, fontSize: 28, fontWeight: '900' },
  navActive: { color: C.yellow },
  navLabel: { color: C.muted, fontSize: 12, fontWeight: '700', marginTop: 3 },
});
