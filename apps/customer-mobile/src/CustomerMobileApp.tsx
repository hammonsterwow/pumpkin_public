import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Image,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { ApiOrderStatus, getPublicOrderStatus, submitAppOrder } from './api/orderApi';
import { requestFaceEmbedding } from './firebase/faceEmbeddingBackend';
import {
  getStoredFaceEnrollmentPoses,
  getStoredUserProfile,
  resetFirebaseFaceEnrollment,
  saveFaceEnrollmentPreferences,
  saveUserPreferences,
  uploadTemporaryFaceFrame,
} from './firebase/faceEnrollment';
import { MENU_DATA } from './native/menuData';
import { CartItem, MenuItem, Order, Temperature } from './native/types';
import FaceCaptureScreen from './screens/FaceCaptureScreen';
import FaceConsentScreen from './screens/FaceConsentScreen';
import FaceRegistrationResultScreen from './screens/FaceRegistrationResultScreen';
import ProfileScreen from './screens/ProfileScreen';
import {
  CustomerTemperature,
  FaceEnrollmentFinalizeResponse,
  FaceEnrollmentFrameResponse,
  FaceEnrollmentStatus,
  FacePose,
} from './types/faceProfile';

type CustomerMobileAppProps = {
  customerId: string;
  customerName: string;
};

type AppScreen =
  | 'home'
  | 'menu'
  | 'detail'
  | 'cart'
  | 'orders'
  | 'profile'
  | 'faceConsent'
  | 'faceCapture'
  | 'faceResult';

const FACE_POSES: FacePose[] = ['front', 'left', 'right', 'up', 'down'];

function createEnrollmentStatus(customerId: string, completed: FacePose[] = [], embeddingReady = false, model: string | null = null): FaceEnrollmentStatus {
  const nextPose = FACE_POSES.find((pose) => !completed.includes(pose)) ?? null;
  return {
    customer_id: customerId,
    required_count: FACE_POSES.length,
    sample_count: completed.length,
    complete: completed.length === FACE_POSES.length,
    embedding_ready: embeddingReady,
    model,
    pipeline_backend: 'firebase-storage-backend-embedding',
    next_pose: nextPose,
    next_pose_label: nextPose,
    updated_at: new Date().toISOString(),
    poses: FACE_POSES.map((pose) => ({
      pose,
      label: pose,
      registered: completed.includes(pose),
      captured_at: completed.includes(pose) ? new Date().toISOString() : null,
      quality: null,
    })),
  };
}

const won = (value: number) => `${value.toLocaleString('ko-KR')}원`;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '요청 처리 중 알 수 없는 오류가 발생했습니다.';
}

