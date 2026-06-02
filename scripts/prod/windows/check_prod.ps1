$ErrorActionPreference = "Continue"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ApiPort = if ($env:CHENGPIAN_API_PORT) { $env:CHENGPIAN_API_PORT } else { "8010" }
$WebDistDir = Join-Path $RootDir "apps\web\dist"
$MetaFile = Join-Path $WebDistDir "build-meta.json"

Write-Host "=== Chengpian Windows Check ==="
Write-Host ""
Write-Host "[1] Frontend build"
if (Test-Path (Join-Path $WebDistDir "index.html")) { Write-Host "dist/index.html exists" } else { Write-Host "dist/index.html missing" }
if (Test-Path $MetaFile) { Get-Content $MetaFile } else { Write-Host "build-meta.json missing" }

Write-Host ""
Write-Host "[2] API health"
try { Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 30 } catch { Write-Host $_.Exception.Message }

Write-Host ""
Write-Host "[3] Ports"
Test-NetConnection 127.0.0.1 -Port ([int]$ApiPort)
Test-NetConnection 127.0.0.1 -Port 5432
Test-NetConnection 127.0.0.1 -Port 6379
