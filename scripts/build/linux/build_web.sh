#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
WEB_DIR="$ROOT_DIR/apps/web"

cd "$WEB_DIR"
npm install
npm run build
