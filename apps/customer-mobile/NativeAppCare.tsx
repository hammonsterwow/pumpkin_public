import React, { useState } from 'react';
import { Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import CareScreen from './src/native/CareScreen';

type AppScreen = 'home' | 'care' | 'profile';

export default function NativeAppCare() {
  const [screen, setScreen] = useState<AppScreen>('home');

  if (screen === 'care') {
    return (
      <SafeAreaView style={styles.safe}>
        <StatusBar style="dark" />
        <CareScreen onBack={() => setScreen('profile')} onDone={() => setScreen('home')} />
        <BottomNav screen={screen} setScreen={setScreen} />
      </SafeAreaView>
    );
  }

  if (screen === 'profile') {
    return (
      <SafeAreaView style={styles.safe}>
        <StatusBar style="dark" />
        <View style={styles.page}>
          <Text style={styles.title}>Other</Text>
          <Text style={styles.welcome}><Text style={styles.yellow}>DANHOBAK</Text> 님{`\n`}환영합니다! 🙌🏻</Text>
          <View style={styles.grid}>
            {['별 히스토리', '전자영수증', '계정정보', '나만의 메뉴', '단골 등록', '개인정보 관리'].map((item) => (
              <Pressable key={item} style={styles.mini} onPress={item === '단골 등록' ? () => setScreen('care') : undefined}>
                <Text style={styles.miniIcon}>{item === '단골 등록' ? '⌗' : '☆'}</Text>
                <Text style={styles.miniText}>{item}</Text>
              </Pressable>
            ))}
          </View>
          <Pressable style={styles.careRow} onPress={() => setScreen('care')}>
            <View style={styles.careIcon}><Text style={styles.careIconText}>%</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={styles.careSub}>매일 만나는 맞춤 혜택</Text>
              <Text style={styles.careTitle}>단골 맞춤 서비스</Text>
            </View>
            <Text style={styles.arrow}>›</Text>
          </Pressable>
        </View>
        <BottomNav screen={screen} setScreen={setScreen} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <View style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.hello}>안녕하세요, <Text style={styles.yellow}>단호박 </Text>님</Text>
          <Text style={styles.location}>⌖ 이화여대 점 ›</Text>
        </View>
        <Pressable style={styles.orderCard}>
          <Text style={styles.orderTitle}>다이렉트 오더로{`\n`}빠르게 주문하세요</Text>
          <Text style={styles.orderSub}>줄 서지 않고 미리 주문하고 픽업!</Text>
          <View style={styles.orderButton}><Text style={styles.orderButtonText}>주문하기</Text></View>
        </Pressable>
        <Pressable style={styles.greenCard} onPress={() => setScreen('care')}>
          <View style={styles.badge}><Text style={styles.badgeText}>NEW</Text></View>
          <Text style={styles.greenTitle}>단골 맞춤 서비스 등록</Text>
          <Text style={styles.greenBody}>즐겨찾기 메뉴를 등록하고 매장에서 더 빠른 맞춤 서비스를 경험하세요.</Text>
          <View style={styles.yellowButton}><Text style={styles.yellowButtonText}>지금 등록하기</Text></View>
        </Pressable>
      </View>
      <BottomNav screen={screen} setScreen={setScreen} />
    </SafeAreaView>
  );
}

function BottomNav({ screen, setScreen }: { screen: AppScreen; setScreen: (screen: AppScreen) => void }) {
  return (
    <View style={styles.nav}>
      <Pressable style={styles.navItem} onPress={() => setScreen('home')}><Text style={[styles.navIcon, screen === 'home' && styles.active]}>⌂</Text><Text style={[styles.navLabel, screen === 'home' && styles.active]}>홈</Text></Pressable>
      <Pressable style={styles.navItem}><Text style={styles.navIcon}>☕</Text><Text style={styles.navLabel}>오더</Text></Pressable>
      <Pressable style={styles.navItem}><Text style={styles.navIcon}>▱</Text><Text style={styles.navLabel}>장바구니</Text></Pressable>
      <Pressable style={styles.navItem} onPress={() => setScreen('profile')}><Text style={[styles.navIcon, screen === 'profile' && styles.active]}>○</Text><Text style={[styles.navLabel, screen === 'profile' && styles.active]}>마이페이지</Text></Pressable>
    </View>
  );
}

const shadow = { shadowColor: '#000', shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 3 };

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F4F4F5' },
  page: { flex: 1, padding: 20, paddingBottom: 112, backgroundColor: '#F4F4F5' },
  header: { backgroundColor: '#FFFFFF', marginHorizontal: -20, marginTop: -20, paddingHorizontal: 20, paddingTop: 40, paddingBottom: 24 },
  hello: { color: '#18181B', fontSize: 26, fontWeight: '900', letterSpacing: -0.4 },
  yellow: { color: '#E09D00' },
  location: { color: '#71717A', fontSize: 14, marginTop: 8, fontWeight: '700' },
  orderCard: { backgroundColor: '#E09D00', borderRadius: 22, padding: 26, minHeight: 178, marginTop: 20, ...shadow },
  orderTitle: { color: '#FFFFFF', fontSize: 28, lineHeight: 36, fontWeight: '900' },
  orderSub: { color: 'rgba(255,255,255,0.84)', fontSize: 15, marginTop: 10, fontWeight: '700' },
  orderButton: { alignSelf: 'flex-start', backgroundColor: '#1E3826', paddingHorizontal: 19, paddingVertical: 11, borderRadius: 24, marginTop: 22 },
  orderButtonText: { color: '#FFFFFF', fontWeight: '900' },
  greenCard: { backgroundColor: '#1E3826', borderRadius: 22, padding: 22, minHeight: 205, marginTop: 18, ...shadow },
  badge: { alignSelf: 'flex-start', backgroundColor: 'rgba(224,157,0,0.2)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, marginBottom: 12 },
  badgeText: { color: '#E09D00', fontWeight: '900', fontSize: 12 },
  greenTitle: { color: '#FFFFFF', fontSize: 21, fontWeight: '900', marginBottom: 8 },
  greenBody: { color: '#D4D4D8', fontSize: 14, lineHeight: 22, fontWeight: '500' },
  yellowButton: { alignSelf: 'flex-start', backgroundColor: '#E09D00', paddingHorizontal: 18, paddingVertical: 12, borderRadius: 16, marginTop: 28 },
  yellowButtonText: { color: '#FFFFFF', fontWeight: '900' },
  title: { color: '#18181B', fontSize: 32, fontWeight: '900', marginTop: 24 },
  welcome: { color: '#18181B', fontSize: 28, lineHeight: 37, fontWeight: '900', textAlign: 'center', marginVertical: 28 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  mini: { width: '31.5%', height: 118, borderRadius: 24, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#F4F4F5', alignItems: 'center', justifyContent: 'center', marginBottom: 12, ...shadow },
  miniIcon: { color: '#E09D00', fontSize: 32, fontWeight: '900' },
  miniText: { color: '#18181B', textAlign: 'center', fontSize: 13, fontWeight: '900', marginTop: 10 },
  careRow: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: 'rgba(224,157,0,0.35)', borderRadius: 24, padding: 20, flexDirection: 'row', alignItems: 'center', gap: 14, ...shadow },
  careIcon: { width: 48, height: 48, borderRadius: 16, backgroundColor: 'rgba(224,157,0,0.10)', alignItems: 'center', justifyContent: 'center' },
  careIconText: { color: '#E09D00', fontSize: 24, fontWeight: '900' },
  careSub: { color: '#71717A', fontSize: 13, fontWeight: '700' },
  careTitle: { color: '#18181B', fontSize: 18, fontWeight: '900', marginTop: 3 },
  arrow: { color: '#A1A1AA', fontSize: 28 },
  nav: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 86, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#E5E7EB', flexDirection: 'row', justifyContent: 'space-around', paddingTop: 10 },
  navItem: { flex: 1, alignItems: 'center' },
  navIcon: { color: '#A1A1AA', fontSize: 28, fontWeight: '900' },
  navLabel: { color: '#71717A', fontSize: 12, fontWeight: '700', marginTop: 3 },
  active: { color: '#E09D00' },
});
