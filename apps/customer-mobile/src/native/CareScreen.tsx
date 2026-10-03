import React, { useMemo, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { MENU_DATA } from './menuData';

const C = {
  bg: '#F4F4F5',
  white: '#FFFFFF',
  text: '#18181B',
  muted: '#71717A',
  icon: '#A1A1AA',
  line: '#E5E7EB',
  yellow: '#E09D00',
  green: '#1E3826',
  disabled: '#D4D4D8',
};

const STEPS = ['정면을 프레임에 맞춰주세요', '왼쪽 각도를 맞춰주세요', '오른쪽 각도를 맞춰주세요'];

type Props = {
  onBack: () => void;
  onDone: () => void;
};

export default function CareScreen({ onBack, onDone }: Props) {
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<string[]>([MENU_DATA[1]?.id].filter(Boolean) as string[]);
  const progress = useMemo(() => Math.round(((step + 1) / STEPS.length) * 100), [step]);
  const completed = step === STEPS.length - 1;
  const canStart = completed && selected.length > 0;

  const toggle = (id: string) => setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Pressable style={styles.backButton} onPress={onBack}><Text style={styles.backIcon}>‹</Text></Pressable>
        <View style={styles.headerCenter}>
          <Text style={styles.kicker}>REGULAR CARE</Text>
          <Text style={styles.headerTitle}>단골 맞춤 서비스 등록</Text>
        </View>
        <View style={styles.shield}><Text style={styles.shieldText}>♢</Text></View>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <View style={styles.heroGlow} />
          <View style={styles.heroTop}>
            <View style={styles.badge}><Text style={styles.badgeText}>✧ 매장 인식 맞춤 혜택</Text></View>
            <View style={styles.scanCircle}><Text style={styles.scanText}>⌗</Text></View>
          </View>
          <Text style={styles.heroTitle}>입장하면 바로 알아보는{`\n`}나만의 커피 취향</Text>
          <Text style={styles.heroBody}>즐겨찾기 메뉴를 고르면 매장에서{`\n`}단골 응대와 추천 주문이 더 빨라집니다.</Text>
        </View>

        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View><Text style={styles.stepLabel}>STEP 1</Text><Text style={styles.cardTitle}>인식 정보 설정</Text></View>
            <Text style={styles.percent}>{progress}%</Text>
          </View>
          <View style={styles.blackBox}>
            <View style={styles.notch} />
            <View style={styles.ringOuter}>
              <View style={[styles.ringProgress, step >= 1 && styles.ringHalf, completed && styles.ringFull]} />
              <View style={styles.ringInner}><Text style={styles.ringIcon}>{completed ? '✓' : '⌗'}</Text></View>
            </View>
            <Text style={styles.guide}>{STEPS[step]}</Text>
            <Text style={styles.guideSub}>매장 맞춤 응대에만 사용됩니다</Text>
          </View>
          <View style={styles.progressRow}>{STEPS.map((_, i) => <View key={i} style={[styles.bar, i <= step && styles.barActive]} />)}</View>
          <View style={styles.actionRow}>
            <Pressable style={styles.reset} onPress={() => setStep(0)}><Text style={styles.resetText}>↻</Text></Pressable>
            <Pressable disabled={completed} style={[styles.next, completed && styles.nextDone]} onPress={() => setStep((x) => Math.min(STEPS.length - 1, x + 1))}>
              <Text style={styles.nextText}>{completed ? '설정 완료' : '다음 각도 스캔'}</Text>
            </Pressable>
          </View>
        </View>

        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View><Text style={styles.stepLabel}>STEP 2</Text><Text style={styles.cardTitle}>즐겨찾기 메뉴 선택</Text></View>
            <Text style={styles.selectedCount}>{selected.length}개 선택</Text>
          </View>
          <View style={styles.menuList}>
            {MENU_DATA.map((item) => {
              const active = selected.includes(item.id);
              return (
                <Pressable key={item.id} style={[styles.favorite, active && styles.favoriteActive]} onPress={() => toggle(item.id)}>
                  <Image source={{ uri: item.image }} style={styles.favoriteImage} />
                  <View style={styles.favoriteInfo}>
                    <Text style={styles.favoriteName}>{item.name}</Text>
                    <Text style={styles.favoriteEng}>{item.engName}</Text>
                    <Text style={styles.favoritePrice}>{item.price.toLocaleString('ko-KR')}원</Text>
                  </View>
                  <View style={[styles.check, active && styles.checkActive]}><Text style={[styles.checkText, active && styles.checkTextActive]}>{active ? '✓' : '♡'}</Text></View>
                </Pressable>
              );
            })}
          </View>
        </View>
      </ScrollView>

      <View style={styles.fixedBottom}>
        <Pressable disabled={!canStart} style={[styles.start, !canStart && styles.startDisabled]} onPress={onDone}>
          <Text style={[styles.startText, !canStart && styles.startTextDisabled]}>☕  단골 맞춤 서비스 시작하기</Text>
        </Pressable>
      </View>
    </View>
  );
}

