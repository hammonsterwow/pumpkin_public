param(
  [int]$Port = 8099,
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$AppDir = Join-Path $RepoRoot "apps\customer-mobile"
$EnvExample = Join-Path $AppDir ".env.example"
$EnvFile = Join-Path $AppDir ".env"

function Get-Executable {
  param([string[]]$Names)

  foreach ($Name in $Names) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $Command) {
      return $Command.Source
    }
  }

  throw "필수 명령을 찾지 못했습니다: $($Names -join ', '). Node.js LTS를 먼저 설치해 주세요."
}

function Get-ConfigLine {
  param(
    [string[]]$Lines,
    [string]$Key
  )

  $Pattern = "^$([Regex]::Escape($Key))="
  return $Lines | Where-Object { $_ -match $Pattern } | Select-Object -Last 1
}

if (-not (Test-Path $AppDir)) {
  throw "고객 앱 폴더를 찾지 못했습니다: $AppDir"
}

if (-not (Test-Path $EnvExample)) {
  throw "기본 설정 파일을 찾지 못했습니다: $EnvExample"
}

$Npm = Get-Executable @("npm.cmd", "npm")
$Npx = Get-Executable @("npx.cmd", "npx")

$RequiredKeys = @(
  "EXPO_PUBLIC_API_BASE_URL",
  "EXPO_PUBLIC_FACE_EMBEDDING_API_BASE_URL",
  "EXPO_PUBLIC_FIREBASE_API_KEY",
  "EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN",
  "EXPO_PUBLIC_FIREBASE_PROJECT_ID",
  "EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET",
  "EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID",
  "EXPO_PUBLIC_FIREBASE_APP_ID"
)

$ExampleLines = @(Get-Content $EnvExample)
if (Test-Path $EnvFile) {
  $EnvLines = @(Get-Content $EnvFile)
} else {
  $EnvLines = @()
}

# Keep unrelated local variables, remove the obsolete standalone-face demo flag,
# and replace each public key with the repository's current client configuration.
$EnvLines = @($EnvLines | Where-Object {
  $_ -notmatch "^\s*EXPO_PUBLIC_FACE_ENROLLMENT_DEMO\s*="
})

foreach ($Key in $RequiredKeys) {
  $ExampleLine = Get-ConfigLine -Lines $ExampleLines -Key $Key
  if ([string]::IsNullOrWhiteSpace($ExampleLine)) {
    throw ".env.example에 $Key 값이 없습니다."
  }

  $Value = $ExampleLine.Substring($Key.Length + 1).Trim()
  if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match "replace-me|your-|example") {
    throw ".env.example의 $Key 값이 완성되지 않았습니다."
  }

  $Pattern = "^$([Regex]::Escape($Key))="
  $EnvLines = @($EnvLines | Where-Object { $_ -notmatch $Pattern })
  $EnvLines += $ExampleLine
}

$EnvLines | Set-Content -Encoding UTF8 $EnvFile
Write-Host "[OK] 검증된 Firebase/Cloud Run 공개 설정을 .env에 적용했습니다." -ForegroundColor Green

Push-Location $AppDir
try {
  if (-not $SkipInstall) {
    Write-Host "[START] 고객 앱 의존성을 확인합니다..." -ForegroundColor Cyan
    & $Npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) {
      throw "npm install이 실패했습니다. exit=$LASTEXITCODE"
    }
  }

  Write-Host ""
  Write-Host "============================================================" -ForegroundColor DarkGreen
  Write-Host " Pumpkin Firebase Customer App" -ForegroundColor Green
  Write-Host " mode   : full app (Firebase Auth / Firestore / Storage)" -ForegroundColor Green
  Write-Host " tunnel : Expo Go QR" -ForegroundColor Green
  Write-Host " port   : $Port" -ForegroundColor Green
  Write-Host "============================================================" -ForegroundColor DarkGreen
  Write-Host ""
  Write-Host "[START] 'Tunnel ready' 아래 QR을 iPhone 카메라로 찍어 주세요." -ForegroundColor Cyan

  & $Npx expo start --tunnel --clear --port $Port
  if ($LASTEXITCODE -ne 0) {
    throw "Expo 실행이 실패했습니다. exit=$LASTEXITCODE"
  }
}
finally {
  Pop-Location
}
