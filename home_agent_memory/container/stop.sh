#!/bin/bash
# Home Agent Memory Layer - 容器停止腳本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 檢查 podman 或 docker
if command -v podman &> /dev/null; then
    COMPOSE_CMD="podman-compose"
elif command -v docker &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 錯誤：找不到 podman 或 docker"
    exit 1
fi

echo "🛑 停止 PostgreSQL 容器..."
$COMPOSE_CMD down

echo "✅ 容器已停止"
echo ""
echo "💡 資料已保留在 volume 中，下次啟動會自動恢復"
echo "   如需完全刪除資料：$COMPOSE_CMD down -v"