export default function CustomerMobileApp({ customerId, customerName }: CustomerMobileAppProps) {
  const [screen, setScreen] = useState<AppScreen>('home');
  const [selectedMenu, setSelectedMenu] = useState<MenuItem | null>(null);
  const [temperature, setTemperature] = useState<Temperature>('ICE');
  const [quantity, setQuantity] = useState(1);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);

  const [preferredMenuId, setPreferredMenuId] = useState<number | null>(MENU_DATA[0]?.id ?? null);
  const [preferredTemperature, setPreferredTemperature] = useState<CustomerTemperature>('ICE');
  const [preferredQuantity, setPreferredQuantity] = useState(1);
  const [completedPoses, setCompletedPoses] = useState<FacePose[]>([]);
  const [enrollment, setEnrollment] = useState<FaceEnrollmentStatus>(() => createEnrollmentStatus(customerId));
  const [lastFrame, setLastFrame] = useState<FaceEnrollmentFrameResponse | null>(null);
  const [finalizeResult, setFinalizeResult] = useState<FaceEnrollmentFinalizeResponse | null>(null);
  const [faceBusy, setFaceBusy] = useState(false);
  const [faceError, setFaceError] = useState('');

  useEffect(() => {
    let active = true;

    const restorePersistedProfile = async () => {
      setFaceBusy(true);
      setFaceError('');
      try {
        const [profileResult, posesResult] = await Promise.allSettled([
          getStoredUserProfile(customerId),
          getStoredFaceEnrollmentPoses(customerId),
        ]);
        if (!active) return;

        if (profileResult.status === 'rejected' && posesResult.status === 'rejected') {
          throw profileResult.reason;
        }

        const profile = profileResult.status === 'fulfilled' ? profileResult.value : null;
        const storedPoses = posesResult.status === 'fulfilled' ? posesResult.value : [];

        if (profile) {
          const preferredMenu = typeof profile.preferredMenu === 'string'
            ? MENU_DATA.find((menu) => menu.name === profile.preferredMenu)
            : undefined;
          if (preferredMenu) setPreferredMenuId(preferredMenu.id);

          const storedTemperature = profile.preferredTemperature;
          if (storedTemperature === 'HOT' || storedTemperature === 'ICE' || storedTemperature === 'NONE') {
            setPreferredTemperature(storedTemperature);
          }

          const storedQuantity = profile.preferredQuantity;
          if (typeof storedQuantity === 'number' && Number.isFinite(storedQuantity)) {
            setPreferredQuantity(Math.max(1, Math.min(20, storedQuantity)));
          }
        }

        const registered = profile?.faceRegistered === true
          || profile?.faceEnrollmentStatus === 'registered';
        const restoredPoses = registered ? FACE_POSES : storedPoses;
        setCompletedPoses(restoredPoses);
        setEnrollment(createEnrollmentStatus(
          customerId,
          restoredPoses,
          registered,
          registered && typeof profile?.faceEmbedding === 'object'
            ? String((profile.faceEmbedding as Record<string, unknown>).model ?? '')
            : null,
        ));

        if (profileResult.status === 'rejected') {
          setFaceError(errorMessage(profileResult.reason));
        } else if (posesResult.status === 'rejected' && !registered) {
          setFaceError(errorMessage(posesResult.reason));
        }
      } catch (error) {
        if (active) setFaceError(errorMessage(error));
      } finally {
        if (active) setFaceBusy(false);
      }
    };

    void restorePersistedProfile();
    return () => {
      active = false;
    };
  }, [customerId]);

  useEffect(() => {
    const active = orders.filter(
      (order) => !['PICKED_UP', 'CANCELLED'].includes(order.apiStatus),
    );
    if (active.length === 0) return undefined;
    const timer = setInterval(() => {
      void Promise.all(active.map(async (order) => {
        try {
          return await getPublicOrderStatus(order.orderId, order.requestId);
        } catch {
          return null;
        }
      })).then((updates) => {
        const byId = new Map(
          updates.filter((value) => value !== null).map((value) => [value!.order_id, value!]),
        );
        setOrders((current) => current.map((order) => {
          const update = byId.get(order.orderId);
          return update ? {
            ...order,
            status: apiStatusLabel(update.status),
            apiStatus: update.status,
          } : order;
        }));
      });
    }, 3000);
    return () => clearInterval(timer);
  }, [orders]);

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
    setCart((previous) => [...previous, { menu: selectedMenu, temperature, quantity }]);
    Alert.alert('장바구니 추가', `${selectedMenu.name} ${quantity}잔을 담았습니다.`);
    setScreen('cart');
  };

  const placeOrder = async () => {
    if (cart.length === 0) {
      Alert.alert('주문 불가', '장바구니에 메뉴를 먼저 담아주세요.');
      return;
    }

    try {
      const orderedItems = [...cart];
      const response = await submitAppOrder(orderedItems, customerId);
      const order: Order = {
        id: response.order_number,
        orderId: response.order_id,
        requestId: response.request_id,
        items: orderedItems,
        status: '접수',
        apiStatus: response.status,
        totalPrice: response.total_price,
        createdAt: new Date(response.created_at).toLocaleString('ko-KR'),
      };
      setOrders((previous) => [order, ...previous]);
      setCart([]);
      Alert.alert('주문 완료', `주문번호 ${response.order_number}로 접수되었습니다.`);
      setScreen('orders');
    } catch (error) {
      Alert.alert('주문 실패', errorMessage(error));
    }
  };

  const selectedPreferredMenu = MENU_DATA.find((menu) => menu.id === preferredMenuId) ?? MENU_DATA[0];

  const persistPreferences = async (
    menuId = preferredMenuId,
    nextTemperature = preferredTemperature,
    nextQuantity = preferredQuantity,
  ) => {
    const menu = MENU_DATA.find((item) => item.id === menuId);
    if (!menu) return;

    const safeTemperature: CustomerTemperature = menu.isIcedOnly ? 'ICE' : nextTemperature;
    const safeQuantity = Math.max(1, Math.min(20, nextQuantity));

    await saveUserPreferences({
      uid: customerId,
      name: customerName,
      preferredMenu: menu.name,
      preferredTemperature: safeTemperature,
      preferredQuantity: safeQuantity,
    });
  };

  const savePreferences = async () => {
    if (!selectedPreferredMenu) {
      Alert.alert('저장 실패', '선호 메뉴를 선택해주세요.');
      return;
    }

    setFaceBusy(true);
    setFaceError('');
    try {
      await persistPreferences();
      Alert.alert(
        '저장 완료',
        '선호 메뉴·온도·수량을 변경했습니다. 기존 얼굴 정보는 그대로 유지됩니다.',
      );
    } catch (error) {
      const message = errorMessage(error);
      setFaceError(message);
      Alert.alert('저장 실패', message);
    } finally {
      setFaceBusy(false);
    }
  };

  const prepareFaceEnrollment = async () => {
    if (!selectedPreferredMenu) {
      setFaceError('선호 메뉴를 선택해주세요.');
      return;
    }
    const safeTemperature: CustomerTemperature = selectedPreferredMenu.isIcedOnly
      ? 'ICE'
      : preferredTemperature;

    setFaceBusy(true);
    setFaceError('');
    try {
      await saveFaceEnrollmentPreferences({
        uid: customerId,
        name: customerName,
        preferredMenu: selectedPreferredMenu.name,
        preferredTemperature: safeTemperature,
        preferredQuantity,
      });
      setPreferredTemperature(safeTemperature);
      setCompletedPoses([]);
      const status = createEnrollmentStatus(customerId);
      setEnrollment(status);
      setLastFrame(null);
      setFinalizeResult(null);
      setScreen('faceCapture');
    } catch (error) {
      setFaceError(errorMessage(error));
    } finally {
      setFaceBusy(false);
    }
  };

  const captureFaceFrame = async (pose: FacePose, imageData: string): Promise<FaceEnrollmentFrameResponse> => {
    await uploadTemporaryFaceFrame(customerId, pose, imageData);
    const nextCompleted = completedPoses.includes(pose) ? completedPoses : [...completedPoses, pose];
    setCompletedPoses(nextCompleted);
    const status = createEnrollmentStatus(customerId, nextCompleted);
    setEnrollment(status);

    const response: FaceEnrollmentFrameResponse = {
      accepted: true,
      detected_pose: pose,
      quality: null,
      reason: 'uploaded_to_firebase_storage',
      face_count: 1,
      next_pose: status.next_pose,
      next_pose_label: status.next_pose_label,
      complete: status.complete,
      status,
    };
    setLastFrame(response);
    return response;
  };

  const completeFaceEnrollment = async () => {
    setFaceBusy(true);
    setFaceError('');
    try {
      const embedding = await requestFaceEmbedding(customerId);
      const status = createEnrollmentStatus(customerId, FACE_POSES, embedding.embedding_ready, embedding.model);
      const result: FaceEnrollmentFinalizeResponse = {
        embedding_ready: embedding.embedding_ready,
        model: embedding.model,
        status,
        embedding_dimension: embedding.embedding_dimension,
        generated_at: embedding.generated_at ?? new Date().toISOString(),
      };
      setEnrollment(status);
      setFinalizeResult(result);
      setScreen('faceResult');
    } catch (error) {
      setFaceError(errorMessage(error));
    } finally {
      setFaceBusy(false);
    }
  };

  const resetEnrollment = async (openCapture = true) => {
    setFaceBusy(true);
    setFaceError('');
    try {
      await resetFirebaseFaceEnrollment(customerId);
      setCompletedPoses([]);
      setEnrollment(createEnrollmentStatus(customerId));
      setLastFrame(null);
      setFinalizeResult(null);
      if (openCapture) setScreen('faceCapture');
    } catch (error) {
      setFaceError(errorMessage(error));
    } finally {
      setFaceBusy(false);
    }
  };

  const confirmReset = () => {
    Alert.alert('얼굴 등록 데이터 초기화', 'Firebase에 저장된 임시 얼굴 사진과 임베딩 정보를 삭제할까요?', [
      { text: '취소', style: 'cancel' },
      { text: '삭제', style: 'destructive', onPress: () => void resetEnrollment(false) },
    ]);
  };

  const selectPreferredMenu = (menuId: number) => {
    const menu = MENU_DATA.find((item) => item.id === menuId);
    if (!menu) return;
    setPreferredMenuId(menuId);
    if (menu.isIcedOnly) setPreferredTemperature('ICE');
  };

  const selectPreferredTemperature = (nextTemperature: CustomerTemperature) => {
    const menu = MENU_DATA.find((item) => item.id === preferredMenuId);
    setPreferredTemperature(menu?.isIcedOnly ? 'ICE' : nextTemperature);
  };

  const changePreferredQuantity = (nextQuantity: number) => {
    setPreferredQuantity(Math.max(1, Math.min(20, nextQuantity)));
  };

  const renderScreen = () => {
    switch (screen) {
      case 'home':
        return <HomeScreen customerName={customerName} onNavigate={setScreen} onSelectMenu={openDetail} />;
      case 'menu':
        return <MenuScreen onSelectMenu={openDetail} />;
      case 'detail':
        return selectedMenu ? (
          <DetailScreen
            menu={selectedMenu}
            temperature={temperature}
            quantity={quantity}
            onTemperature={setTemperature}
            onQuantity={setQuantity}
            onAdd={addToCart}
          />
        ) : <MenuScreen onSelectMenu={openDetail} />;
      case 'cart':
        return <CartScreen cart={cart} total={cartTotal} onRemove={(index) => setCart((items) => items.filter((_, current) => current !== index))} onOrder={placeOrder} />;
      case 'orders':
        return <OrdersScreen orders={orders} />;
      case 'profile':
        return (
          <ProfileScreen
            enrollment={enrollment}
            preferredMenuId={preferredMenuId}
            preferredTemperature={preferredTemperature}
            preferredQuantity={preferredQuantity}
            busy={faceBusy}
            error={faceError}
            onSelectPreferredMenu={selectPreferredMenu}
            onSelectPreferredTemperature={selectPreferredTemperature}
            onChangePreferredQuantity={changePreferredQuantity}
            onSavePreferences={() => void savePreferences()}
            onRegisterFace={() => { setFaceError(''); setScreen('faceConsent'); }}
            onDeleteFace={confirmReset}
          />
        );
      case 'faceConsent':
        return <FaceConsentScreen onBack={() => setScreen('profile')} onAgree={() => void prepareFaceEnrollment()} />;
      case 'faceCapture':
        return (
          <FaceCaptureScreen
            status={enrollment}
            lastFrame={lastFrame}
            submitting={faceBusy}
            error={faceError}
            onBack={() => setScreen('profile')}
            onCaptureImage={captureFaceFrame}
            onFinalize={completeFaceEnrollment}
            onReset={() => resetEnrollment(true)}
          />
        );
      case 'faceResult':
        return finalizeResult ? (
          <FaceRegistrationResultScreen
            result={finalizeResult}
            onDone={() => setScreen('profile')}
            onRetry={() => void resetEnrollment(true)}
          />
        ) : <LoadingScreen message="최종화 결과를 불러오는 중입니다." />;
      default:
        return <HomeScreen customerName={customerName} onNavigate={setScreen} onSelectMenu={openDetail} />;
    }
  };

  const showBottomNav = !['faceConsent', 'faceCapture', 'faceResult'].includes(screen);

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <View style={styles.root}>
        <View style={styles.body}>{renderScreen()}</View>
        {showBottomNav ? <BottomNav screen={screen} cartCount={cart.length} onNavigate={setScreen} /> : null}
      </View>
    </SafeAreaView>
  );
}

