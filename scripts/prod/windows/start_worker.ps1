$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ApiDir = Join-Path $RootDir "apps\api"
$Python = Join-Path $ApiDir ".venv-win\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "Missing Windows API virtualenv: $Python. Run scripts\\build\\windows\\setup_api_venv.ps1 first."
}

$env:CHENGPIAN_DATA_DIR = if ($env:CHENGPIAN_DATA_DIR) { $env:CHENGPIAN_DATA_DIR } else { (Join-Path $RootDir "data") }
$env:CHENGPIAN_WEB_DIST_DIR = if ($env:CHENGPIAN_WEB_DIST_DIR) { $env:CHENGPIAN_WEB_DIST_DIR } else { (Join-Path $RootDir "apps\web\dist") }

$Supervisor = Join-Path $RootDir "scripts\windows\run_worker_supervisor.ps1"

if (-not (Test-Path $Supervisor)) {
  throw "Missing worker supervisor script: $Supervisor"
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Supervisor -RootDir $RootDir
