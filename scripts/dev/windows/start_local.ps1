param(
  [switch]$Detached
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ApiDir = Join-Path $RootDir "apps\api"
$WebDir = Join-Path $RootDir "apps\web"
$DataDir = Join-Path $RootDir "data"
$LogsDir = Join-Path $DataDir "logs"
$ApiLogsDir = Join-Path $LogsDir "api"
$WorkerLogsDir = Join-Path $LogsDir "worker"
$WebLogsDir = Join-Path $LogsDir "web"
$ApiPython = Join-Path $ApiDir ".venv-win\Scripts\python.exe"
$WebVite = Join-Path $WebDir "node_modules\.bin\vite.cmd"
$ApiOut = Join-Path $ApiLogsDir "windows.out.log"
$ApiErr = Join-Path $ApiLogsDir "windows.err.log"
$WorkerOut = Join-Path $WorkerLogsDir "windows.out.log"
$WorkerErr = Join-Path $WorkerLogsDir "windows.err.log"
$WebOut = Join-Path $WebLogsDir "windows.out.log"
$WebErr = Join-Path $WebLogsDir "windows.err.log"
$WorkerSupervisor = Join-Path $RootDir "scripts\windows\run_worker_supervisor.ps1"
$WebUrl = "http://127.0.0.1:5173"

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

function Watch-CombinedLogs {
  param(
    [Parameter(Mandatory = $true)][array]$Processes,
    [Parameter(Mandatory = $true)][array]$Logs
  )

  Write-Host ""
  Write-Host "Combined logs are streaming below. Press Ctrl+C to stop all local services."
  Write-Host ""

  $jobs = @()
  foreach ($log in $Logs) {
    $jobs += Start-Job -ArgumentList $log.Label, $log.Path -ScriptBlock {
      param([string]$Label, [string]$Path)
      while (-not (Test-Path -LiteralPath $Path)) {
        Start-Sleep -Milliseconds 300
      }
      Get-Content -LiteralPath $Path -Tail 40 -Wait | ForEach-Object {
        "[{0}] [{1}] {2}" -f (Get-Date -Format "HH:mm:ss"), $Label, $_
      }
    }
  }

  try {
    while ($true) {
      foreach ($job in $jobs) {
        Receive-Job -Job $job -ErrorAction SilentlyContinue
      }

      $running = 0
      foreach ($proc in $Processes) {
        try {
          $proc.Refresh()
          if (-not $proc.HasExited) { $running += 1 }
        } catch {
          # Process may have already disappeared.
        }
      }
      if ($running -lt $Processes.Count) {
        Write-Host ""
        Write-Host "A local service exited. Stopping remaining services..."
        break
      }

      Start-Sleep -Milliseconds 500
    }
  } finally {
    foreach ($job in $jobs) {
      Stop-Job -Job $job -ErrorAction SilentlyContinue | Out-Null
      Remove-Job -Job $job -Force -ErrorAction SilentlyContinue | Out-Null
    }
  }
}

& (Join-Path $PSScriptRoot "stop_local.ps1")

if (-not (Test-Path $DataDir)) {
  New-Item -ItemType Directory -Path $DataDir | Out-Null
}
foreach ($dir in @($LogsDir, $ApiLogsDir, $WorkerLogsDir, $WebLogsDir)) {
  if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
}

if (-not (Test-Path $ApiPython)) {
  throw "Missing Windows API virtualenv: $ApiPython. Run scripts\\build\\windows\\setup_api_venv.ps1 first."
}

if (-not (Test-Path $WebVite)) {
  Write-Host "Web dependencies missing. Running npm install..."
  Set-Location $WebDir
  & npm.cmd install
  if ($LASTEXITCODE -ne 0) {
    throw "npm install failed. Fix web dependency installation first."
  }
}

$env:CHENGPIAN_API_HOST = '127.0.0.1'
$env:CHENGPIAN_API_PORT = '8010'
$env:CHENGPIAN_RELOAD = '0'
$env:CHENGPIAN_EXPOSE_DOCS = '0'
$env:CHENGPIAN_DATA_DIR = Join-Path $RootDir 'data'
$env:CHENGPIAN_WEB_DIST_DIR = Join-Path $RootDir 'apps\web\dist'
$env:CHENGPIAN_ALLOW_ROOT_RUNTIME = '1'

$npm = (Get-Command npm.cmd).Source

$apiProc = Start-Process -FilePath $ApiPython -ArgumentList @('run_api.py') -WorkingDirectory $ApiDir -RedirectStandardOutput $ApiOut -RedirectStandardError $ApiErr -WindowStyle Hidden -PassThru
$workerProc = Start-Process -FilePath "powershell.exe" -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $WorkerSupervisor, '-RootDir', $RootDir, '-LogOut', $WorkerOut, '-LogErr', $WorkerErr) -WorkingDirectory $RootDir -WindowStyle Hidden -PassThru
$webProc = Start-Process -FilePath $npm -ArgumentList @('run','dev','--','--host','127.0.0.1','--port','5173') -WorkingDirectory $WebDir -RedirectStandardOutput $WebOut -RedirectStandardError $WebErr -WindowStyle Hidden -PassThru

