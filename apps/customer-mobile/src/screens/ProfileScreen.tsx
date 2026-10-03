import React, { useState } from 'react';
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useAuth } from '../auth/AuthProvider';
import RegistrationStatusBadge from '../components/RegistrationStatusBadge';
import { MENU_DATA } from '../native/menuData';
import {
  CustomerTemperature,
  FaceEnrollmentStatus,
  getFaceRegistrationStatus,
} from '../types/faceProfile';

export default function ProfileScreen({
  enrollment,
  preferredMenuId,
  preferredTemperature,
  preferredQuantity,
  busy,
  error,
  onSelectPreferredMenu,
  onSelectPreferredTemperature,
  onChangePreferredQuantity,
  onSavePreferences,
  onRegisterFace,
  onDeleteFace,
}: {
  enrollment: FaceEnrollmentStatus | null;
  preferredMenuId: number | null;
  preferredTemperature: CustomerTemperature;
  preferredQuantity: number;
  busy: boolean;
  error: string;
  onSelectPreferredMenu: (menuId: number) => void;
  onSelectPreferredTemperature: (temperature: CustomerTemperature) => void;
  onChangePreferredQuantity: (quantity: number) => void;
  onSavePreferences: () => void;
  onRegisterFace: () => void;
  onDeleteFace: () => void;
}) {
  const { user, signOutUser } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const registrationStatus = getFaceRegistrationStatus(enrollment);
  const customerName = user?.displayName?.trim() || user?.email?.split('@')[0] || '고객';
  const avatarText = customerName.charAt(0);

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await signOutUser();
    } catch (signOutError) {
      Alert.alert(
        '로그아웃 실패',
        signOutError instanceof Error ? signOutError.message : '로그아웃 중 오류가 발생했습니다.',
      );
    } finally {
      setSigningOut(false);
    }
  };

  const selectedMenu = MENU_DATA.find((menu) => menu.id === preferredMenuId);
  const hotDisabled = Boolean(selectedMenu?.isIcedOnly);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.profileCard}>
        <View style={styles.avatar}><Text style={styles.avatarText}>{avatarText}</Text></View>
        <Text style={styles.name}>{customerName} 님</Text>
        <Text style={styles.uidDiagnostic}>Firebase UID: {user?.uid || '없음'}</Text>
        <RegistrationStatusBadge status={registrationStatus} />
        <Text style={styles.description}>앱에서 선호 메뉴·온도·수량과 얼굴을 등록하면 Jetson이 같은 고객 ID로 임베딩을 생성하고 단골 인식에 사용합니다.</Text>
        {enrollment ? (
          <Text style={styles.progress}>촬영 진행 {enrollment.sample_count}/{enrollment.required_count} · 임베딩 {enrollment.embedding_ready ? '준비됨' : '미준비'}</Text>
        ) : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.title}>단골 맞춤 서비스</Text>
        <Text style={styles.subtitle}>로봇이 단골 고객을 인식했을 때 추천할 평소 주문을 설정하세요.</Text>

        <Text style={styles.sectionLabel}>선호 메뉴</Text>
        <View style={styles.menuList}>
          {MENU_DATA.map((menu) => {
            const selected = preferredMenuId === menu.id;
            return (
              <Pressable key={menu.id} style={[styles.menu, selected && styles.menuSelected]} onPress={() => onSelectPreferredMenu(menu.id)} disabled={busy}>
                <Image source={{ uri: menu.image }} style={styles.menuImage} />
                <View style={styles.menuInfo}>
                  <Text style={styles.menuName}>{menu.name}</Text>
                  <Text style={styles.menuMeta}>{menu.engName} · {menu.price.toLocaleString('ko-KR')}원</Text>
                </View>
                <Text style={[styles.radio, selected && styles.radioSelected]}>{selected ? '●' : '○'}</Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.sectionLabel}>선호 온도</Text>
        <View style={styles.optionRow}>
          <Pressable
            style={[styles.option, preferredTemperature === 'ICE' && styles.optionSelected]}
            onPress={() => onSelectPreferredTemperature('ICE')}
            disabled={busy}
          >
            <Text style={[styles.optionText, preferredTemperature === 'ICE' && styles.optionTextSelected]}>ICE</Text>
          </Pressable>
          <Pressable
            style={[styles.option, preferredTemperature === 'HOT' && styles.optionSelected, hotDisabled && styles.optionDisabled]}
            onPress={() => onSelectPreferredTemperature('HOT')}
            disabled={busy || hotDisabled}
          >
            <Text style={[styles.optionText, preferredTemperature === 'HOT' && styles.optionTextSelected]}>HOT</Text>
          </Pressable>
        </View>
        {hotDisabled ? <Text style={styles.help}>선택한 메뉴는 ICE 전용입니다.</Text> : null}

        <Text style={styles.sectionLabel}>선호 수량</Text>
        <View style={styles.quantityRow}>
          <Pressable
            style={styles.quantityButton}
            onPress={() => onChangePreferredQuantity(Math.max(1, preferredQuantity - 1))}
            disabled={busy}
          >
            <Text style={styles.quantityButtonText}>−</Text>
          </Pressable>
          <Text style={styles.quantity}>{preferredQuantity}</Text>
          <Pressable
            style={styles.quantityButton}
            onPress={() => onChangePreferredQuantity(Math.min(20, preferredQuantity + 1))}
            disabled={busy}
          >
            <Text style={styles.quantityButtonText}>＋</Text>
          </Pressable>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {registrationStatus === 'REGISTERED' ? (
          <Pressable
            style={[styles.preferenceSave, busy && styles.disabled]}
            onPress={onSavePreferences}
            disabled={busy}
          >
            <Text style={styles.preferenceSaveText}>
              {busy ? '저장 중...' : '선호 주문 변경 저장'}
            </Text>
          </Pressable>
        ) : null}

        {registrationStatus === 'REGISTERED' ? null : (
          <Pressable style={[styles.primary, busy && styles.disabled]} onPress={onRegisterFace} disabled={busy}>
            <Text style={styles.primaryText}>{busy ? '서버 확인 중...' : registrationStatus === 'UNREGISTERED' ? '얼굴 등록 시작' : '얼굴 등록 이어하기'}</Text>
          </Pressable>
        )}
        {registrationStatus === 'UNREGISTERED' ? null : (
          <Pressable style={styles.delete} onPress={onDeleteFace} disabled={busy}><Text style={styles.deleteText}>얼굴 등록 데이터 초기화</Text></Pressable>
        )}
      </View>

      <Pressable
        style={[styles.logout, signingOut && styles.disabled]}
        onPress={() => void handleSignOut()}
        disabled={signingOut}
      >
        <Text style={styles.logoutText}>{signingOut ? '로그아웃 중...' : '로그아웃'}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4F4F5' },
  content: { padding: 20, paddingBottom: 120 },
  profileCard: { backgroundColor: '#1E3826', borderRadius: 28, padding: 24, alignItems: 'center' },
  avatar: { width: 76, height: 76, borderRadius: 38, backgroundColor: '#E09D00', alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: '#FFFFFF', fontSize: 30, fontWeight: '900' },
  name: { color: '#FFFFFF', fontSize: 23, fontWeight: '900', marginVertical: 12 },
  uidDiagnostic: { color: '#FDE68A', fontSize: 11, fontWeight: '800', marginBottom: 10, textAlign: 'center' },
  description: { color: '#D4D4D8', fontSize: 13, lineHeight: 20, textAlign: 'center', marginTop: 14 },
  progress: { color: '#FFFFFF', fontSize: 12, fontWeight: '800', marginTop: 12 },
  card: { backgroundColor: '#FFFFFF', borderRadius: 26, padding: 20, marginTop: 18 },
  title: { color: '#18181B', fontSize: 21, fontWeight: '900' },
  subtitle: { color: '#71717A', fontSize: 14, lineHeight: 21, marginTop: 8 },
  sectionLabel: { color: '#18181B', fontSize: 15, fontWeight: '900', marginTop: 22, marginBottom: 10 },
  menuList: { gap: 10 },
  menu: { flexDirection: 'row', alignItems: 'center', borderRadius: 18, padding: 12, backgroundColor: '#FAFAFA', borderWidth: 1, borderColor: '#E5E7EB' },
  menuSelected: { backgroundColor: '#FFF7E0', borderColor: '#E09D00' },
  menuImage: { width: 54, height: 54, borderRadius: 14, backgroundColor: '#E5E7EB' },
  menuInfo: { flex: 1, marginLeft: 12 },
  menuName: { color: '#18181B', fontSize: 15, fontWeight: '900' },
  menuMeta: { color: '#71717A', fontSize: 12, marginTop: 4 },
  radio: { color: '#A1A1AA', fontSize: 22 },
  radioSelected: { color: '#E09D00' },
  optionRow: { flexDirection: 'row', gap: 10 },
  option: { flex: 1, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FAFAFA', borderWidth: 1, borderColor: '#E5E7EB' },
  optionSelected: { backgroundColor: '#FFF7E0', borderColor: '#E09D00' },
  optionDisabled: { opacity: 0.35 },
  optionText: { color: '#71717A', fontSize: 15, fontWeight: '900' },
  optionTextSelected: { color: '#E09D00' },
  help: { color: '#71717A', fontSize: 12, marginTop: 8 },
  quantityRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 24 },
  quantityButton: { width: 46, height: 46, borderRadius: 16, backgroundColor: '#F4F4F5', alignItems: 'center', justifyContent: 'center' },
  quantityButtonText: { color: '#18181B', fontSize: 24, fontWeight: '900' },
  quantity: { minWidth: 40, textAlign: 'center', color: '#18181B', fontSize: 22, fontWeight: '900' },
  error: { color: '#B91C1C', fontSize: 13, lineHeight: 20, marginTop: 14 },
  preferenceSave: { height: 58, borderRadius: 18, backgroundColor: '#1E3826', alignItems: 'center', justifyContent: 'center', marginTop: 20 },
  preferenceSaveText: { color: '#FFFFFF', fontSize: 17, fontWeight: '900' },
  primary: { height: 58, borderRadius: 18, backgroundColor: '#E09D00', alignItems: 'center', justifyContent: 'center', marginTop: 20 },
  primaryText: { color: '#FFFFFF', fontSize: 17, fontWeight: '900' },
  delete: { height: 50, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  deleteText: { color: '#EF4444', fontSize: 14, fontWeight: '800' },
  logout: { height: 56, borderRadius: 18, borderWidth: 1, borderColor: '#D4D4D8', backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center', marginTop: 18 },
  logoutText: { color: '#52525B', fontSize: 16, fontWeight: '900' },
  disabled: { opacity: 0.55 },
});