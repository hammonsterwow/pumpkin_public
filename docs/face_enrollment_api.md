# Face Enrollment API Contract

This document defines the boundary between the customer mobile app and the Jetson backend.
The mobile team owns camera UI and guidance. The Jetson backend owns validation, pose/quality analysis, storage, embedding generation, and recognition.

## 1. Create customer

`POST /api/customers`

```json
{
  "name": "홍길동",
  "preferred_menu": "아메리카노",
  "preferred_temperature": "ICE",
  "preferred_quantity": 1
}
```

Use the returned `customer_id` for all following requests.

## 2. Send one enrollment frame

`POST /api/customers/{customer_id}/face-enrollment/frames`

```json
{
  "requested_pose": "front",
  "image_data": "data:image/jpeg;base64,..."
}
```

Allowed `requested_pose` values:

- `front`
- `left`
- `right`
- `up`
- `down`
- `unknown`

Phase 1 uses `requested_pose` as a temporary fallback until the real landmark/pose model is connected.
In Phase 2 the Jetson backend will detect the pose itself.

Example response:

```json
{
  "accepted": true,
  "detected_pose": "front",
  "quality": 0.91,
  "reason": "accepted_by_phase1_fallback",
  "face_count": 1,
  "next_pose": "left",
  "next_pose_label": "왼쪽",
  "complete": false,
  "status": {
    "customer_id": "customer_ab12cd34",
    "required_count": 5,
    "sample_count": 1,
    "complete": false,
    "embedding_ready": false
  }
}
```

The app should:

1. Show the camera preview.
2. Send a frame for the current guide pose.
3. Advance only when `accepted` is `true`.
4. Display `next_pose_label` as the next instruction.
5. Call finalize when `complete` becomes `true`.

## 3. Check progress

`GET /api/customers/{customer_id}/face-enrollment`

This may be used after app restart or network reconnection.

## 4. Finalize enrollment

`POST /api/customers/{customer_id}/face-enrollment/finalize`

Phase 1 returns `embedding_ready: false` because the embedding model is not connected yet.
Phase 2 will create and save customer embeddings without changing this endpoint.

## 5. Reset enrollment

`DELETE /api/customers/{customer_id}/face-enrollment`

Use this when the user cancels registration or wants to retry from the beginning.

## Current implementation boundary

Implemented now:

- customer existence check
- image data validation
- per-pose progress storage
- next-pose response
- completion state
- stable app-to-Jetson API contract

Next Jetson phases:

1. face detection and single-face validation
2. landmark-based yaw/pitch pose detection
3. blur, brightness, face-size and centering quality checks
4. aligned face crop generation
5. ArcFace/InsightFace embedding generation
6. embedding database and real-time recognition ROS node
