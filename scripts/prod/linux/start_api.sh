#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
API_DIR="$ROOT_DIR/apps/api"

if [[ "${CHENGPIAN_ALLOW_MANUAL_START:-0}" != "1" ]]; then
  if [[ -f "/etc/systemd/system/chengpian-api.service" ]]; then
    printf '拒绝手工启动 API：生产环境请使用 systemctl start chengpian-api.service\n' >&2
    exit 1
  fi
fi

export CHENGPIAN_API_HOST="${CHENGPIAN_API_HOST:-127.0.0.1}"
export CHENGPIAN_API_PORT="${CHENGPIAN_API_PORT:-8010}"
export CHENGPIAN_RELOAD="${CHENGPIAN_RELOAD:-0}"
export CHENGPIAN_EXPOSE_DOCS="${CHENGPIAN_EXPOSE_DOCS:-0}"
export CHENGPIAN_DATA_DIR="${CHENGPIAN_DATA_DIR:-$ROOT_DIR/data}"
export CHENGPIAN_WEB_DIST_DIR="${CHENGPIAN_WEB_DIST_DIR:-$ROOT_DIR/apps/web/dist}"

cd "$API_DIR"
exec .venv/bin/python run_api.py
