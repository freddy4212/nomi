#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_START_SCRIPT="$ROOT_DIR/memory_layer/container/start.sh"
FRONTEND_DIR="$ROOT_DIR/control_panel/frontend"
FRONTEND_ENV_FILE="$FRONTEND_DIR/.env.local"
BACKEND_LOG_FILE="$ROOT_DIR/control_panel/backend/backend.log"

find_free_port() {
  local start_port="${1:-8000}"
  local end_port="${2:-8099}"
  local port

  for ((port=start_port; port<=end_port; port++)); do
    if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "$port"
      return 0
    fi
  done

  return 1
}

echo "========================================"
echo "NOMI Host Unified Startup"
echo "========================================"

if [[ ! -f "$MEMORY_START_SCRIPT" ]]; then
  echo "Error: memory layer startup script not found"
  echo "Expected: $MEMORY_START_SCRIPT"
  exit 1
fi

echo "[1/3] Starting Memory Layer container..."
bash "$MEMORY_START_SCRIPT"

echo "[2/3] Selecting backend port..."
if [[ -n "${NOMI_BACKEND_PORT:-}" ]]; then
  if lsof -nP -iTCP:"$NOMI_BACKEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Error: NOMI_BACKEND_PORT=$NOMI_BACKEND_PORT is already in use"
    exit 1
  fi
  BACKEND_PORT="$NOMI_BACKEND_PORT"
else
  BACKEND_PORT="$(find_free_port 8000 8099 || true)"
  if [[ -z "$BACKEND_PORT" ]]; then
    echo "Error: no free backend port found in range 8000-8099"
    exit 1
  fi
fi

echo "Backend port selected: $BACKEND_PORT"

FRONTEND_PORT="${NOMI_FRONTEND_PORT:-}"
if [[ -n "$FRONTEND_PORT" ]]; then
  if lsof -nP -iTCP:"$FRONTEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Error: NOMI_FRONTEND_PORT=$FRONTEND_PORT is already in use"
    exit 1
  fi
else
  FRONTEND_PORT="$(find_free_port 5173 5199 || true)"
  if [[ -z "$FRONTEND_PORT" ]]; then
    echo "Error: no free frontend port found in range 5173-5199"
    exit 1
  fi
fi

echo "Frontend port selected: $FRONTEND_PORT"

echo "Writing frontend env: $FRONTEND_ENV_FILE"
cat > "$FRONTEND_ENV_FILE" <<EOF
VITE_NOMI_BACKEND_PORT=$BACKEND_PORT
EOF

mkdir -p "$(dirname "$BACKEND_LOG_FILE")"

echo "[3/3] Starting backend and frontend..."
(
  cd "$ROOT_DIR"
  NOMI_BACKEND_PORT="$BACKEND_PORT" python -m control_panel.backend.main
) > "$BACKEND_LOG_FILE" 2>&1 &
BACKEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Backend log: $BACKEND_LOG_FILE"

cleanup() {
  echo ""
  echo "Stopping NOMI services..."
  if kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  echo "Done."
}

trap cleanup EXIT INT TERM

# wait backend ready (best effort)
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
    echo "Backend is ready at http://127.0.0.1:$BACKEND_PORT"
    break
  fi
  sleep 1
done

cd "$FRONTEND_DIR"
if [[ ! -d node_modules ]]; then
  echo "Installing frontend dependencies..."
  npm install
fi

echo "Starting frontend dev server..."
echo "Frontend will use backend port: $BACKEND_PORT"
echo "Frontend dev server port: $FRONTEND_PORT"
npm run dev -- --port "$FRONTEND_PORT"
