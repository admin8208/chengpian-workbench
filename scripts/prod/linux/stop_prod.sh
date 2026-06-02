#!/usr/bin/env bash
set -euo pipefail

pkill -f "run_api.py" || true
pkill -f "run_worker.py" || true
