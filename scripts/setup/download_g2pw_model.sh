#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/../../apps/api/g2pW"
MODEL_FILE="g2pw.onnx"
OUTPUT_PATH="$OUTPUT_DIR/$MODEL_FILE"
mkdir -p "$OUTPUT_DIR"
if [ -f "$OUTPUT_PATH" ]; then
    SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
    echo "✓ 模型已存在: $OUTPUT_PATH ($SIZE)"
    exit 0
fi
echo "正在下载 G2PW 模型（约 160MB）..."
echo "来源: HuggingFace alextomcat/G2PWModel"
URL="https://huggingface.co/alextomcat/G2PWModel/resolve/main/g2pW.onnx"
if command -v wget &>/dev/null; then
    wget -O "$OUTPUT_PATH" "$URL"
elif command -v curl &>/dev/null; then
    curl -L -o "$OUTPUT_PATH" "$URL"
else
    echo "错误: 请安装 wget 或 curl" >&2
    exit 1
fi
if [ -f "$OUTPUT_PATH" ]; then
    SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
    echo "✓ 下载完成: $OUTPUT_PATH ($SIZE)"
else
    echo "错误: 下载失败" >&2
    echo "请手动下载并放置到: $OUTPUT_PATH" >&2
    echo "下载地址: $URL" >&2
    exit 1
fi
