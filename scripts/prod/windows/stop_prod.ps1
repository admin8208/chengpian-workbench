Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "run_api.py|run_worker.py|run_worker_supervisor.ps1" } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force
}