Write-Host ("Started local services. api_pid={0} worker_pid={1} web_pid={2}" -f $apiProc.Id, $workerProc.Id, $webProc.Id)
Write-Host ("Logs: {0}, {1}, {2}" -f $ApiErr, $WorkerErr, $WebErr)

Write-Host "Waiting for API and Web to become ready..."
$apiReady = Wait-Port -Port ([int]$env:CHENGPIAN_API_PORT) -TimeoutSeconds 90
$webReady = Wait-Port -Port 5173 -TimeoutSeconds 90
$postgresReady = Test-NetConnection 127.0.0.1 -Port 5432 -InformationLevel Quiet
$redisReady = Test-NetConnection 127.0.0.1 -Port 6379 -InformationLevel Quiet

Write-Host ""
Write-Host "Startup status:"
Write-Host ("  API        http://127.0.0.1:{0}  {1}" -f $env:CHENGPIAN_API_PORT, $(if ($apiReady) { "OK" } else { "FAILED" }))
Write-Host ("  Web        http://127.0.0.1:5173  {0}" -f $(if ($webReady) { "OK" } else { "FAILED" }))
Write-Host ("  PostgreSQL 127.0.0.1:5432       {0}" -f $(if ($postgresReady) { "OK" } else { "FAILED" }))
Write-Host ("  Redis      127.0.0.1:6379       {0}" -f $(if ($redisReady) { "OK" } else { "FAILED" }))

if (-not $apiReady -or -not $webReady -or -not $postgresReady -or -not $redisReady) {
  if (-not $apiReady) { Show-LogTail -Label "API error log" -Path $ApiErr }
  if (-not $webReady) { Show-LogTail -Label "Web error log" -Path $WebErr; Show-LogTail -Label "Web output log" -Path $WebOut }
  if (-not $postgresReady) { Write-Host "PostgreSQL is not reachable on 127.0.0.1:5432." }
  if (-not $redisReady) { Write-Host "Redis is not reachable on 127.0.0.1:6379." }
  throw "Local startup did not complete. Fix the FAILED item above and run start_local.bat again."
}

try {
  Invoke-RestMethod "http://127.0.0.1:$($env:CHENGPIAN_API_PORT)/api/health" -TimeoutSec 30 | Out-Null
  Write-Host "API health check OK."
} catch {
  Show-LogTail -Label "API error log" -Path $ApiErr
  throw "API port is open, but /api/health failed: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Open $WebUrl"
try {
  Start-Process $WebUrl | Out-Null
} catch {
  Write-Host "Failed to open browser automatically: $($_.Exception.Message)"
}
if ($Detached) {
  Write-Host "Detached mode enabled. Services will keep running in background."
  Write-Host "Run scripts\\dev\\windows\\stop_local.ps1 to stop them."
  return
}

Write-Host "Keep this window open while using Chengpian Workbench. Press Ctrl+C to stop local services."

$combinedLogs = @(
  [pscustomobject]@{ Label = 'API OUT'; Path = $ApiOut },
  [pscustomobject]@{ Label = 'API ERR'; Path = $ApiErr },
  [pscustomobject]@{ Label = 'WORKER OUT'; Path = $WorkerOut },
  [pscustomobject]@{ Label = 'WORKER ERR'; Path = $WorkerErr },
  [pscustomobject]@{ Label = 'WEB OUT'; Path = $WebOut },
  [pscustomobject]@{ Label = 'WEB ERR'; Path = $WebErr }
)

$serviceExited = $false
try {
  Watch-CombinedLogs -Processes @($apiProc, $workerProc, $webProc) -Logs $combinedLogs
  $serviceExited = $true
} finally {
  & (Join-Path $PSScriptRoot "stop_local.ps1")
}

if ($serviceExited) {
  throw "A local service exited unexpectedly. Check the log paths printed above."
}
