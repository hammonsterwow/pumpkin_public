$ErrorActionPreference = "Stop"

$ProjectId = "pumpkin-63c92"
$FirebaseCliVersion = "latest"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$CliRoot = Join-Path $env:LOCALAPPDATA "pumpkin-firebase-cli"
$FirebaseCmd = Join-Path $CliRoot "node_modules\.bin\firebase.cmd"
Set-Location $RepoRoot

function Invoke-NativeCommand {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments,
    [switch]$CaptureOutput
  )

  $PreviousErrorActionPreference = $ErrorActionPreference
  try {
    # Windows PowerShell turns native stderr warnings into error records.
    # The native process exit code is the source of truth.
    $ErrorActionPreference = "Continue"

    if ($CaptureOutput) {
      $Output = & $Command @Arguments 2>&1
      $ExitCode = $LASTEXITCODE
      $Output | ForEach-Object { Write-Host $_ }
      return [PSCustomObject]@{
        Output = @($Output)
        ExitCode = $ExitCode
      }
    }

    & $Command @Arguments
    return [PSCustomObject]@{
      Output = @()
      ExitCode = $LASTEXITCODE
    }
  }
  finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
  }
}

# Do not use npx here. A partially populated npx cache can omit transitive
# dependencies and make Firebase CLI fail before it starts.
if (-not (Test-Path $FirebaseCmd)) {
  Write-Host "Installing an isolated Firebase CLI..."
  New-Item -ItemType Directory -Force -Path $CliRoot | Out-Null
  $InstallResult = Invoke-NativeCommand -Command "npm.cmd" -Arguments @(
    "install",
    "--prefix", $CliRoot,
    "--no-audit",
    "--no-fund",
    "firebase-tools@$FirebaseCliVersion",
    "@colors/colors@1.6.0"
  )
  if ($InstallResult.ExitCode -ne 0 -or -not (Test-Path $FirebaseCmd)) {
    throw "Firebase CLI installation failed with exit code $($InstallResult.ExitCode)."
  }
}

Write-Host "Checking Firebase CLI login..."
$LoginResult = Invoke-NativeCommand -Command $FirebaseCmd -Arguments @("login:list") -CaptureOutput
$HasNoAuthorizedAccount = (($LoginResult.Output -join "`n") -match "No authorized accounts")

if ($LoginResult.ExitCode -ne 0 -or $HasNoAuthorizedAccount) {
  Write-Host "Firebase login is required. Complete the browser sign-in with the account that owns $ProjectId."
  $FirebaseLoginResult = Invoke-NativeCommand -Command $FirebaseCmd -Arguments @("login")
  if ($FirebaseLoginResult.ExitCode -ne 0) {
    throw "Firebase login failed with exit code $($FirebaseLoginResult.ExitCode)."
  }
}

Write-Host "Deploying Firestore rules to $ProjectId..."
$DeployResult = Invoke-NativeCommand -Command $FirebaseCmd -Arguments @(
  "deploy",
  "--only", "firestore:rules",
  "--project", $ProjectId
)
if ($DeployResult.ExitCode -ne 0) {
  throw "Firestore rules deployment failed with exit code $($DeployResult.ExitCode)."
}

Write-Host "Firestore rules deployed successfully."
