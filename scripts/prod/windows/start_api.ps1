$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ApiDir = Join-Path $RootDir "apps\api"
$Python = Join-Path $ApiDir ".venv-win\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "Missing Windows API virtualenv: $Python. Run scripts\\build\\windows\\setup_api_venv.ps1 first."
}

$env:CHENGPIAN_API_HOST = if ($env:CHENGPIAN_API_HOST) { $env:CHENGPIAN_API_HOST } else { "127.0.0.1" }
$env:CHENGPIAN_API_PORT = if ($env:CHENGPIAN_API_PORT) { $env:CHENGPIAN_API_PORT } else { "8010" }
$env:CHENGPIAN_RELOAD = if ($env:CHENGPIAN_RELOAD) { $env:CHENGPIAN_RELOAD } else { "0" }
$env:CHENGPIAN_EXPOSE_DOCS = if ($env:CHENGPIAN_EXPOSE_DOCS) { $env:CHENGPIAN_EXPOSE_DOCS } else { "0" }
$env:CHENGPIAN_DATA_DIR = if ($env:CHENGPIAN_DATA_DIR) { $env:CHENGPIAN_DATA_DIR } else { (Join-Path $RootDir "data") }
$env:CHENGPIAN_WEB_DIST_DIR = if ($env:CHENGPIAN_WEB_DIST_DIR) { $env:CHENGPIAN_WEB_DIST_DIR } else { (Join-Path $RootDir "apps\web\dist") }

Set-Location $ApiDir
& $Python run_api.py
