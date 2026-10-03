import { fetch } from 'expo/fetch';
import { File } from 'expo-file-system';
import { collection, doc, getDoc, getDocs, serverTimestamp, setDoc, updateDoc } from 'firebase/firestore';
import { deleteObject, ref } from 'firebase/storage';

import { auth, firestore, storage } from './config';

export type StoredFacePose = 'front' | 'left' | 'right' | 'up' | 'down';
export const STORED_FACE_POSES: StoredFacePose[] = ['front', 'left', 'right', 'up', 'down'];

export type FaceEnrollmentPreferencePayload = {
  uid: string;
  name: string;
  preferredMenu: string;
  preferredTemperature: 'HOT' | 'ICE' | 'NONE';
  preferredQuantity: number;
};

async function uploadFileToStorage(
  storagePath: string,
  fileUri: string,
): Promise<void> {
  const user = auth.currentUser;
  if (!user) {
    throw new Error('사진을 저장하려면 다시 로그인해주세요.');
  }

  const bucket = storage.app.options.storageBucket;
  if (!bucket) {
    throw new Error('Firebase Storage 설정을 찾지 못했습니다.');
  }

  const token = await user.getIdToken();
  const uploadUrl =
    `https://firebasestorage.googleapis.com/v0/b/${encodeURIComponent(bucket)}/o`
    + `?uploadType=media&name=${encodeURIComponent(storagePath)}`;
  const file = new File(fileUri);

  if (!file.exists) {
    throw new Error('촬영한 사진 파일을 찾지 못했습니다.');
  }

  const response = await fetch(uploadUrl, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': file.type || 'image/jpeg',
    },
    body: file,
  });

  if (!response.ok) {
    const responseText = await response.text();
    throw new Error(
      `사진 저장에 실패했습니다. (HTTP ${response.status})`
      + (responseText ? ` ${responseText}` : ''),
    );
  }
}

export async function saveUserPreferences(
  payload: FaceEnrollmentPreferencePayload,
): Promise<void> {
  await setDoc(
    doc(firestore, 'users', payload.uid),
    {
      uid: payload.uid,
      name: payload.name,
      preferredMenu: payload.preferredMenu,
      preferredTemperature: payload.preferredTemperature,
      preferredQuantity: payload.preferredQuantity,
      updatedAt: serverTimestamp(),
    },
    { merge: true },
  );
}

export async function saveFaceEnrollmentPreferences(
  payload: FaceEnrollmentPreferencePayload,
): Promise<void> {
  await setDoc(
    doc(firestore, 'users', payload.uid),
    {
      uid: payload.uid,
      name: payload.name,
      preferredMenu: payload.preferredMenu,
      preferredTemperature: payload.preferredTemperature,
      preferredQuantity: payload.preferredQuantity,
      faceEnrollmentStatus: 'capturing',
      updatedAt: serverTimestamp(),
    },
    { merge: true },
  );
}

export async function uploadTemporaryFaceFrame(
  uid: string,
  pose: StoredFacePose,
  fileUri: string,
): Promise<void> {
  if (!fileUri) {
    throw new Error('촬영 이미지의 파일 경로가 없습니다.');
  }

  const storagePath = `face-enrollment-temp/${uid}/${pose}.jpg`;
  await uploadFileToStorage(storagePath, fileUri);

  await setDoc(
    doc(firestore, 'users', uid, 'faceEnrollment', pose),
    {
      pose,
      storagePath,
      uploadedAt: serverTimestamp(),
    },
    { merge: true },
  );
}

export async function markFaceEnrollmentProcessing(uid: string): Promise<void> {
  await updateDoc(doc(firestore, 'users', uid), {
    faceEnrollmentStatus: 'processing',
    updatedAt: serverTimestamp(),
  });
}

export async function saveFaceEmbeddingResult(
  uid: string,
  result: { model: string; dimension: number; centroid: number[] },
): Promise<void> {
  await setDoc(
    doc(firestore, 'users', uid),
    {
      faceRegistered: true,
      faceEnrollmentStatus: 'registered',
      faceEmbedding: {
        model: result.model,
        dimension: result.dimension,
        centroid: result.centroid,
        updatedAt: serverTimestamp(),
      },
      updatedAt: serverTimestamp(),
    },
    { merge: true },
  );
}

export async function deleteTemporaryFaceFrames(uid: string): Promise<void> {
  await Promise.all(
    STORED_FACE_POSES.map(async (pose) => {
      const storageRef = ref(storage, `face-enrollment-temp/${uid}/${pose}.jpg`);
      try {
        await deleteObject(storageRef);
      } catch (error: any) {
        if (error?.code !== 'storage/object-not-found') throw error;
      }
    }),
  );
}

export async function resetFirebaseFaceEnrollment(uid: string): Promise<void> {
  await deleteTemporaryFaceFrames(uid);
  await setDoc(
    doc(firestore, 'users', uid),
    {
      faceRegistered: false,
      faceEnrollmentStatus: 'not_started',
      faceEmbedding: null,
      updatedAt: serverTimestamp(),
    },
    { merge: true },
  );
}

export async function getStoredUserProfile(
  uid: string,
): Promise<Record<string, unknown> | null> {
  const snapshot = await getDoc(doc(firestore, 'users', uid));
  return snapshot.exists() ? snapshot.data() : null;
}

export async function getStoredFaceEnrollmentPoses(
  uid: string,
): Promise<StoredFacePose[]> {
  const snapshot = await getDocs(collection(firestore, 'users', uid, 'faceEnrollment'));
  return snapshot.docs
    .map((poseDoc) => poseDoc.id)
    .filter((pose): pose is StoredFacePose => STORED_FACE_POSES.includes(pose as StoredFacePose));
}
