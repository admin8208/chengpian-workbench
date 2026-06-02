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
$WebDist = Join-Path $WebDir "dist"
$WebDistIndex = Join-Path $WebDist "index.html"
$ApiOut = Join-Path $ApiLogsDir "debug.out.log"
$ApiErr = Join-Path $ApiLogsDir "debug.err.log"
$WorkerOut = Join-Path $WorkerLogsDir "debug.out.log"
$WorkerErr = Join-Path $WorkerLogsDir "debug.err.log"
$WebOut = Join-Path $WebLogsDir "debug.out.log"
$WebErr = Join-Path $WebLogsDir "debug.err.log"
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
    [Parameter(Mandatory = $true)][array]$Logs,
    [Parameter(Mandatory = $true)]$ApiProcess,
    [Parameter(Mandatory = $true)][int]$ApiPort,
    [Parameter(Mandatory = $true)][int]$WebPort
  )

  Write-Host ""
  Write-Host "Combined debug logs are streaming below. Press Ctrl+C to stop all debug services."
  Write-Host ""

  $jobs = @()
  $apiReloadGraceDeadline = $null
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

      $apiAlive = Test-NetConnection 127.0.0.1 -Port $ApiPort -InformationLevel Quiet -WarningAction SilentlyContinue
      $webAlive = Test-NetConnection 127.0.0.1 -Port $WebPort -InformationLevel Quiet -WarningAction SilentlyContinue
      $apiProcAlive = $false
      try {
        $ApiProcess.Refresh()
        $apiProcAlive = -not $ApiProcess.HasExited
      } catch {
        $apiProcAlive = $false
      }
      $workerAlive = $false
      if ($Processes.Count -gt 0) {
        try {
          $workerProc = $Processes[0]
          $workerProc.Refresh()
          $workerAlive = -not $workerProc.HasExited
        } catch {
          $workerAlive = $false
        }
      }

      if (-not $apiAlive -and $apiProcAlive) {
        if (-not $apiReloadGraceDeadline) {
          $apiReloadGraceDeadline = (Get-Date).AddSeconds(12)
        }
      } else {
        $apiReloadGraceDeadline = $null
      }

      $apiFailed = (-not $apiAlive) -and (-not $apiProcAlive)
      if ((-not $apiAlive) -and $apiProcAlive -and $apiReloadGraceDeadline -and ((Get-Date) -ge $apiReloadGraceDeadline)) {
        $apiFailed = $true
      }

      if ($apiFailed -or -not $webAlive -or -not $workerAlive) {
        Write-Host ""
        Write-Host "A debug service exited. Stopping remaining services..."
        $apiStatus = if ($apiAlive) { "OK" } elseif ($apiProcAlive) { "RELOADING" } else { "FAILED" }
        Write-Host ("  API port {0}: {1}" -f $ApiPort, $apiStatus)
        Write-Host ("  Web port {0}: {1}" -f $WebPort, $(if ($webAlive) { "OK" } else { "FAILED" }))
        Write-Host ("  Worker: {0}" -f $(if ($workerAlive) { "OK" } else { "FAILED" }))
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
  $npm = (Get-Command npm.cmd).Source
  $installProc = Start-Process -FilePath $npm -ArgumentList @('install') -WorkingDirectory $WebDir -NoNewWindow -Wait -PassThru
  if ($installProc.ExitCode -ne 0) {
    throw "npm install failed. Fix web dependency installation first."
  }
}

if (-not (Test-Path $WebDistIndex)) {
  Write-Host "Frontend dist missing. Running npm run build once for API preflight..."
  $npm = (Get-Command npm.cmd).Source
  $buildProc = Start-Process -FilePath $npm -ArgumentList @('run','build') -WorkingDirectory $WebDir -NoNewWindow -Wait -PassThru
  if ($buildProc.ExitCode -ne 0) {
    throw "npm run build failed. Fix frontend build first."
  }
}

$env:CHENGPIAN_API_HOST = '127.0.0.1'
$env:CHENGPIAN_API_PORT = '8010'
$env:CHENGPIAN_RELOAD = '1'
$env:CHENGPIAN_EXPOSE_DOCS = '1'
$env:CHENGPIAN_DATA_DIR = Join-Path $RootDir 'data'
$env:CHENGPIAN_WEB_DIST_DIR = Join-Path $RootDir 'apps\web\dist'
$env:CHENGPIAN_ALLOW_ROOT_RUNTIME = '1'

$npm = (Get-Command npm.cmd).Source

$apiProc = Start-Process -FilePath $ApiPython -ArgumentList @('run_api.py') -WorkingDirectory $ApiDir -RedirectStandardOutput $ApiOut -RedirectStandardError $ApiErr -WindowStyle Hidden -PassThru
$workerProc = Start-Process -FilePath "powershell.exe" -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $WorkerSupervisor, '-RootDir', $RootDir, '-LogOut', $WorkerOut, '-LogErr', $WorkerErr) -WorkingDirectory $RootDir -WindowStyle Hidden -PassThru
$webProc = Start-Process -FilePath $npm -ArgumentList @('run','dev','--','--host','127.0.0.1','--port','5173') -WorkingDirectory $WebDir -RedirectStandardOutput $WebOut -RedirectStandardError $WebErr -WindowStyle Hidden -PassThru

Write-Host ("Started debug services. api_pid={0} worker_pid={1} web_pid={2}" -f $apiProc.Id, $workerProc.Id, $webProc.Id)
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
Write-Host ("  Docs       http://127.0.0.1:{0}/docs  {1}" -f $env:CHENGPIAN_API_PORT, $(if ($apiReady) { "OK" } else { "FAILED" }))
Write-Host ("  PostgreSQL 127.0.0.1:5432       {0}" -f $(if ($postgresReady) { "OK" } else { "FAILED" }))
Write-Host ("  Redis      127.0.0.1:6379       {0}" -f $(if ($redisReady) { "OK" } else { "FAILED" }))

if (-not $apiReady -or -not $webReady -or -not $postgresReady -or -not $redisReady) {
  if (-not $apiReady) { Show-LogTail -Label "API error log" -Path $ApiErr; Show-LogTail -Label "API output log" -Path $ApiOut }
  if (-not $webReady) { Show-LogTail -Label "Web error log" -Path $WebErr; Show-LogTail -Label "Web output log" -Path $WebOut }
  if (-not $workerProc.HasExited) {
    $null = $workerProc.Refresh()
  }
  if ($workerProc.HasExited) { Show-LogTail -Label "Worker error log" -Path $WorkerErr; Show-LogTail -Label "Worker output log" -Path $WorkerOut }
  if (-not $postgresReady) { Write-Host "PostgreSQL is not reachable on 127.0.0.1:5432." }
  if (-not $redisReady) { Write-Host "Redis is not reachable on 127.0.0.1:6379." }
  throw "Debug startup did not complete. Fix the FAILED item above and run debug.bat again."
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
  Write-Host "Detached debug mode enabled. Services will keep running in background."
  Write-Host "Run scripts\\dev\\windows\\stop_local.ps1 to stop them."
  return
}

Write-Host "Debug mode is running in foreground."
Write-Host "Keep this window open while fixing and verifying changes. Press Ctrl+C to stop debug services."

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
  Watch-CombinedLogs -Processes @($workerProc) -Logs $combinedLogs -ApiProcess $apiProc -ApiPort ([int]$env:CHENGPIAN_API_PORT) -WebPort 5173
  $serviceExited = $true
} finally {
  & (Join-Path $PSScriptRoot "stop_local.ps1")
}

if ($serviceExited) {
  throw "A debug service exited unexpectedly. Check the log paths printed above."
}
