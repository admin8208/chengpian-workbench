$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ApiScript = Join-Path $PSScriptRoot "start_api.ps1"
$WorkerScript = Join-Path $PSScriptRoot "start_worker.ps1"
$ApiPort = if ($env:CHENGPIAN_API_PORT) { [int]$env:CHENGPIAN_API_PORT } else { 8010 }
$DataDir = if ($env:CHENGPIAN_DATA_DIR) { $env:CHENGPIAN_DATA_DIR } else { (Join-Path $RootDir "data") }
$LogsDir = Join-Path $DataDir "logs\prod"
$ApiOut = Join-Path $LogsDir "api.out.log"
$ApiErr = Join-Path $LogsDir "api.err.log"
$WorkerOut = Join-Path $LogsDir "worker.out.log"
$WorkerErr = Join-Path $LogsDir "worker.err.log"

function Wait-Port {
  param(
    [Parameter(Mandatory = $true)][int]$Port,
    [int]$TimeoutSeconds = 60
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-NetConnection 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) {
      return $true
    }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Show-LogTail {
  param(
    [Parameter(Mandatory = $true)][string]$Label,
    [Parameter(Mandatory = $true)][string]$Path
  )

  Write-Host ""
  Write-Host "--- ${Label}: $Path ---"
  if (Test-Path $Path) {
    Get-Content $Path -Tail 80
  } else {
    Write-Host "Log file does not exist."
  }
}

if (-not (Test-Path $ApiScript)) {
  throw "Missing production API start script: $ApiScript"
}

if (-not (Test-Path $WorkerScript)) {
  throw "Missing production worker start script: $WorkerScript"
}

if (-not (Test-Path $LogsDir)) {
  New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$apiProc = Start-Process powershell.exe -ArgumentList @(
  '-NoProfile',
  '-ExecutionPolicy', 'Bypass',
  '-File', $ApiScript
) -WorkingDirectory $RootDir -RedirectStandardOutput $ApiOut -RedirectStandardError $ApiErr -WindowStyle Hidden -PassThru

$workerProc = Start-Process powershell.exe -ArgumentList @(
  '-NoProfile',
  '-ExecutionPolicy', 'Bypass',
  '-File', $WorkerScript
) -WorkingDirectory $RootDir -RedirectStandardOutput $WorkerOut -RedirectStandardError $WorkerErr -WindowStyle Hidden -PassThru

Write-Host ("Started production services. api_pid={0} worker_pid={1}" -f $apiProc.Id, $workerProc.Id)
Write-Host ("Logs: {0}, {1}, {2}, {3}" -f $ApiOut, $ApiErr, $WorkerOut, $WorkerErr)
Write-Host "Waiting for production API to become ready..."

$apiReady = Wait-Port -Port $ApiPort -TimeoutSeconds 90
Start-Sleep -Seconds 3
$workerAlive = -not $workerProc.HasExited

if (-not $apiReady) {
  Show-LogTail -Label "API error log" -Path $ApiErr
  Show-LogTail -Label "API output log" -Path $ApiOut
  throw "Production API did not open port $ApiPort."
}

try {
  Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 30 | Out-Null
  Write-Host ("API health check OK on http://127.0.0.1:{0}" -f $ApiPort)
} catch {
  Show-LogTail -Label "API error log" -Path $ApiErr
  Show-LogTail -Label "API output log" -Path $ApiOut
  throw "Production API port is open, but /api/health failed: $($_.Exception.Message)"
}

if (-not $workerAlive) {
  Show-LogTail -Label "Worker error log" -Path $WorkerErr
  Show-LogTail -Label "Worker output log" -Path $WorkerOut
  throw "Production worker exited during startup."
}

Write-Host "Production API and worker started successfully."
