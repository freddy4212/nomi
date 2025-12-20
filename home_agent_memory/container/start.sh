#!/bin/bash
# Home Agent Memory Layer - 容器啟動腳本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================"
echo "  Home Agent Memory Layer - PostgreSQL Container"
echo "================================================"
echo ""

# 檢查 podman 或 docker
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    COMPOSE_CMD="podman-compose"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 錯誤：找不到 podman 或 docker"
    echo "請先安裝 Podman: https://podman.io/getting-started/installation"
    exit 1
fi

echo "使用容器引擎: $CONTAINER_CMD"
echo ""

# 檢查 compose
if ! command -v $COMPOSE_CMD &> /dev/null; then
    echo "❌ 錯誤：找不到 $COMPOSE_CMD"
    if [ "$CONTAINER_CMD" = "podman" ]; then
        echo "請安裝 podman-compose: pip install podman-compose"
    else
        echo "請安裝 docker-compose"
    fi
    exit 1
fi

# 啟動容器
echo "🚀 啟動 PostgreSQL 容器..."
$COMPOSE_CMD up -d

echo ""
echo "⏳ 等待資料庫就緒..."
sleep 5

# 檢查健康狀態
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if $CONTAINER_CMD exec home_agent_db pg_isready -U home_agent -d home_agent &> /dev/null; then
        echo ""
        echo "✅ 資料庫已就緒！"
        break
    fi
    echo -n "."
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo ""
    echo "❌ 資料庫啟動超時"
    exit 1
fi

echo ""
echo "================================================"
echo "  連線資訊"
echo "================================================"
echo "  Host:     localhost"
echo "  Port:     5432"
echo "  Database: home_agent"
echo "  User:     home_agent"
echo "  Password: home_agent_pwd"
echo ""
echo "  連線字串:"
echo "  postgresql://home_agent:home_agent_pwd@localhost:5432/home_agent"
echo "================================================"
echo ""
echo "📌 常用命令："
echo "  停止:  $COMPOSE_CMD down"
echo "  日誌:  $COMPOSE_CMD logs -f"
echo "  連線:  $CONTAINER_CMD exec -it home_agent_db psql -U home_agent -d home_agent"
echo ""
