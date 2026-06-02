#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"

if [[ "${CHENGPIAN_ALLOW_MANUAL_START:-0}" != "1" ]]; then
  if [[ -f "/etc/systemd/system/chengpian-worker.service" ]]; then
    printf '拒绝手工启动 Worker：生产环境请使用 systemctl start chengpian-worker.service\n' >&2
    exit 1
  fi
fi

export CHENGPIAN_DATA_DIR="${CHENGPIAN_DATA_DIR:-$ROOT_DIR/data}"
export CHENGPIAN_WEB_DIST_DIR="${CHENGPIAN_WEB_DIST_DIR:-$ROOT_DIR/apps/web/dist}"

cd "$API_DIR"
exec .venv/bin/python run_worker.py
