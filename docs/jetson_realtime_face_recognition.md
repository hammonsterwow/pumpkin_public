# Jetson real-time customer recognition

This feature reuses frames already captured by `vision_node`. It never opens a
second camera and it fails open: if the model or Firestore is unavailable, the
ordinary anonymous ordering flow continues.

## Runtime contract

1. `vision_node` detects a customer and immediately starts the existing greeting.
2. In parallel, `buffalo_l` runs every 0.4 seconds on the current webcam frame.
3. Firestore customer embeddings are cached locally and refreshed every 60 seconds.
4. One customer is confirmed only after three matching votes in the latest five
   recognition attempts. Inference stops after a stable match, or after five
   unmatched attempts for an anonymous customer, so CPU-only fallback cannot
   starve STT/NLU for the rest of the order.
5. After the greeting finishes, the robot asks:
   `율리님, 평소 드시던 아이스 아메리카노 한 잔으로 도와드릴까요?`
6. The personalized offer is represented as an ordinary `CONFIRM_ORDER` state,
   so an affirmative answer uses the existing order confirmation path.

## Required Jetson configuration

Use a dedicated Google service account with the minimum available read-only Firestore IAM role. Firestore server credentials bypass mobile security rules, and standard IAM roles are generally database-scoped rather than limited to the `users` collection. Keep its JSON key outside the repository.

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/secure/path/pumpkin-firestore-reader.json
export PUMPKIN_FIREBASE_PROJECT_ID=YOUR_FIREBASE_PROJECT_ID
export PUMPKIN_ENABLE_VISION=1
export PUMPKIN_ENABLE_FACE_RECOGNITION=1
```

The core Python environment needs InsightFace, Google Cloud Firestore, NumPy,
and a JetPack-compatible ONNX Runtime GPU build. Do not install the generic
`onnxruntime-gpu` PyPI wheel blindly on Jetson; select the wheel compatible
with the installed JetPack/CUDA version.

## Tuning

```bash
export PUMPKIN_FACE_THRESHOLD=0.45
export PUMPKIN_FACE_INTERVAL_SEC=0.4
export PUMPKIN_FACE_VOTE_WINDOW=5
export PUMPKIN_FACE_REQUIRED_VOTES=3
export PUMPKIN_FACE_MAX_ATTEMPTS=5
export PUMPKIN_FACE_CACHE_REFRESH_SEC=60
```

The threshold is only an initial value. Record genuine and impostor similarity
scores in the actual kiosk lighting and choose the operating threshold from that
data before production use.

## Validation topics

```bash
ros2 topic echo /face_recognition_result
ros2 topic echo /customer_context
ros2 topic echo /decision_result
```

Expected successful sequence:

```text
/human_presence: true
/face_recognition_result: matched=true, reason=stable_match
/customer_context: recognized=true
/decision_result: response_key=preferred_order_offer, decision=CONFIRM_ORDER
```
