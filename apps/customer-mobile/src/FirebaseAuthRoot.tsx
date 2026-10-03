import React from 'react';
import { ActivityIndicator, SafeAreaView, StyleSheet, Text, View } from 'react-native';

import CustomerMobileApp from './CustomerMobileApp';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import AuthScreen from './screens/AuthScreen';

function AuthenticatedRoot() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#E09D00" />
          <Text style={styles.loadingText}>로그인 상태를 확인하는 중입니다.</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!user) return <AuthScreen />;

  const customerName =
    user.displayName?.trim()
    || user.email?.split('@')[0]
    || '고객';

  return (
    <CustomerMobileApp
      customerId={user.uid}
      customerName={customerName}
    />
  );
}

export default function FirebaseAuthRoot() {
  return (
    <AuthProvider>
      <AuthenticatedRoot />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F4F4F5' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  loadingText: { color: '#71717A', marginTop: 14, fontWeight: '700' },
});