const shadow = { shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 10, elevation: 3 };

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  header: { backgroundColor: 'rgba(244,244,245,0.96)', borderBottomWidth: 1, borderBottomColor: C.line, paddingHorizontal: 20, paddingTop: 18, paddingBottom: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  backButton: { width: 48, height: 48, borderRadius: 24, backgroundColor: C.white, borderWidth: 1, borderColor: C.line, alignItems: 'center', justifyContent: 'center' },
  backIcon: { color: C.text, fontSize: 38, lineHeight: 42, marginTop: -4 },
  headerCenter: { alignItems: 'center' },
  kicker: { color: C.yellow, fontSize: 13, letterSpacing: 5, fontWeight: '900' },
  headerTitle: { color: C.text, fontSize: 20, fontWeight: '900', marginTop: 6 },
  shield: { width: 48, height: 48, borderRadius: 24, backgroundColor: C.green, alignItems: 'center', justifyContent: 'center' },
  shieldText: { color: C.white, fontSize: 25 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 190 },
  hero: { backgroundColor: C.green, borderRadius: 32, padding: 24, minHeight: 242, overflow: 'hidden', ...shadow },
  heroGlow: { position: 'absolute', right: -40, top: -50, width: 170, height: 170, borderRadius: 85, backgroundColor: 'rgba(224,157,0,0.25)' },
  heroTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  badge: { backgroundColor: 'rgba(255,255,255,0.10)', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 7 },
  badgeText: { color: C.yellow, fontSize: 13, fontWeight: '900' },
  scanCircle: { width: 64, height: 64, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.12)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)', alignItems: 'center', justifyContent: 'center' },
  scanText: { color: C.yellow, fontSize: 32, fontWeight: '900' },
  heroTitle: { color: C.white, fontSize: 29, lineHeight: 39, fontWeight: '900', marginTop: 26, letterSpacing: -0.5 },
  heroBody: { color: 'rgba(255,255,255,0.68)', fontSize: 16, lineHeight: 26, fontWeight: '700', marginTop: 16 },
  card: { backgroundColor: C.white, borderRadius: 30, padding: 24, marginTop: 26, borderWidth: 1, borderColor: '#F1F1F1', ...shadow },
  cardHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 },
  stepLabel: { color: C.icon, fontSize: 15, fontWeight: '900', marginBottom: 6 },
  cardTitle: { color: C.text, fontSize: 22, fontWeight: '900', letterSpacing: -0.4 },
  percent: { color: C.yellow, fontSize: 18, fontWeight: '900' },
  blackBox: { height: 316, borderRadius: 30, backgroundColor: '#000', borderWidth: 6, borderColor: '#18181B', overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  notch: { position: 'absolute', top: 16, width: 112, height: 24, borderRadius: 14, backgroundColor: '#09090B' },
  ringOuter: { width: 148, height: 148, borderRadius: 74, backgroundColor: '#3F3F46', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  ringProgress: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 50, backgroundColor: C.yellow },
  ringHalf: { width: 86 },
  ringFull: { width: 148, backgroundColor: '#34D399' },
  ringInner: { width: 112, height: 112, borderRadius: 56, backgroundColor: '#18181B', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#27272A' },
  ringIcon: { color: C.white, fontSize: 50, fontWeight: '900' },
  guide: { color: C.white, fontSize: 17, fontWeight: '900', marginTop: 24 },
  guideSub: { color: 'rgba(255,255,255,0.42)', fontSize: 13, fontWeight: '700', marginTop: 12 },
  progressRow: { flexDirection: 'row', gap: 10, marginTop: 20 },
  bar: { flex: 1, height: 6, borderRadius: 6, backgroundColor: C.line },
  barActive: { backgroundColor: C.yellow },
  actionRow: { flexDirection: 'row', gap: 14, marginTop: 20 },
  reset: { width: 58, height: 58, borderRadius: 18, backgroundColor: C.bg, alignItems: 'center', justifyContent: 'center' },
  resetText: { color: C.text, fontSize: 28, fontWeight: '900' },
  next: { flex: 1, height: 58, borderRadius: 18, backgroundColor: C.yellow, alignItems: 'center', justifyContent: 'center' },
  nextDone: { backgroundColor: '#34D399' },
  nextText: { color: C.white, fontSize: 18, fontWeight: '900' },
  selectedCount: { color: C.green, fontSize: 14, fontWeight: '900', marginTop: 26 },
  menuList: { gap: 14 },
  favorite: { backgroundColor: '#FAFAFA', borderWidth: 1, borderColor: '#EFEFEF', borderRadius: 20, padding: 14, flexDirection: 'row', alignItems: 'center' },
  favoriteActive: { backgroundColor: '#FFF7E8', borderColor: C.yellow },
  favoriteImage: { width: 72, height: 72, borderRadius: 16, backgroundColor: C.line },
  favoriteInfo: { flex: 1, marginLeft: 14 },
  favoriteName: { color: C.text, fontSize: 17, fontWeight: '900' },
  favoriteEng: { color: C.muted, fontSize: 14, fontWeight: '700', marginTop: 4 },
  favoritePrice: { color: C.text, fontSize: 15, fontWeight: '900', marginTop: 6 },
  check: { width: 46, height: 46, borderRadius: 23, backgroundColor: C.white, borderWidth: 1, borderColor: C.line, alignItems: 'center', justifyContent: 'center' },
  checkActive: { backgroundColor: C.yellow, borderColor: C.yellow },
  checkText: { color: C.icon, fontSize: 28, fontWeight: '700' },
  checkTextActive: { color: C.white, fontSize: 28 },
  fixedBottom: { position: 'absolute', left: 0, right: 0, bottom: 86, paddingHorizontal: 20, paddingBottom: 18 },
  start: { height: 58, borderRadius: 18, backgroundColor: C.yellow, alignItems: 'center', justifyContent: 'center' },
  startDisabled: { backgroundColor: C.disabled },
  startText: { color: C.white, fontSize: 17, fontWeight: '900' },
  startTextDisabled: { color: C.muted },
});
