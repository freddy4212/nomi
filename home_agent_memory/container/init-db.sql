-- Home Agent Memory Layer - 資料庫初始化腳本
-- 此腳本會在容器首次啟動時自動執行

-- 啟用 TimescaleDB 擴展
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 啟用 pgvector 擴展
CREATE EXTENSION IF NOT EXISTS vector;

-- 顯示已啟用的擴展
SELECT extname, extversion FROM pg_extension;

-- 確認 TimescaleDB 版本
SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'timescaledb';

-- 確認 vector 版本  
SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'vector';

-- 記錄初始化完成
DO $$
BEGIN
    RAISE NOTICE 'Home Agent Memory Layer 資料庫初始化完成';
    RAISE NOTICE 'TimescaleDB 和 pgvector 擴展已啟用';
END $$;