function apiStatusLabel(status: ApiOrderStatus): Order['status'] {
  const labels: Record<ApiOrderStatus, Order['status']> = {
    RECEIVED: '접수',
    PREPARING: '제조중',
    READY: '픽업가능',
    PICKED_UP: '완료',
    CANCELLED: '취소',
  };
  return labels[status];
}

function HomeScreen({ customerName, onNavigate, onSelectMenu }: { customerName: string; onNavigate: (screen: AppScreen) => void; onSelectMenu: (menu: MenuItem) => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.homeContent} showsVerticalScrollIndicator={false}>
      <View style={styles.header}>
        <Text style={styles.hello}>안녕하세요, <Text style={styles.yellow}>{customerName}</Text> 님</Text>
        <Text style={styles.location}>⌖ 이화여대 점</Text>
      </View>
      <Pressable style={styles.orderHero} onPress={() => onNavigate('menu')}>
        <Text style={styles.heroTitle}>다이렉트 오더로{`\n`}빠르게 주문하세요</Text>
        <Text style={styles.heroBody}>README와 NLU의 공통 메뉴 5종으로 주문합니다.</Text>
        <View style={styles.heroButton}><Text style={styles.heroButtonText}>주문하기</Text></View>
      </Pressable>
      <Pressable style={styles.faceHero} onPress={() => onNavigate('profile')}>
        <Text style={styles.faceBadge}>NEW</Text>
        <Text style={styles.faceTitle}>단골 맞춤 서비스 등록</Text>
        <Text style={styles.faceBody}>선호 메뉴·온도·수량과 얼굴을 등록하면 매장 로봇이 평소 주문을 바로 추천합니다.</Text>
      </Pressable>
      <View style={styles.sectionRow}>
        <Text style={styles.sectionTitle}>공통 메뉴</Text>
        <Pressable onPress={() => onNavigate('menu')}><Text style={styles.link}>전체보기</Text></Pressable>
      </View>
      <View style={styles.grid}>
        {MENU_DATA.map((menu) => (
          <Pressable key={menu.id} style={styles.menuCard} onPress={() => onSelectMenu(menu)}>
            <Image source={{ uri: menu.image }} style={styles.menuImage} />
            <View style={styles.menuCardText}>
              <Text style={styles.menuName}>{menu.name}</Text>
              <Text style={styles.menuPrice}>{won(menu.price)}</Text>
            </View>
          </Pressable>
        ))}
      </View>
    </ScrollView>
  );
}

