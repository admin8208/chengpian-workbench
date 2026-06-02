#!/usr/bin/env bash
set -euo pipefail

API_PORT="${CHENGPIAN_API_PORT:-8010}"
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
WEB_DIST_DIR="$ROOT_DIR/apps/web/dist"
WEB_SRC_DIR="$ROOT_DIR/apps/web/src"
META_FILE="$WEB_DIST_DIR/build-meta.json"

echo "=== 成片工作台 Linux 检查 ==="
echo
echo "[1] Frontend build"
if [[ -f "$WEB_DIST_DIR/index.html" ]]; then
  echo "dist/index.html exists"
else
  echo "dist/index.html missing"
fi

if [[ -f "$META_FILE" ]]; then
  echo "build-meta.json exists"
  python3 - <<'PY' "$META_FILE"
import json, sys
path = sys.argv[1]
obj = json.load(open(path, 'r', encoding='utf-8'))
print(f"built_at={obj.get('built_at') or 'unknown'}")
print(f"git_commit={obj.get('git_commit') or 'unknown'}")
print(f"git_branch={obj.get('git_branch') or 'unknown'}")
PY
else
  echo "build-meta.json missing"
fi

if [[ -d "$WEB_SRC_DIR" && -f "$WEB_DIST_DIR/index.html" ]]; then
  SRC_TS=$(python3 - <<'PY' "$WEB_SRC_DIR"
from pathlib import Path
import sys
root = Path(sys.argv[1])
latest = 0.0
for p in root.rglob('*'):
    if p.is_file():
        latest = max(latest, p.stat().st_mtime)
print(latest)
PY
)
  DIST_TS=$(python3 - <<'PY' "$WEB_DIST_DIR/index.html"
from pathlib import Path
import sys
print(Path(sys.argv[1]).stat().st_mtime)
PY
)
  python3 - <<'PY' "$SRC_TS" "$DIST_TS"
import sys
src_ts = float(sys.argv[1])
dist_ts = float(sys.argv[2])
if src_ts > dist_ts:
    print("WARN: frontend dist may be stale (src newer than dist)")
else:
    print("frontend dist freshness looks ok")
PY
fi

echo
echo "[2] API health"
curl --max-time 5 "http://127.0.0.1:${API_PORT}/api/health" || true

echo
echo "[3] Listening ports"
ss -ltnp | grep -E ":${API_PORT}|:80|:443" || true
