$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ApiDir = Join-Path $RootDir "apps\api"
$WebDir = Join-Path $RootDir "apps\web"

function Collect-LocalProcessIds {
  $ids = @()

  Get-CimInstance Win32_Process |
    Where-Object {
      $cmd = [string]$_.CommandLine
      if (-not $cmd) {
        return $false
      }

      (($cmd -like "*$ApiDir*") -and (($cmd -match 'run_api.py') -or ($cmd -match 'run_worker.py'))) -or
      ($cmd -like "*run_worker_supervisor.ps1*") -or
      (($cmd -like "*$WebDir*") -and (($cmd -match 'vite(\.cmd|\.js)?') -or ($cmd -match 'npm(\.cmd)?\s+run\s+dev')))
    } |
    ForEach-Object {
      $ids += [int]$_.ProcessId
    }

  foreach ($port in @(8010, 5173)) {
    try {
      $listeners = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -State Listen -ErrorAction SilentlyContinue
      foreach ($listener in $listeners) {
        if ($listener.OwningProcess) {
          $ids += [int]$listener.OwningProcess
        }
      }
    } catch {
      # Older Windows builds may not have Get-NetTCPConnection available.
    }
  }

  $allProcesses = @(Get-CimInstance Win32_Process)
  for ($i = 0; $i -lt 3; $i += 1) {
    $parentIds = @($ids | Sort-Object -Unique)
    foreach ($proc in $allProcesses) {
      if ($parentIds -contains [int]$proc.ParentProcessId) {
        $ids += [int]$proc.ProcessId
      }
    }
  }

  return @($ids | Sort-Object -Unique)
}

$stoppedAny = $false
for ($attempt = 0; $attempt -lt 6; $attempt += 1) {
  $processIds = @(Collect-LocalProcessIds)
  if ($processIds.Count -eq 0) {
    break
  }

  $stoppedAny = $true
  foreach ($processId in $processIds) {
    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
    } catch {
      # The process may have already exited.
    }
  }
  Start-Sleep -Milliseconds 500
}

Write-Host "Requested stop for API, Worker, and Web dev server."
