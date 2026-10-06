# Pumpkin Face Embedding Cloud Run Backend

This service completes the mobile app's Firebase-based face enrollment flow.

## Security boundary

- The mobile app sends a Firebase ID token.
- The service verifies the token and requires the URL UID, JSON UID, and token UID to match.
- It reads only the five fixed JPEG objects under
  `face-enrollment-temp/{uid}/`.
- It stores the generated embedding centroid under
  `users/{uid}.faceEmbedding` in Firestore.
- Temporary Storage objects and pose metadata are deleted only after the
  embedding is stored successfully.

Cloud Run must allow unauthenticated network invocation because the mobile app
does not have Google Cloud IAM credentials. Application access is still
authenticated by the Firebase ID token.

## Deploy from Windows PowerShell

Prerequisites:

1. Billing is enabled for the `pumpkin-63c92` Google Cloud project.
2. Install the Google Cloud CLI.
3. From the repository root, sign in once:

```powershell
gcloud auth login
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\face_backend\deploy.ps1
```

The script performs all project-side setup:

- enables Cloud Run, Cloud Build, Artifact Registry, and IAM APIs
- creates a dedicated runtime service account
- grants the runtime service account Firestore user and Storage object permissions
- builds the InsightFace image with the model baked in
- deploys with 2 CPU, 4 GiB memory, concurrency 1, and scale-to-zero
- reads the Cloud Run URL
- writes `EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL` to
  `apps/customer-mobile/.env`

After deployment, restart Expo so the public environment variable is bundled:

```powershell
cd apps\customer-mobile
npx expo start --tunnel --clear --port 8099
```

## Health check

```powershell
$Url = gcloud run services describe pumpkin-face-backend --region asia-northeast3 --format "value(status.url)"
Invoke-RestMethod "$Url/health"
```

The first real generation request may take longer while the process initializes
the CPU model. The model files are already inside the image, so it does not
download them at request time.
