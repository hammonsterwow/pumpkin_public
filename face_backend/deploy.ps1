param(
  [string]$ProjectId = "pumpkin-63c92",
  [string]$Region = "asia-northeast3",
  [string]$StorageBucket = "pumpkin-63c92.firebasestorage.app",
  [string]$ServiceName = "pumpkin-face-backend",
  [string]$Repository = "pumpkin"
)

$ErrorActionPreference = "Stop"
$ServiceAccountName = "pumpkin-face-backend"
$ServiceAccount = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/${ServiceName}:latest"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
  throw "Google Cloud CLI(gcloud)가 설치되어 있지 않습니다. https://cloud.google.com/sdk/docs/install 에서 설치한 뒤 다시 실행해주세요."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

gcloud config set project $ProjectId
if ($LASTEXITCODE -ne 0) { throw "Google Cloud 프로젝트 설정에 실패했습니다." }

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com iam.googleapis.com
if ($LASTEXITCODE -ne 0) { throw "필요한 Google Cloud API 활성화에 실패했습니다." }

# A missing repository is an expected first-deploy state. PowerShell 5.1 can
# promote gcloud's NOT_FOUND stderr to a terminating error when
# $ErrorActionPreference is Stop, so probe it with native errors temporarily
# non-terminating and inspect the process exit code explicitly.
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$ArtifactRepositoryProbe = gcloud artifacts repositories describe $Repository --location $Region --project $ProjectId --format "value(name)" 2>&1
$ArtifactRepositoryExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $PreviousErrorActionPreference

if (-not $ArtifactRepositoryExists) {
  gcloud artifacts repositories create $Repository --repository-format docker --location $Region --project $ProjectId --quiet
  if ($LASTEXITCODE -ne 0) { throw "Artifact Registry 저장소 생성에 실패했습니다." }

  # Verify creation before Cloud Build so the push cannot race repository
  # propagation or continue with a missing destination.
  gcloud artifacts repositories describe $Repository --location $Region --project $ProjectId --format "value(name)"
  if ($LASTEXITCODE -ne 0) { throw "Artifact Registry 저장소 생성 확인에 실패했습니다." }
}

$ExistingServiceAccount = gcloud iam service-accounts list --project $ProjectId --filter "email:$ServiceAccount" --format "value(email)"
if ($LASTEXITCODE -ne 0) { throw "서비스 계정 조회에 실패했습니다." }
if (-not $ExistingServiceAccount) {
  gcloud iam service-accounts create $ServiceAccountName --display-name "Pumpkin face backend" --project $ProjectId
  if ($LASTEXITCODE -ne 0) { throw "서비스 계정 생성에 실패했습니다." }
}

gcloud projects add-iam-policy-binding $ProjectId --member "serviceAccount:$ServiceAccount" --role "roles/datastore.user" --condition None
if ($LASTEXITCODE -ne 0) { throw "Firestore 권한 부여에 실패했습니다." }

gcloud projects add-iam-policy-binding $ProjectId --member "serviceAccount:$ServiceAccount" --role "roles/storage.objectAdmin" --condition None
if ($LASTEXITCODE -ne 0) { throw "Storage 권한 부여에 실패했습니다." }

gcloud builds submit --project $ProjectId --region $Region --config face_backend/cloudbuild.yaml --substitutions "_IMAGE=$Image" .
if ($LASTEXITCODE -ne 0) { throw "Cloud Build가 실패했습니다. 위 빌드 로그의 첫 오류를 확인해주세요." }

gcloud run deploy $ServiceName --project $ProjectId --region $Region --image $Image --service-account $ServiceAccount --set-env-vars "FIREBASE_STORAGE_BUCKET=$StorageBucket,PUMPKIN_FACE_MODEL=buffalo_l" --cpu 2 --memory 4Gi --concurrency 1 --timeout 900 --min 0 --max 2 --allow-unauthenticated --quiet
if ($LASTEXITCODE -ne 0) { throw "Cloud Run 배포에 실패했습니다." }

$ServiceUrl = gcloud run services describe $ServiceName --project $ProjectId --region $Region --format "value(status.url)"
if ($LASTEXITCODE -ne 0 -or -not $ServiceUrl) { throw "Cloud Run 주소를 읽지 못했습니다." }

$EnvPath = Join-Path $RepoRoot "apps/customer-mobile/.env"
$EnvLine = "EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL=$ServiceUrl"
if (Test-Path $EnvPath) {
  $EnvText = Get-Content $EnvPath -Raw
  if ($EnvText -match "(?m)^EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL=.*$") {
    $EnvText = [regex]::Replace($EnvText, "(?m)^EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL=.*$", $EnvLine)
  } else {
    $EnvText = $EnvText.TrimEnd() + [Environment]::NewLine + $EnvLine + [Environment]::NewLine
  }
  Set-Content -Path $EnvPath -Value $EnvText -Encoding utf8
} else {
  Set-Content -Path $EnvPath -Value ($EnvLine + [Environment]::NewLine) -Encoding utf8
}

Write-Host ""
Write-Host "배포 완료: $ServiceUrl" -ForegroundColor Green
Write-Host "앱 .env에 얼굴 백엔드 주소를 자동으로 저장했습니다." -ForegroundColor Green
Write-Host "이제 Expo를 Ctrl+C로 종료한 뒤 npx expo start --tunnel --clear --port 8099 로 다시 실행하세요."
