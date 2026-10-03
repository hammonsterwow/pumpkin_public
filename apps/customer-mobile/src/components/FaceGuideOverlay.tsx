import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { FacePose } from '../types/faceProfile';

const GUIDES: Record<FacePose, { title: string; body: string }> = {
  front: { title: '정면을 바라봐 주세요', body: '얼굴 전체가 원 안에 들어오도록 맞춰주세요.' },
  left: { title: '얼굴을 왼쪽으로 돌려주세요', body: '고개만 살짝 돌리고 시선은 자연스럽게 유지해주세요.' },
  right: { title: '얼굴을 오른쪽으로 돌려주세요', body: '빛이 얼굴 한쪽에만 강하게 닿지 않도록 해주세요.' },
  up: { title: '얼굴을 위쪽으로 들어주세요', body: '턱을 살짝 올리고 얼굴이 프레임을 벗어나지 않게 해주세요.' },
  down: { title: '얼굴을 아래쪽으로 내려주세요', body: '턱을 살짝 내리고 눈과 얼굴 윤곽이 보이도록 해주세요.' },
};

export default function FaceGuideOverlay({ pose, accepted }: { pose: FacePose; accepted: boolean }) {
  const guide = GUIDES[pose];

  return (
    <View style={styles.frame}>
      <View style={[styles.oval, accepted && styles.completed]}>
        <Text style={styles.icon}>{accepted ? '✓' : '⌗'}</Text>
      </View>
      <Text style={styles.title}>{guide.title}</Text>
      <Text style={styles.body}>{accepted ? '서버가 이 프레임을 승인했습니다.' : guide.body}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { minHeight: 300, borderRadius: 28, backgroundColor: '#09090B', alignItems: 'center', justifyContent: 'center', padding: 24 },
  oval: { width: 148, height: 190, borderRadius: 74, borderWidth: 5, borderColor: '#E09D00', alignItems: 'center', justifyContent: 'center' },
  completed: { borderColor: '#34D399' },
  icon: { color: '#FFFFFF', fontSize: 48, fontWeight: '900' },
  title: { color: '#FFFFFF', fontSize: 18, fontWeight: '900', marginTop: 24 },
  body: { color: '#A1A1AA', fontSize: 14, lineHeight: 21, textAlign: 'center', marginTop: 10 },
});