function MenuScreen({ onSelectMenu }: { onSelectMenu: (menu: MenuItem) => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.pageContent} showsVerticalScrollIndicator={false}>
      <Text style={styles.pageTitle}>오더</Text>
      <Text style={styles.pageDescription}>아메리카노, 카페라떼, 바닐라라떼, 레몬에이드, 딸기스무디를 제공합니다.</Text>
      {MENU_DATA.map((menu) => (
        <Pressable key={menu.id} style={styles.listCard} onPress={() => onSelectMenu(menu)}>
          <Image source={{ uri: menu.image }} style={styles.listImage} />
          <View style={styles.listInfo}><Text style={styles.menuName}>{menu.name}</Text><Text style={styles.menuPrice}>{won(menu.price)}</Text></View>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function DetailScreen({ menu, temperature, quantity, onTemperature, onQuantity, onAdd }: { menu: MenuItem; temperature: Temperature; quantity: number; onTemperature: (temperature: Temperature) => void; onQuantity: (quantity: number) => void; onAdd: () => void }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.pageContent}>
      <Image source={{ uri: menu.image }} style={styles.detailImage} />
      <Text style={styles.detailTitle}>{menu.name}</Text>
      <Text style={styles.detailDescription}>{menu.description}</Text>
      <View style={styles.optionCard}><Text style={styles.optionTitle}>온도</Text><View style={styles.row}>{['ICE', 'HOT'].map((item) => <Pressable key={item} disabled={menu.isIcedOnly && item === 'HOT'} style={[styles.choice, temperature === item && styles.choiceActive, menu.isIcedOnly && item === 'HOT' && styles.choiceDisabled]} onPress={() => onTemperature(item as Temperature)}><Text>{item}</Text></Pressable>)}</View></View>
      <View style={styles.optionCard}><Text style={styles.optionTitle}>수량</Text><View style={styles.quantityRow}><Pressable style={styles.qtyButton} onPress={() => onQuantity(Math.max(1, quantity - 1))}><Text style={styles.qtyText}>−</Text></Pressable><Text style={styles.qtyValue}>{quantity}</Text><Pressable style={styles.qtyButton} onPress={() => onQuantity(Math.min(20, quantity + 1))}><Text style={styles.qtyText}>＋</Text></Pressable></View></View>
      <Pressable style={styles.orderButton} onPress={onAdd}><Text style={styles.orderButtonText}>장바구니 담기 · {won(menu.price * quantity)}</Text></Pressable>
    </ScrollView>
  );
}

function CartScreen({ cart, total, onRemove, onOrder }: { cart: CartItem[]; total: number; onRemove: (index: number) => void; onOrder: () => void }) {
  return <ScrollView style={styles.scroll} contentContainerStyle={styles.pageContent}><Text style={styles.pageTitle}>장바구니</Text>{cart.length === 0 ? <Text style={styles.empty}>담긴 메뉴가 없습니다.</Text> : cart.map((item, index) => <View key={`${item.menu.id}-${index}`} style={styles.cartCard}><View style={{ flex: 1 }}><Text style={styles.menuName}>{item.menu.name}</Text><Text style={styles.cartMeta}>{item.temperature} · {item.quantity}잔</Text></View><Pressable onPress={() => onRemove(index)}><Text style={styles.remove}>삭제</Text></Pressable></View>)}<View style={styles.totalRow}><Text style={styles.totalLabel}>합계</Text><Text style={styles.totalValue}>{won(total)}</Text></View><Pressable style={styles.orderButton} onPress={onOrder}><Text style={styles.orderButtonText}>주문하기</Text></Pressable></ScrollView>;
}

function OrdersScreen({ orders }: { orders: Order[] }) {
  return <ScrollView style={styles.scroll} contentContainerStyle={styles.pageContent}><Text style={styles.pageTitle}>주문 내역</Text>{orders.length === 0 ? <Text style={styles.empty}>아직 주문 내역이 없습니다.</Text> : orders.map((order) => <View key={order.id} style={styles.orderCard}><Text style={styles.orderId}>#{order.id}</Text><Text style={styles.orderStatus}>{order.status}</Text><Text style={styles.orderDate}>{order.createdAt}</Text><Text style={styles.orderTotal}>{won(order.totalPrice)}</Text></View>)}</ScrollView>;
}

function LoadingScreen({ message }: { message: string }) {
  return <View style={styles.loading}><Text style={styles.loadingText}>{message}</Text></View>;
}

function BottomNav({ screen, cartCount, onNavigate }: { screen: AppScreen; cartCount: number; onNavigate: (screen: AppScreen) => void }) {
  const items: Array<[AppScreen, string]> = [['home', '홈'], ['menu', '오더'], ['orders', '주문'], ['cart', `장바구니${cartCount ? ` ${cartCount}` : ''}`], ['profile', '마이']];
  return <View style={styles.bottomNav}>{items.map(([target, label]) => <Pressable key={target} style={styles.navItem} onPress={() => onNavigate(target)}><Text style={[styles.navText, screen === target && styles.navTextActive]}>{label}</Text></Pressable>)}</View>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F4F4F5' },
  root: { flex: 1 }, body: { flex: 1 }, scroll: { flex: 1 },
  homeContent: { padding: 20, paddingBottom: 120 }, pageContent: { padding: 20, paddingBottom: 120 },
  header: { marginBottom: 18 }, hello: { fontSize: 24, fontWeight: '900', color: '#18181B' }, yellow: { color: '#E09D00' }, location: { color: '#71717A', marginTop: 6 },
  orderHero: { backgroundColor: '#1E3826', borderRadius: 28, padding: 24 }, heroTitle: { color: '#FFF', fontSize: 28, fontWeight: '900', lineHeight: 36 }, heroBody: { color: '#D4D4D8', marginTop: 10, lineHeight: 21 }, heroButton: { alignSelf: 'flex-start', backgroundColor: '#E09D00', borderRadius: 16, paddingHorizontal: 18, paddingVertical: 12, marginTop: 18 }, heroButtonText: { color: '#FFF', fontWeight: '900' },
  faceHero: { backgroundColor: '#FFF7E0', borderRadius: 24, padding: 20, marginTop: 14 }, faceBadge: { color: '#E09D00', fontWeight: '900' }, faceTitle: { fontSize: 19, fontWeight: '900', color: '#18181B', marginTop: 8 }, faceBody: { color: '#71500A', marginTop: 6, lineHeight: 20 },
  sectionRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 28, marginBottom: 12 }, sectionTitle: { fontSize: 20, fontWeight: '900' }, link: { color: '#E09D00', fontWeight: '800' }, grid: { gap: 12 }, menuCard: { backgroundColor: '#FFF', borderRadius: 22, overflow: 'hidden' }, menuImage: { width: '100%', height: 160, backgroundColor: '#E5E7EB' }, menuCardText: { padding: 16 }, menuName: { fontSize: 16, fontWeight: '900', color: '#18181B' }, menuPrice: { color: '#E09D00', fontWeight: '900', marginTop: 4 },
  pageTitle: { fontSize: 28, fontWeight: '900', color: '#18181B', marginBottom: 8 }, pageDescription: { color: '#71717A', lineHeight: 21, marginBottom: 18 }, listCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 20, padding: 12, marginBottom: 10 }, listImage: { width: 72, height: 72, borderRadius: 16 }, listInfo: { marginLeft: 14 },
  detailImage: { width: '100%', height: 260, borderRadius: 28, backgroundColor: '#E5E7EB' }, detailTitle: { fontSize: 28, fontWeight: '900', marginTop: 20 }, detailDescription: { color: '#71717A', marginTop: 8, lineHeight: 21 }, optionCard: { backgroundColor: '#FFF', borderRadius: 20, padding: 18, marginTop: 16 }, optionTitle: { fontWeight: '900', fontSize: 16 }, row: { flexDirection: 'row', gap: 10, marginTop: 12 }, choice: { flex: 1, height: 46, borderRadius: 14, backgroundColor: '#F4F4F5', alignItems: 'center', justifyContent: 'center' }, choiceActive: { backgroundColor: '#FFF7E0', borderWidth: 1, borderColor: '#E09D00' }, choiceDisabled: { opacity: 0.3 }, quantityRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 24, marginTop: 12 }, qtyButton: { width: 46, height: 46, borderRadius: 14, backgroundColor: '#F4F4F5', alignItems: 'center', justifyContent: 'center' }, qtyText: { fontSize: 24, fontWeight: '900' }, qtyValue: { fontSize: 22, fontWeight: '900' }, orderButton: { height: 58, borderRadius: 18, backgroundColor: '#E09D00', alignItems: 'center', justifyContent: 'center', marginTop: 20 }, orderButtonText: { color: '#FFF', fontSize: 17, fontWeight: '900' },
  empty: { color: '#71717A', marginTop: 20 }, cartCard: { flexDirection: 'row', backgroundColor: '#FFF', borderRadius: 18, padding: 16, marginTop: 10 }, cartMeta: { color: '#71717A', marginTop: 4 }, remove: { color: '#EF4444', fontWeight: '800' }, totalRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 24 }, totalLabel: { fontSize: 17, fontWeight: '900' }, totalValue: { fontSize: 20, fontWeight: '900', color: '#E09D00' }, orderCard: { backgroundColor: '#FFF', borderRadius: 20, padding: 18, marginTop: 12 }, orderId: { fontWeight: '900' }, orderStatus: { color: '#1E3826', fontWeight: '900', marginTop: 6 }, orderDate: { color: '#71717A', marginTop: 6 }, orderTotal: { color: '#E09D00', fontWeight: '900', marginTop: 10 },
  bottomNav: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 78, backgroundColor: '#FFF', borderTopWidth: 1, borderTopColor: '#E5E7EB', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around' }, navItem: { flex: 1, alignItems: 'center' }, navText: { color: '#A1A1AA', fontSize: 12, fontWeight: '800' }, navTextActive: { color: '#E09D00' }, loading: { flex: 1, alignItems: 'center', justifyContent: 'center' }, loadingText: { color: '#71717A', fontWeight: '800' },
});
