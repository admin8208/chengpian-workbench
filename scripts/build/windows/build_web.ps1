$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$WebDir = Join-Path $RootDir "apps\web"

Set-Location $WebDir
npm install
npm run build
