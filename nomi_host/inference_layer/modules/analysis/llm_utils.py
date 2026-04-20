"""
llm_utils.py - LLM 設定與回應解析輔助函式
"""

import json
from pathlib import Path
from typing import Any, Dict

import yaml


def load_llm_config(config_path: Path) -> Dict[str, str]:
    """從指定 config 路徑讀取 LLM 設定"""
    if not config_path.exists():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[ActivityAnalyzer] Warning: failed to read {config_path}: {e}")
        return {}

    llm_config = config.get("llm", {}) if isinstance(config, dict) else {}
    if not isinstance(llm_config, dict):
        return {}
    return llm_config


def parse_llm_response(response_text: str, skeleton_only: bool) -> Dict[str, Any]:
    """解析 LLM 回應文字並回傳結構化欄位"""
    cleaned = response_text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    try:
        result_json = json.loads(cleaned)
        summary = result_json.get("label", "分析完成")
        detail = result_json.get("analysis", cleaned)
        env_impact = result_json.get("environment_impact", "無環境資料" if skeleton_only else "未提供")
        safety_flag = result_json.get("safety_flag", None)
    except json.JSONDecodeError:
        summary = "分析完成"
        detail = cleaned
        env_impact = "無環境資料" if skeleton_only else "無法解析"
        safety_flag = None

    return {
        "summary": summary,
        "detail": detail,
        "environment_impact": env_impact,
        "safety_flag": safety_flag,
    }
