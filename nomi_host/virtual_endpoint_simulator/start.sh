#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# 尋找空閒後端 Port
mkdir -p "$ROOT_DIR/backend_logs"
BACKEND_LOG="$ROOT_DIR/backend_logs/backend_$(date +%s).log"
echo "Starting Backend... Logs: $BACKEND_LOG"

# 簡單的 Python script 找出可用 Port
BACKEND_PORT=$(python3 -c '
import socket
s = socket.socket()
s.bind(("", 0))
print(s.getsockname()[1])
s.close()
')

# 確保 Port > 8000 (習慣上) - 這裡做簡單處理，如果系統分配 < 8000 就用系統分配的，或者加個邏輯
# 為了穩定，我們還是用之前的 find_port.py 邏輯比較好
# 這裡改回用之前寫好的 find_port.py
BACKEND_PORT=$(python3 "$ROOT_DIR/find_port.py" 8000)
echo "Found available backend port: $BACKEND_PORT"

# 啟動後端
# 使用 nohup 讓它在背景執行
# 使用 Unbuffered python (-u) 以確保 Log 即時寫入
nohup python3 -u -m uvicorn backend.app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Backend running at http://127.0.0.1:$BACKEND_PORT"
echo "Backend Logs are being written to: $BACKEND_LOG"
echo "---------------------------------------------------"

# 顯示後端啟動的前幾行 Log，確保已載入資料
sleep 2
head -n 20 "$BACKEND_LOG"
echo "---------------------------------------------------"

echo "Starting frontend with API linked to backend..."

# 因為 Vite 預設會自己往下找 port，我們只需要把後端 URL 傳給它
# 為了避免 port 衝突導致混亂，也讓前端嘗試從 5174 開始找
cd "$ROOT_DIR/frontend"

# 使用環境變數傳遞 API_BASE_URL 給前端 App.vue
export VITE_API_BASE_URL="http://127.0.0.1:$BACKEND_PORT/api"

# 啟動前端 (npm run dev 本身會處理 port 佔用問題，自動往後延)
npm run dev

# 當前端結束時，清理後端
kill "$BACKEND_PID"

