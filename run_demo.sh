#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/backend"
exec "$ROOT/.venv/bin/uvicorn" municipal_hub.main:app --host 0.0.0.0 --port 8080
