#Requires -Version 5.1
<#
.SYNOPSIS
    下载 G2PW 多音字消歧 ONNX 模型到指定目录
.DESCRIPTION
    模型用于中文文本转拼音时的多音字消歧，约 160MB。
    来源：HuggingFace alextomcat/G2PWModel
#>

param(
    [string] = (Join-Path  "..\..\apps\api\g2pW")
)

 = "g2pw.onnx"
 = Join-Path  

if (Test-Path ) {
     = (Get-Item ).Length
    Write-Host "模型已存在:  (0 MB)" -ForegroundColor Green
    exit 0
}

Write-Host "正在下载 G2PW 模型（约 160MB）..." -ForegroundColor Cyan
Write-Host "来源: HuggingFace alextomcat/G2PWModel" -ForegroundColor Cyan

 = "https://huggingface.co/alextomcat/G2PWModel/resolve/main/g2pW.onnx"

try {
    Continue = 'SilentlyContinue'
    Invoke-WebRequest -Uri  -OutFile  -UseBasicParsing
    Continue = 'Continue'

    if (Test-Path ) {
         = (Get-Item ).Length
        Write-Host "下载完成:  (0 MB)" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "下载失败：文件未生成" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "下载失败: " -ForegroundColor Red
    Write-Host "请手动下载并放置到: " -ForegroundColor Yellow
    Write-Host "下载地址: " -ForegroundColor Yellow
    exit 1
}
