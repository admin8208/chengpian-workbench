$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$ApiDir = Join-Path $RootDir "apps\api"
$VenvDir = Join-Path $ApiDir ".venv-win"
$PipIndexUrl = if ($env:PIP_INDEX_URL) { $env:PIP_INDEX_URL } else { "https://pypi.tuna.tsinghua.edu.cn/simple" }

Set-Location $ApiDir
if (-not (Test-Path $VenvDir)) {
  py -3.12 -m venv $VenvDir
}

$Python = Join-Path $VenvDir "Scripts\python.exe"
& $Python -m pip install -U pip
& $Python -m pip install -r requirements.txt -i $PipIndexUrl --timeout 120 --retries 10
