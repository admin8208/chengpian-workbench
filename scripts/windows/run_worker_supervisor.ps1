param(
  [string]$RootDir = "",
  [string]$LogOut = "",
  [string]$LogErr = "",
  [int]$RestartDelaySeconds = 3
)

$ErrorActionPreference = "Stop"

if (-not $RootDir) {
  $RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$ApiDir = Join-Path $RootDir "apps\api"
$Python = Join-Path $ApiDir ".venv-win\Scripts\python.exe"
$DataDir = if ($env:CHENGPIAN_DATA_DIR) { $env:CHENGPIAN_DATA_DIR } else { (Join-Path $RootDir "data") }
$LogsDir = Join-Path $DataDir "logs\worker-supervisor"

if (-not (Test-Path -LiteralPath $Python)) {
  throw "Missing Windows API virtualenv: $Python. Run scripts\build\windows\setup_api_venv.ps1 first."
}

if (-not (Test-Path -LiteralPath $LogsDir)) {
  New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

if (-not $LogOut) {
  $LogOut = Join-Path $LogsDir "worker.out.log"
}
if (-not $LogErr) {
  $LogErr = Join-Path $LogsDir "worker.err.log"
}

$env:CHENGPIAN_DATA_DIR = $DataDir
$env:CHENGPIAN_WEB_DIST_DIR = if ($env:CHENGPIAN_WEB_DIST_DIR) { $env:CHENGPIAN_WEB_DIST_DIR } else { (Join-Path $RootDir "apps\web\dist") }

Set-Location $ApiDir

while ($true) {
  $startedAt = Get-Date
  Add-Content -LiteralPath $LogOut -Value ("[{0}] worker supervisor starting run_worker.py" -f $startedAt.ToString("s"))
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $Python run_worker.py >> $LogOut 2>> $LogErr
    $exitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }
  $endedAt = Get-Date
  Add-Content -LiteralPath $LogErr -Value ("[{0}] worker exited with code {1}" -f $endedAt.ToString("s"), $exitCode)
  Start-Sleep -Seconds ([Math]::Max(1, $RestartDelaySeconds))
}
