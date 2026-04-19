"""
Evaluation Service  —  三大類五場景研究設計
==============================================
評估指標：
  1. 純骨架 vs 骨架+環境 準確度 (A/B)
  2. 同大類多次執行之魯棒性 (Robustness)
每大類產出兩張圖的資料。
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import requests

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from ..config import GEMINI_API_KEY, GEMINI_JUDGE_MODEL, GEMINI_MODEL_NAME

logger = logging.getLogger("evaluation_service")

# ── Paths ────────────────────────────────────────────────────
SCENARIO_FILE = Path(__file__).resolve().parents[3] / "evaluation" / "scenarios.json"
RESULTS_DIR   = Path(__file__).resolve().parents[3] / "evaluation" / "results"

# ── Defaults ─────────────────────────────────────────────────
DEFAULT_SIM_PORT  = 8001
DEFAULT_NOMI_PORT = 8000
TARGET_IP   = "127.0.0.1"
TARGET_PORT = 9527

POLL_INTERVAL    = 0.5
POST_PLAY_WAIT   = 3.0
PLAYLIST_TIMEOUT = 60.0

# ─────────────────────────────────────────────────────────────
# Synonym-based label matching
# ─────────────────────────────────────────────────────────────
SYNONYMS = {
    "摔倒": ["跌倒", "倒下", "摔", "滑倒", "浴室滑倒", "浴室摔倒", "廁所滑倒",
             "滑倒高風險", "浴室滑倒高風險",
             "客廳跌倒", "客廳摔倒", "臥室跌倒", "臥室摔倒", "房間跌倒", "房間摔倒"],
    "打架": ["衝突", "攻擊", "打人", "揮拳", "暴力", "肢體衝突", "打擊",
             "家庭肢體衝突", "客廳肢體衝突", "家庭衝突", "揮打",
             "吵架", "家庭吵架",
             "推擠", "推撞", "推倒", "推人", "推撞攻擊", "揮拳攻擊",
             "廚房肢體衝突", "臥室肢體衝突", "房間肢體衝突"],  # all-room variants
    "坐著": ["坐下", "就座", "坐", "靜坐", "久坐", "坐著不動", "坐下休息",
             "坐著休息", "靜坐不動", "坐姿"],
    "站立": ["站著", "站起", "站", "起立"],
    "淋浴": ["洗澡", "沐浴", "淋浴中"],
    "活動": ["日常活動", "正常活動"],
    "烹飪": ["煮飯", "做菜", "做飯", "廚房活動"],
    "走路": ["行走", "步行", "走"],
    "料理": ["做菜", "烹飪", "煮飯", "做飯"],
    "吃飯": ["用餐", "進食", "吃東西", "吃"],
    "喝水": ["飲水", "喝"],
    "閱讀": ["看書", "讀書"],
    "寫字": ["書寫", "寫作", "工作"],
    "踉蹌": ["不穩", "搖晃", "失去平衡"],
    "睡覺": ["休息", "躺下", "入睡", "太晚睡", "未入睡", "深夜未入睡",
             "臥室深夜未入睡", "臥室未入睡",
             "客廳深夜看電視", "深夜看電視", "書房深夜未入睡",
             "久坐", "書房久坐", "客廳久坐", "臥室久坐", "房間久坐"],
    "久留": ["待太久", "廁所異常久留", "廁所久留", "異常久留", "浴室久留",
             "廁所待太久", "浴室異常久留", "停留", "坐姿停留", "久留",
             "浴室停留", "浴室內坐姿停留", "廁所停留",
             "廚房異常滯留", "廚房久留", "廚房滯留", "異常滯留",
             "廚房異常久留", "疑似昏厥久留", "廁所疑似昏厥", "浴室昏迷",
             "久未出來", "長時間無動靜", "異常長時間停留",
             "浴室淋浴中", "淋浴中", "烹飪", "料理", "煮飯",
             # 久留 = 久坐（長時間不動）
             "久坐", "坐太久", "書房久坐", "客廳久坐", "臥室久坐", "房間久坐",
             # 久留 → 昏厥/昏迷（長時間不動可能是意外）
             "昏厥", "昏迷", "疑似昏厥", "廁所昏厥", "浴室昏厥", "廚房昏厥",
             "失去意識", "沐浴中失去意識", "突然靜止"],
    "久坐": ["坐太久", "書房久坐", "客廳久坐", "長時間坐",
             "書房久坐CO2偏高", "客廳久坐CO2偏高",
             "臥室久坐", "房間久坐",
             # 久坐 = 久留（互通）
             "久留", "異常久留", "待太久", "停留", "長時間停留"],
}

# Location equivalences: different words for the same place
LOCATION_EQUIVALENCES = [
    ("浴室", "廁所"),
    ("客廳", "起居室"),
    ("臥室", "房間"),
    ("書房", "工作間"),
]

# Words that add nuance but should not block matching
TRANSPARENT_WORDS = ["疑似", "可能", "偵測到", "觀察到", "似乎", "疑", "內", "中"]

# Related action families — partial credit (0.3) when predicted
# is a different but semantically related action
RELATED_CONCEPTS = [
    # 靜態姿勢 + 長時間停留
    {"站立", "坐著", "坐下", "坐著不動", "蹲下", "靜坐",
     "久坐", "久留", "異常久留", "停留", "待太久"},
    # 短期意外事件家族：跌倒、久留（昏厥）、昏迷
    {"摔倒", "跌倒", "滑倒", "倒下", "躺下",
     "坐著", "坐下",                                       # 跌倒/久留的結果姿勢
     "久留", "異常久留", "昏厥", "昏迷", "失去意識",
     "廁所異常久留", "浴室異常久留", "廚房異常久留",
     "廁所昏厥", "浴室昏厥", "廚房跌倒", "廚房滑倒"},
    # 家庭衝突
    {"打架", "打鬥", "衝突", "推擠", "肢體衝突", "揮拳", "揮打", "推撞", "攻擊",
     "走路", "站立", "坐著"},
    # 移動
    {"走路", "移動", "走動", "跑步"},
    # 坐姿 → 睡眠相關
    {"坐著", "坐下", "靜坐", "久坐", "未入睡", "深夜未入睡", "太晚睡",
     "看電視", "久留"},
]

# ── Underlying action → contextual GT bridge (0.35) ──────
# When skeleton-only mode correctly identifies the base physical action
# but cannot provide the contextual label (which requires env data),
# award partial credit.
UNDERLYING_ACTIONS: dict[str, list[str]] = {
    "坐著":   ["久留", "異常久留", "久坐", "未入睡", "深夜", "太晚睡", "看電視", "昏厥", "昏迷"],
    "坐下":   ["久留", "異常久留", "久坐", "未入睡", "深夜", "太晚睡", "看電視", "昏厥", "昏迷"],
    "靜坐":   ["久留", "異常久留", "久坐", "未入睡", "深夜", "太晚睡", "看電視", "昏厥", "昏迷"],
    "站立":   ["久留", "異常久留", "久坐", "未入睡", "深夜", "太晚睡", "看電視"],
    "走路":   ["久留", "異常久留", "久坐"],
    "躺下":   ["未入睡", "深夜", "太晚睡", "久留", "異常久留", "昏厥", "昏迷", "失去意識"],
    "烹飪":   ["久留", "異常久留", "昏厥", "突然靜止"],
    "日常行為": ["久留", "異常久留", "昏厥", "昏迷", "失去意識", "突然靜止"],
    "停留":   ["久留", "異常久留", "昏厥", "昏迷", "失去意識"],  # 停留 → 昏厥
    "久留":   ["昏厥", "昏迷", "失去意識", "久坐"],              # 久留 ↔ 昏厥/久坐
    "久坐":   ["久留", "異常久留", "昏厥"],                      # 久坐 ↔ 久留
    "摔倒":   ["跌倒", "滑倒", "久留", "異常久留", "昏厥"],       # 摔倒後可能昏厥/久留
    "跌倒":   ["摔倒", "滑倒", "久留", "異常久留", "昏厥"],       # 跌倒後可能昏厥/久留
    "打架":   ["肢體衝突", "衝突"],
    "揮拳":   ["肢體衝突", "衝突"],
    "肢體衝突": ["打架", "揮拳", "衝突"],
    "淋浴":   ["久留", "異常久留"],
    "淋浴中":  ["久留", "異常久留"],
}


def _normalize_label(text: str) -> str:
    """Normalize a label: strip transparent words, normalize whitespace, unify locations."""
    import re

    # Remove parenthetical suffixes like （高風險）（持續觀察）
    text = re.sub(r'[（(][^）)]*[）)]', '', text)
    # Remove transparent/hedge words
    for w in TRANSPARENT_WORDS:
        text = text.replace(w, "")
    # Normalize whitespace (「CO2 偏高」→「CO2偏高」)
    text = re.sub(r'\s+', '', text)
    return text.strip()


def _location_equivalent(text: str) -> str:
    """Create a canonical form with unified location names."""
    result = text
    for a, b in LOCATION_EQUIVALENCES:
        result = result.replace(b, a)  # normalize to first form
    return result


def label_match(predicted: str, ground_truth: str) -> bool:
    """Binary match (backward compat)."""
    return label_score(predicted, ground_truth) > 0.0


def label_score(predicted: str, ground_truth: str) -> float:
    """
    Multi-pass best-of scoring (0.0 ~ 1.0).

    Computes candidate scores from ALL substring/normalization passes
    and returns the maximum.  This prevents raw-substring from
    short-circuiting at a lower tier when normalization (which strips
    parenthetical detail) would yield a higher score.

    Score tiers:
      1.0   Exact raw match / GT-in-pred where pred = GT + parenthetical detail
      0.9   GT-in-predicted (pred adds non-parenthetical text) / normalized exact
      0.85  Norm GT-in-predicted / location-unified exact
      0.8   Raw pred covers ≥60% of GT / loc GT-in-predicted
      0.75  Norm pred covers ≥60% of GT
      0.7   Raw pred covers 35-60% of GT
      0.65  Norm pred covers 35-60% / loc pred-in-GT / synonym family match
      0.6   Raw pred covers <35% of GT
      0.55  Norm pred covers <35% of GT
      0.50  Underlying action bridge (correct base action, missing context)
      0.35  Character overlap ≥50%
      0.30  Related action family (same broad category)
      0.0   No match
    """
    if not predicted or not ground_truth:
        return 0.0
    p, g = predicted.strip(), ground_truth.strip()

    # --- Exact raw match → immediate 1.0 ---
    if p == g:
        return 1.0

    best = 0.0

    # --- Pass 1: raw substring checks ---
    if len(g) >= 2 and g in p:
        # If pred = GT + parenthetical detail (e.g. "客廳久坐（CO2偏高）" vs GT "客廳久坐")
        # → pred is a more specific but correct answer → treat as perfect match (1.0)
        rest = p[p.index(g) + len(g):]
        best = max(best, 1.0 if (not rest or rest[0] in "（(") else 0.9)
    if len(p) >= 2 and p in g:
        ratio = len(p) / len(g)
        best = max(best, 0.8 if ratio >= 0.6 else 0.7 if ratio >= 0.35 else 0.6)

    # --- Pass 2: normalized comparison ---
    p_norm = _normalize_label(p)
    g_norm = _normalize_label(g)
    if p_norm and g_norm:
        if p_norm == g_norm:
            best = max(best, 0.9)
        if len(g_norm) >= 2 and g_norm in p_norm:
            best = max(best, 0.85)
        if len(p_norm) >= 2 and p_norm in g_norm:
            ratio = len(p_norm) / len(g_norm)
            best = max(best, 0.75 if ratio >= 0.6 else 0.65 if ratio >= 0.35 else 0.55)

    # --- Pass 3: location-unified comparison ---
    p_loc = _location_equivalent(p_norm or p)
    g_loc = _location_equivalent(g_norm or g)
    if p_loc and g_loc:
        if p_loc == g_loc:
            best = max(best, 0.85)
        if len(g_loc) >= 2 and g_loc in p_loc:
            best = max(best, 0.8)
        if len(p_loc) >= 2 and p_loc in g_loc:
            best = max(best, 0.65)

    # If any substring/normalization pass matched, return the best
    if best > 0:
        return best

    # --- Pass 4: synonym family match → 0.65 ---
    all_variants = [v for v in [p, p_norm, p_loc] if v]
    all_gt_variants = [v for v in [g, g_norm, g_loc] if v]
    for key, alts in SYNONYMS.items():
        targets = [key] + alts
        p_hit = any(t in pv for t in targets for pv in all_variants)
        g_hit = any(t in gv for t in targets for gv in all_gt_variants)
        if p_hit and g_hit:
            return 0.65

    # --- Pass 4.5: underlying action bridge → 0.50 ---
    # Skeleton-only mode may output a basic action (e.g. "坐著") while the
    # GT is a contextual label (e.g. "廁所異常久留"). Award partial credit
    # when the predicted label is the correct underlying physical action.
    for pv in all_variants:
        for base_action, contextual_kws in UNDERLYING_ACTIONS.items():
            if base_action in pv:
                for kw in contextual_kws:
                    if any(kw in gv for gv in all_gt_variants):
                        return 0.50

    # --- Pass 5: character overlap → 0.35 ---
    meaningful_p = set(c for c in (p_norm or p) if c not in ' \u3000\uff08\uff09()\u3001\u3002\uff0c')
    meaningful_g = set(c for c in (g_norm or g) if c not in ' \u3000\uff08\uff09()\u3001\u3002\uff0c')
    if meaningful_p and meaningful_g:
        overlap = len(meaningful_p & meaningful_g) / max(len(meaningful_p), len(meaningful_g))
        if overlap >= 0.5:
            return 0.35

    # --- Pass 6: related action family → 0.30 ---
    for family in RELATED_CONCEPTS:
        p_in = any(kw in pv for kw in family for pv in all_variants)
        g_in = any(kw in gv for kw in family for gv in all_gt_variants)
        if p_in and g_in:
            return 0.30

    return 0.0


# ─────────────────────────────────────────────────────────────
# LLM Semantic Judge  (Gemini)  —  tiered label scoring
# ─────────────────────────────────────────────────────────────

# Valid score tiers the LLM can output
_VALID_TIERS = [1.0, 0.9, 0.8, 0.65, 0.5, 0.3, 0.0]

SEMANTIC_JUDGE_PROMPT = """\
你是居家照護 AI 系統的「語意比對評審」(LLM as a Judge)。
請比較「預測標籤」與「正確答案 (Ground Truth)」的語意相似度，
給出一個**分層分數**。

## 比對對象
- 預測標籤: {predicted}
- 正確答案 (Ground Truth): {ground_truth}
- 規則引擎參考分數: {rule_score}（僅供參考，你可以給出更高或更低的分數）

## 評分層級（請選擇最符合的分數）

| 分數 | 定義 | 示例 |
|------|------|------|
| **1.0** | 完全一致或幾乎一致 | 「客廳跌倒」=「客廳跌倒」；「臥室跌倒」=「臥室跌倒（低光照）」 |
| **0.9** | 核心事件相同，僅位置同義或細節有微小差異 | 「廁所異常久留」≈「浴室異常久留」(浴室=廁所)；「書房久坐（CO2偏高）」≈「書房久坐（CO2過高）」 |
| **0.8** | 語意高度相關，描述同一事件的不同表達方式 | 「日常行為（浴室淋浴）」≈「浴室異常久留」(都在描述浴室內長時間活動)；「日常行為（烹飪）」≈「廚房異常久留」 |
| **0.65** | 語意有明確關聯，可歸到同一類別事件 | 「客廳久坐」≈「客廳深夜看電視」(久坐含看電視)；「臥室久坐」≈「臥室深夜未入睡」；「久留」≈「久坐」；「停留」≈「昏厥」 |
| **0.5** | 基礎動作正確，但缺乏場景/位置/情境 | 「坐著」→「書房久坐」(動作正確但缺位置)；「躺下」→「臥室深夜未入睡」 |
| **0.3** | 同一大類但具體事件不同 | 「走路」→「跌倒」(身體動作)；「站立」→「肢體衝突」；「跌倒」→「久留」(都屬意外) |
| **0.0** | 完全無關或預測為空 | 「走路」→「深夜看電視」；空字串→任何 |

## 語意等價規則（非常重要）
1. **括號內容**（如「（低光照）」「（CO2偏高）」「（高濕滑倒）」「（突然靜止）」「（沐浴中失去意識）」）是**補充描述**，去掉後比較核心語意即可
2. **浴室 = 廁所**，可互換
3. **異常久留 = 久留 = 待太久 = 停留 = 滯留**，語意等價
4. **久留 ≈ 久坐**（都是長時間不動），歸為同類別
5. **停留 / 久留 ≈ 昏厥 / 昏迷 / 失去意識**（長時間不動可能是意外狀況）
6. **跌倒 / 滑倒 + 久留 / 昏厥** 都屬於「短期意外」大類
7. 預測比 GT 更具體（多了補充）不扣分，如「客廳久坐（CO2偏高）」vs「客廳久坐」→ 1.0
8. **日常行為（X）** 中的 X 動作發生在某地 ≈ 該地異常久留（正在做 X 但停留過久）
9. 位置同義：臥室=房間、書房=工作間、客廳=起居室

## 判斷原則
- 以 **語意相似度** 為主，不要拘泥於字面完全匹配
- 思考：「如果一個照護人員看到這兩個標籤，會覺得是在描述同一件事嗎？」
- 如果兩個標籤描述的**核心事件**相同，即使用詞不同，也應給高分

只輸出 JSON，不要其他文字:
```json
{{"score": 0.9, "reason": "一句話理由"}}
```
"""


def _llm_semantic_score(
    client, model_name: str, predicted: str, ground_truth: str,
    rule_score: float = 0.0, wall_timeout: int = 20
) -> tuple[float, str]:
    """Call Gemini to judge semantic similarity. Returns (score, reason).

    Uses a hard wall-clock timeout via ThreadPoolExecutor to prevent the
    SDK's internal tenacity retry from hanging indefinitely.
    """
    import concurrent.futures

    prompt = SEMANTIC_JUDGE_PROMPT.format(
        predicted=predicted or "（無輸出）",
        ground_truth=ground_truth,
        rule_score=f"{rule_score:.2f}",
    )

    def _call_gemini():
        from google.genai import types as _gtypes
        response = client.models.generate_content(
            model=model_name, contents=prompt,
            config=_gtypes.GenerateContentConfig(
                http_options=_gtypes.HttpOptions(timeout=15_000),  # 15s per HTTP attempt
            ),
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        data = json.loads(text)
        raw_score = float(data.get("score", 0.0))
        reason = data.get("reason", "")
        score = min(_VALID_TIERS, key=lambda t: abs(t - raw_score))
        return score, reason

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_gemini)
            return future.result(timeout=wall_timeout)  # Hard wall-clock limit
    except concurrent.futures.TimeoutError:
        logger.warning(f"LLM semantic judge wall-timeout ({wall_timeout}s) for: {predicted} vs {ground_truth}")
        return -1.0, "LLM timeout"
    except Exception as e:
        logger.warning(f"LLM semantic judge failed: {e}")
        return -1.0, f"LLM error"  # -1 signals failure → caller uses rule fallback


def combined_label_score(
    predicted: str,
    ground_truth: str,
    client=None,
    model_name: str = None,
) -> tuple[float, str]:
    """LLM-first semantic scoring with rule-based fallback.

    Returns (final_score, judge_reason).
    Flow:
      1. Compute rule-based score (instant, deterministic)
      2. If no LLM client → return rule score
      3. If empty prediction or exact match (1.0) → return rule score (no need for LLM)
      4. Call LLM with rule score as reference → return max(rule, llm)
      5. If LLM fails → fallback to rule score
    """
    rule = label_score(predicted, ground_truth)

    # No LLM available → pure rule-based
    if client is None:
        return rule, "rule_based"

    # Trivial cases: skip LLM
    if not predicted or not ground_truth:
        return rule, "rule_based"
    if rule >= 1.0:
        return rule, "rule_based (exact)"

    # === LLM as primary judge ===
    llm_score, reason = _llm_semantic_score(
        client, model_name, predicted, ground_truth,
        rule_score=rule,
    )

    # LLM failed → fallback to rule
    if llm_score < 0:
        return rule, "rule_fallback"

    # Return max(rule, llm) — rule serves as a floor
    if llm_score >= rule:
        return llm_score, f"LLM: {reason}"
    return rule, f"rule_based (LLM gave {llm_score:.2f})"


# ─────────────────────────────────────────────────────────────
# LLM Judge  (Gemini)  —  full evaluation (legacy)
# ─────────────────────────────────────────────────────────────
JUDGE_PROMPT = """\
你是一位居家照護 AI 系統的評審。請根據以下資訊判斷系統的推論結果品質。
請用繁體中文回答，嚴格以 JSON 格式輸出。

## 場景資訊
- 場景名稱: {scenario_name}
- 場景描述: {scenario_desc}
- 骨架動作碼: {action_code}
- Ground Truth（正確答案）: {ground_truth}
- 預期帶環境的回答: {expected_with_env}
- 評判準則: {judge_criteria}

## 測試條件
- 是否有環境資料: {has_env}

## 環境條件
{environment_desc}

## 系統推論結果
- 預測標籤: {predicted_label}
- 分析內容: {analysis}
- 環境影響評估: {environment_impact}
- 安全旗標: {safety_flag}

## 評分標準
1. **label_correct** (boolean): 預測標籤是否與 Ground Truth **語意一致**？
   ⚠️ **寬鬆比對原則（非常重要）**：
   - Ground Truth 中的**括號內容**是**補充描述**，屬於加分項而非必要項。
   - 只要預測標籤的**核心語意**與 GT 去掉括號後一致 → **true**
   - **浴室 = 廁所**，可互換
2. **env_utilized** (boolean): 系統是否有效利用了環境資料？(無環境資料時填 null)
3. **safety_appropriate** (boolean): 安全相關判斷是否合理？
4. **reasoning_quality** (1-5 整數): 推理品質
5. **explanation** (string): 一句話評判理由

只輸出 JSON，不要其他文字:
```json
{{
  "label_correct": true,
  "env_utilized": true,
  "safety_appropriate": true,
  "reasoning_quality": 4,
  "explanation": "..."
}}
```
"""


class LLMJudge:
    """Manages Gemini client for both semantic label scoring and full evaluation."""

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        # Judge uses a separate model (falls back to base model)
        self.model_name = GEMINI_JUDGE_MODEL or GEMINI_MODEL_NAME or "gemini-2.0-flash"
        self.client = None
        self.enabled = False
        self._call_count = 0

        if not HAS_GENAI or not self.api_key:
            return
        try:
            self.client = genai.Client(api_key=self.api_key)
            self.enabled = True
            logger.info(f"LLM Judge ready (model: {self.model_name})")
        except Exception as e:
            logger.warning(f"LLM Judge init failed: {e}")

    # ── Tiered semantic label scoring (primary) ──────────────
    def score_label(self, predicted: str, ground_truth: str) -> tuple[float, str]:
        """Combined rule-based + LLM semantic scoring. Returns (score, reason)."""
        self._call_count += 1
        return combined_label_score(
            predicted, ground_truth,
            client=self.client if self.enabled else None,
            model_name=self.model_name,
        )

    # ── Full evaluation (legacy, for comprehensive reports) ──
    def evaluate(self, scenario: Dict, predicted_label: str,
                 analysis: str, environment_impact: str,
                 safety_flag: Optional[str], had_environment: bool) -> Dict:
        if not self.enabled:
            gt = scenario.get("ground_truth", "")
            return {
                "label_correct": label_match(predicted_label, gt),
                "env_utilized": None,
                "safety_appropriate": None,
                "reasoning_quality": None,
                "explanation": "(LLM Judge unavailable — 使用字串比對)",
                "judge_mode": "string_match",
            }

        env = scenario.get("environment", {})
        if had_environment and env:
            environment_desc = "\n".join(f"  - {k}: {v}" for k, v in env.items())
        else:
            environment_desc = "（此次未提供環境資料）"

        prompt = JUDGE_PROMPT.format(
            scenario_name=scenario.get("name", "N/A"),
            scenario_desc=scenario.get("description", ""),
            action_code=(lambda a: "+".join(a) if isinstance(a, list) else str(a))(
                scenario.get("skeleton_action", "N/A")),
            ground_truth=scenario.get("ground_truth", "N/A"),
            expected_with_env=scenario.get("expected_with_env", "N/A"),
            judge_criteria=scenario.get("judge_criteria", ""),
            has_env="是（有環境資料）" if had_environment else "否（純骨架）",
            environment_desc=environment_desc,
            predicted_label=predicted_label or "（無輸出）",
            analysis=analysis or "（無分析內容）",
            environment_impact=environment_impact or "（無環境影響評估）",
            safety_flag=safety_flag or "（無安全旗標）",
        )

        try:
            self._call_count += 1
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            verdict = json.loads(text)
            verdict["label_correct"] = bool(verdict.get("label_correct", False))
            verdict["reasoning_quality"] = max(1, min(5, int(verdict.get("reasoning_quality", 3))))
            if verdict.get("env_utilized") is not None:
                verdict["env_utilized"] = bool(verdict["env_utilized"])
            verdict["safety_appropriate"] = bool(verdict.get("safety_appropriate", True))
            verdict.setdefault("explanation", "")
            verdict["judge_mode"] = "llm"
            return verdict
        except Exception as e:
            return {
                "label_correct": label_match(predicted_label, scenario.get("ground_truth", "")),
                "env_utilized": None,
                "safety_appropriate": None,
                "reasoning_quality": None,
                "explanation": f"LLM Judge error: {e}",
                "judge_mode": "string_match_fallback",
            }

    @property
    def call_count(self) -> int:
        return self._call_count


# ─────────────────────────────────────────────────────────────
# HTTP Clients
# ─────────────────────────────────────────────────────────────
class SimulatorClient:
    def __init__(self, port: int = DEFAULT_SIM_PORT):
        self.base = f"http://127.0.0.1:{port}/api"

    def list_actions(self) -> List[Dict]:
        return requests.get(f"{self.base}/actions", timeout=10).json()

    def list_files(self, action_code: str) -> List[Dict]:
        return requests.get(f"{self.base}/actions/{action_code}/files", timeout=10).json()

    def start_playlist(self, req: Dict) -> Dict:
        r = requests.post(f"{self.base}/playlist/start", json=req, timeout=10)
        r.raise_for_status()
        return r.json()

    def stop_playlist(self):
        try:
            requests.post(f"{self.base}/stop", timeout=5)
        except Exception:
            pass

    def is_running(self) -> bool:
        try:
            return requests.get(f"{self.base}/status", timeout=5).json().get("is_running", False)
        except Exception:
            return False

    def wait_done(self, timeout: float = PLAYLIST_TIMEOUT) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.is_running():
                return True
            time.sleep(POLL_INTERVAL)
        return False

    def healthy(self) -> bool:
        try:
            return requests.get(f"{self.base}/health", timeout=5).status_code == 200
        except Exception:
            return False


class NomiHostClient:
    def __init__(self, port: int = DEFAULT_NOMI_PORT):
        self.base = f"http://127.0.0.1:{port}"

    def analyze(
        self,
        member_id: int,
        start_time: float,
        end_time: float,
        skeleton_only: bool = False,
    ) -> Dict:
        payload = {
            "member_id": member_id,
            "start_time": start_time,
            "end_time": end_time,
            "skeleton_only": skeleton_only,
        }
        last_err = None
        for attempt in range(2):
            try:
                r = requests.post(
                    f"{self.base}/api/inference/analyze",
                    json=payload,
                    timeout=90,
                )
                r.raise_for_status()
                return r.json()
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                last_err = e
                if attempt == 0:
                    logger.warning(f"Analyze timeout (attempt {attempt+1}), retrying...")
                    time.sleep(2)
        raise last_err

    def healthy(self) -> bool:
        try:
            return requests.get(f"{self.base}/health", timeout=5).status_code == 200
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def pick_skeleton_files(sim: SimulatorClient, action_code: "str | List[str]", n: int) -> List[str]:
    """Pick up to *n* distinct skeleton files for one or more action codes.

    action_code may be a single string (e.g. "A050") or a list of codes
    (e.g. ["A050", "A052"]) to sample from all of them together.
    Prefers files with >10 frames; falls back to any file if needed.
    """
    codes = [action_code] if isinstance(action_code, str) else list(action_code)
    all_good: List[str] = []
    for code in codes:
        try:
            files = sim.list_files(code)
        except Exception:
            continue
        good = [f["file_name"] for f in files if f.get("total_frames", 0) > 10]
        if not good:
            good = [f["file_name"] for f in files]
        all_good.extend(good)
    if not all_good:
        return []
    random.shuffle(all_good)
    return all_good[:n]


def build_playlist(file_name: str, duration_ms: int = 5000,
                   environment: Optional[Dict] = None) -> Dict:
    items = [{
        "file_name": file_name,
        "start_frame": 0, "end_frame": -1, "repeat": 1,
        "speed_factor": 1.0, "start_time_offset": 0,
        "duration_ms": duration_ms,
    }]
    env_items = []
    if environment:
        env_items.append({
            "type": "manual",
            "content": environment.get("room", "Room"),
            "start_time_offset": 0, "duration_ms": duration_ms,
            "data_offset_sec": 0.0, "data_end_sec": 0.0,
            "activity_label": environment.get("activity_label", ""),
            "dataset_source": "manual",
            "temperature": environment.get("temperature"),
            "humidity": environment.get("humidity"),
            "co2": environment.get("co2"),
            "light": environment.get("light"),
            "sound_event": environment.get("sound_event"),
            "time_of_day": environment.get("time_of_day"),
            "duration_min": environment.get("duration_min"),
            "entry_context": environment.get("entry_context"),
            "tv_on": environment.get("tv_on"),
            "motion_detected": environment.get("motion_detected"),
        })
    return {
        "items": items, "environment_items": env_items,
        "target_ip": TARGET_IP, "target_port": TARGET_PORT,
        "protocol": "tcp", "interval_ms": 33, "loop_playlist": False,
    }


# ─────────────────────────────────────────────────────────────
# Evaluation Runner
# ─────────────────────────────────────────────────────────────
class EvaluationRunner:
    """
    Runs the full evaluation across all categories / scenarios.
    Emits SSE events for real-time UI updates.
    """

    def __init__(self, sim_port: int = DEFAULT_SIM_PORT,
                 nomi_port: int = DEFAULT_NOMI_PORT,
                 use_judge: bool = True):
        self.sim = SimulatorClient(sim_port)
        self.nomi = NomiHostClient(nomi_port)
        self.judge = LLMJudge() if use_judge else None
        self._running = False
        self._cancel = False
        self._full_results: Dict = {}

    @property
    def is_running(self) -> bool:
        return self._running

    def cancel(self):
        self._cancel = True

    # ── Play & collect one inference ─────────────────────────

    def _run_single(
        self,
        file_name: str,
        duration_ms: int,
        environment: Optional[Dict],
        skeleton_only: bool = False,
    ) -> Dict:
        """
        Play one skeleton file and collect Nomi inference result.
        environment:
          - None            → pure skeleton, no context
          - location-only dict (room/time_of_day/duration_min) → Phase A
          - full env dict   → Phase B (all sensors + location + time)
        skeleton_only=True  → (legacy) force LLM to ignore all env data
        skeleton_only=False → LLM uses whatever env data is in the playlist
        """
        result: Dict[str, Any] = {
            "label": None, "analysis": None,
            "environment_impact": None, "safety_flag": None, "error": None,
        }
        start_time = time.time()
        # Phase A: location+time context only (sensors stripped by caller)
        # Phase B: full environment overlay
        playlist = build_playlist(file_name, duration_ms, None if skeleton_only else environment)
        try:
            self.sim.start_playlist(playlist)
        except Exception as e:
            result["error"] = str(e)
            return result

        done = self.sim.wait_done(timeout=PLAYLIST_TIMEOUT)
        if not done:
            self.sim.stop_playlist()
            result["error"] = "timeout"
            return result

        time.sleep(POST_PLAY_WAIT)
        end_time = time.time()

        try:
            # member_id=-1 = broad search across all events in this time window
            inf = self.nomi.analyze(-1, start_time, end_time, skeleton_only=skeleton_only)
            if "error" in inf:
                result["error"] = inf["error"]
            else:
                result["label"] = inf.get("summary", "N/A")
                result["analysis"] = inf.get("detail", "")
                result["environment_impact"] = inf.get("environment_impact", "")
                result["safety_flag"] = inf.get("safety_flag")
        except Exception as e:
            result["error"] = str(e)

        result["duration_sec"] = round(end_time - start_time, 1)
        result["skeleton_only"] = skeleton_only
        return result

    # ── Main evaluation loop ─────────────────────────────────

    async def run_full(self, scenarios_data: Dict,
                       runs_override: Optional[int] = None
                       ) -> AsyncGenerator[str, None]:
        self._running = True
        self._cancel = False

        categories = scenarios_data.get("categories", [])
        cfg = scenarios_data.get("config", {})
        runs_per = runs_override or cfg.get("runs_per_scenario", 3)
        duration_ms = cfg.get("duration_ms", 5000)

        total_scenarios = sum(len(c.get("scenarios", [])) for c in categories)

        yield self._sse("eval_start", {
            "total_categories": len(categories),
            "total_scenarios": total_scenarios,
            "runs_per_scenario": runs_per,
            "total_runs": total_scenarios * runs_per * 2,  # ×2 for A/B
        })

        all_category_results: List[Dict] = []

        for cat_idx, cat in enumerate(categories):
            if self._cancel:
                yield self._sse("eval_cancelled", {})
                break

            cat_id = cat["id"]
            cat_name = cat["name"]
            scenarios = cat.get("scenarios", [])

            yield self._sse("category_start", {
                "index": cat_idx, "id": cat_id, "name": cat_name,
                "scenario_count": len(scenarios), "color": cat.get("color", "#333"),
            })

            category_result: Dict[str, Any] = {
                "category_id": cat_id,
                "category_name": cat_name,
                "color": cat.get("color", "#333"),
                "scenarios": [],
            }

            for sc_idx, sc in enumerate(scenarios):
                if self._cancel:
                    yield self._sse("eval_cancelled", {})
                    break

                sc_id = sc["id"]
                sc_name = sc["name"]
                action_code = sc["skeleton_action"]
                # Environment variants: each run picks a random variant
                variants = sc.get("env_variants")
                # Fallback: legacy single-env format
                fallback_gt = sc.get("ground_truth", "")
                fallback_env = sc.get("environment", {})
                # Collect all unique GTs for display
                all_gts = [v["ground_truth"] for v in variants] if variants else [fallback_gt]

                yield self._sse("scenario_start", {
                    "cat_index": cat_idx, "sc_index": sc_idx,
                    "id": sc_id, "name": sc_name,
                    "action_code": "+".join(action_code) if isinstance(action_code, list) else action_code,
                    "ground_truth": " / ".join(dict.fromkeys(all_gts)),
                    "runs": runs_per,
                })

                # Pick N skeleton files
                files = await asyncio.to_thread(
                    pick_skeleton_files, self.sim, action_code, runs_per)
                ac_display = "+".join(action_code) if isinstance(action_code, list) else action_code
                if not files:
                    yield self._sse("scenario_done", {
                        "id": sc_id, "name": sc_name,
                        "error": f"No skeleton files for {ac_display}",
                    })
                    category_result["scenarios"].append({
                        "id": sc_id, "name": sc_name,
                        "error": f"No skeleton files for {ac_display}",
                        "runs": [],
                    })
                    continue

                # Pad if fewer files than requested
                while len(files) < runs_per:
                    files.append(files[0])

                # Pre-assign variants for each run using round-robin cycle.
                # This guarantees every variant appears equally (or ±1) across runs:
                #   runs=6, variants=3 → each variant appears exactly 2 times
                #   runs=5, variants=3 → variants 0,1 appear 2×, variant 2 appears 1×
                # The cycle starts at a random offset each evaluation for variety.
                import random as _rng
                if variants:
                    nv = len(variants)
                    offset = _rng.randint(0, nv - 1)      # random starting variant
                    # Build full cycles, then truncate to runs_per
                    cycle = [(offset + i) % nv for i in range(runs_per)]
                    # Light shuffle within each cycle-block so order isn't always identical
                    block_size = nv
                    shuffled: List[int] = []
                    pos = 0
                    while pos < len(cycle):
                        block = cycle[pos:pos + block_size]
                        _rng.shuffle(block)
                        shuffled.extend(block)
                        pos += block_size
                    run_variants = shuffled[:runs_per]
                else:
                    run_variants = [None] * runs_per

                runs_data: List[Dict] = []
                for run_i in range(runs_per):
                    if self._cancel:
                        break
                    fn = files[run_i]

                    # Pick environment variant for this run
                    vi = run_variants[run_i]
                    if vi is not None and variants:
                        variant = variants[vi]
                        env_data = variant["environment"]
                        gt = variant["ground_truth"]
                        variant_label = variant.get("label", "")
                    else:
                        env_data = fallback_env
                        gt = fallback_gt
                        variant_label = ""

                    # ── Phase A: 純骨架（完全無環境資料） ──
                    yield self._sse("run_progress", {
                        "sc_id": sc_id, "run": run_i + 1,
                        "phase": "A", "desc": "純骨架動作辨識（無環境資料）", "file": fn,
                    })
                    result_a = await asyncio.to_thread(
                        self._run_single, fn, duration_ms, None, True)
                    await asyncio.sleep(1.5)

                    # ── Phase B: skeleton + full environment (sensors + location + time) ──
                    yield self._sse("run_progress", {
                        "sc_id": sc_id, "run": run_i + 1,
                        "phase": "B", "desc": "骨架+完整環境（含感測器）", "file": fn,
                    })
                    result_b = await asyncio.to_thread(
                        self._run_single, fn, duration_ms, env_data, False)
                    await asyncio.sleep(1.5)

                    # ── Scoring: rule-based + LLM semantic judge ──
                    label_a = result_a.get("label") or ""
                    label_b = result_b.get("label") or ""

                    if self.judge and self.judge.enabled:
                        yield self._sse("run_progress", {
                            "sc_id": sc_id, "run": run_i + 1,
                            "phase": "judge", "desc": "LLM 語意評審中",
                        })
                        score_a, reason_a = await asyncio.to_thread(
                            self.judge.score_label, label_a, gt)
                        score_b, reason_b = await asyncio.to_thread(
                            self.judge.score_label, label_b, gt)
                    else:
                        score_a = label_score(label_a, gt)
                        score_b = label_score(label_b, gt)
                        reason_a = reason_b = "rule_based"

                    judge_mode = "combined" if (self.judge and self.judge.enabled) else "rule_based"
                    verdict_a = {
                        "label_correct": score_a >= 0.8,
                        "partial_match": 0.3 <= score_a < 0.8,
                        "judge_mode": judge_mode,
                        "explanation": reason_a,
                    }
                    verdict_b = {
                        "label_correct": score_b >= 0.8,
                        "partial_match": 0.3 <= score_b < 0.8,
                        "judge_mode": judge_mode,
                        "explanation": reason_b,
                    }

                    run_row = {
                        "run_index": run_i,
                        "file_name": fn,
                        "variant_label": variant_label,
                        "ground_truth": gt,
                        "no_env": {
                            "label": label_a,
                            "ground_truth": gt,
                            "analysis": (result_a.get("analysis") or "")[:300],
                            "environment_impact": result_a.get("environment_impact", ""),
                            "safety_flag": result_a.get("safety_flag"),
                            "error": result_a.get("error"),
                            "score": score_a,
                            "correct": score_a >= 0.8,
                            "partial": 0.3 <= score_a < 0.8,
                            "reasoning_quality": verdict_a.get("reasoning_quality"),
                            "env_utilized": verdict_a.get("env_utilized"),
                            "safety_appropriate": verdict_a.get("safety_appropriate"),
                            "explanation": verdict_a.get("explanation", ""),
                        },
                        "with_env": {
                            "label": label_b,
                            "ground_truth": gt,
                            "analysis": (result_b.get("analysis") or "")[:300],
                            "environment_impact": result_b.get("environment_impact", ""),
                            "safety_flag": result_b.get("safety_flag"),
                            "error": result_b.get("error"),
                            "score": score_b,
                            "correct": score_b >= 0.8,
                            "partial": 0.3 <= score_b < 0.8,
                            "reasoning_quality": verdict_b.get("reasoning_quality"),
                            "env_utilized": verdict_b.get("env_utilized"),
                            "safety_appropriate": verdict_b.get("safety_appropriate"),
                            "explanation": verdict_b.get("explanation", ""),
                        },
                    }
                    runs_data.append(run_row)

                    yield self._sse("run_done", {
                        "sc_id": sc_id, "run": run_i + 1,
                        "score_a": score_a, "score_b": score_b,
                        "correct_a": score_a >= 0.8, "correct_b": score_b >= 0.8,
                        "partial_a": 0.3 <= score_a < 0.8, "partial_b": 0.3 <= score_b < 0.8,
                        "label_a": label_a, "label_b": label_b,
                        "gt": gt, "variant_label": variant_label,
                    })
                    await asyncio.sleep(1.0)

                # ── Per-scenario summary ──
                sc_summary = self._scenario_summary(sc, runs_data)
                category_result["scenarios"].append(sc_summary)

                yield self._sse("scenario_done", sc_summary)

            # ── Per-category summary ──
            cat_summary = self._category_summary(category_result)
            category_result["summary"] = cat_summary
            all_category_results.append(category_result)

            yield self._sse("category_done", {
                "id": cat_id, "name": cat_name, "summary": cat_summary,
            })

        # ── Overall ──
        overall = self._overall_summary(all_category_results)
        self._full_results = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "runs_per_scenario": runs_per,
                "duration_ms": duration_ms,
                "judge_enabled": self.judge.enabled if self.judge else False,
                "judge_calls": self.judge.call_count if self.judge else 0,
            },
            "categories": all_category_results,
            "overall": overall,
        }
        yield self._sse("eval_complete", self._full_results)
        self._running = False

    # ── Summary helpers ──────────────────────────────────────

    @staticmethod
    def _scenario_summary(sc: Dict, runs: List[Dict]) -> Dict:
        import statistics
        n = len(runs)
        # Multi-tier scores per run: 0.0 ~ 1.0
        scores_a = [r["no_env"].get("score", 1.0 if r["no_env"].get("correct") else 0.0) for r in runs]
        scores_b = [r["with_env"].get("score", 1.0 if r["with_env"].get("correct") else 0.0) for r in runs]

        rq_a = [r["no_env"]["reasoning_quality"] for r in runs if r["no_env"].get("reasoning_quality") is not None]
        rq_b = [r["with_env"]["reasoning_quality"] for r in runs if r["with_env"].get("reasoning_quality") is not None]
        env_used = sum(1 for r in runs if r["with_env"].get("env_utilized") is True)

        # Accuracy: mean of tiered scores (0-100)
        acc_a = round(sum(scores_a) / n * 100, 1) if n else 0
        acc_b = round(sum(scores_b) / n * 100, 1) if n else 0

        # Robustness: measure consistency across runs using std dev
        # Lower std dev = more consistent = higher robustness
        # consistency = 1 - (std_dev / 0.5)  [0.5 is max possible std dev for 0/0.5/1 space]
        # Clamp to [0, 1]
        std_a = round(statistics.stdev(scores_a), 3) if n > 1 else 0.0
        std_b = round(statistics.stdev(scores_b), 3) if n > 1 else 0.0
        robustness_a = round(max(0.0, 1.0 - std_a / 0.5) * 100, 1)
        robustness_b = round(max(0.0, 1.0 - std_b / 0.5) * 100, 1)

        # Full/partial breakdown (thresholds aligned with multi-tier scoring)
        exact_a  = sum(1 for s in scores_a if s >= 0.8)
        partial_a = sum(1 for s in scores_a if 0.3 <= s < 0.8)
        miss_a   = sum(1 for s in scores_a if s < 0.3)
        exact_b  = sum(1 for s in scores_b if s >= 0.8)
        partial_b = sum(1 for s in scores_b if 0.3 <= s < 0.8)
        miss_b   = sum(1 for s in scores_b if s < 0.3)

        # Collect all unique GTs across runs (variant system)
        run_gts = list(dict.fromkeys(r.get("ground_truth", "") for r in runs))
        gt_display = " / ".join(run_gts) if run_gts else sc.get("ground_truth", "")

        return {
            "id": sc["id"],
            "name": sc["name"],
            "ground_truth": gt_display,
            "runs": runs,
            "total_runs": n,
            # Accuracy (tiered, 0-100)
            "accuracy_no_env": acc_a,
            "accuracy_with_env": acc_b,
            "accuracy_delta": round(acc_b - acc_a, 1),
            # Robustness consistency (0-100, higher = more stable across runs)
            "robustness_no_env": robustness_a,
            "robustness_with_env": robustness_b,
            "std_no_env": std_a,
            "std_with_env": std_b,
            # Per-run score lists (for chart rendering)
            "scores_no_env": scores_a,
            "scores_with_env": scores_b,
            # Breakdown
            "breakdown_no_env":  {"exact": exact_a,  "partial": partial_a,  "miss": miss_a},
            "breakdown_with_env": {"exact": exact_b, "partial": partial_b, "miss": miss_b},
            "avg_quality_no_env": round(sum(rq_a) / len(rq_a), 2) if rq_a else None,
            "avg_quality_with_env": round(sum(rq_b) / len(rq_b), 2) if rq_b else None,
            "env_utilized_count": env_used,
        }

    @staticmethod
    def _category_summary(cat_result: Dict) -> Dict:
        scenarios = cat_result.get("scenarios", [])
        valid = [s for s in scenarios if "error" not in s]
        if not valid:
            return {"accuracy_no_env": 0, "accuracy_with_env": 0, "delta": 0, "robustness_no_env": 0, "robustness_with_env": 0}
        acc_a = round(sum(s["accuracy_no_env"] for s in valid) / len(valid), 1)
        acc_b = round(sum(s["accuracy_with_env"] for s in valid) / len(valid), 1)
        rob_a = round(sum(s["robustness_no_env"] for s in valid) / len(valid), 1)
        rob_b = round(sum(s["robustness_with_env"] for s in valid) / len(valid), 1)
        return {
            "accuracy_no_env": acc_a,
            "accuracy_with_env": acc_b,
            "delta": round(acc_b - acc_a, 1),
            "robustness_no_env": rob_a,
            "robustness_with_env": rob_b,
            "scenario_count": len(valid),
        }

    @staticmethod
    def _overall_summary(categories: List[Dict]) -> Dict:
        all_sc = []
        for c in categories:
            for s in c.get("scenarios", []):
                if "error" not in s:
                    all_sc.append(s)
        if not all_sc:
            return {}
        total_runs = sum(s["total_runs"] for s in all_sc)
        # Use tiered scores for overall accuracy
        total_score_a = sum(sum(s.get("scores_no_env", [])) for s in all_sc)
        total_score_b = sum(sum(s.get("scores_with_env", [])) for s in all_sc)
        # Overall robustness = average of per-scenario robustness
        avg_rob_a = round(sum(s.get("robustness_no_env", 0) for s in all_sc) / len(all_sc), 1)
        avg_rob_b = round(sum(s.get("robustness_with_env", 0) for s in all_sc) / len(all_sc), 1)
        return {
            "total_scenarios": len(all_sc),
            "total_runs": total_runs,
            "overall_accuracy_no_env": round(total_score_a / total_runs * 100, 1) if total_runs else 0,
            "overall_accuracy_with_env": round(total_score_b / total_runs * 100, 1) if total_runs else 0,
            "overall_delta": round((total_score_b - total_score_a) / total_runs * 100, 1) if total_runs else 0,
            "overall_robustness_no_env": avg_rob_a,
            "overall_robustness_with_env": avg_rob_b,
        }

    @staticmethod
    def _sse(event: str, data: Any) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# ─────────────────────────────────────────────────────────────
# Rescore existing results with current label_score tables
# ─────────────────────────────────────────────────────────────
def rescore_results(results: Dict, use_llm: bool = True) -> Dict:
    """Re-score all runs using rule-based + LLM semantic judge.

    When `use_llm=True` (default), low-confidence items (rule-based < 0.9)
    are re-evaluated by the LLM Judge for better semantic matching.
    Returns a deep copy with updated scores and summaries.
    """
    import copy
    import statistics as _stats

    rescored = copy.deepcopy(results)

    # Initialize LLM client for semantic scoring (if available)
    client = None
    model_name = None
    if use_llm and HAS_GENAI:
        api_key = GEMINI_API_KEY
        model_name = GEMINI_JUDGE_MODEL or GEMINI_MODEL_NAME or "gemini-2.0-flash"
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                logger.info(f"Rescore: LLM Judge enabled (model={model_name})")
            except Exception as e:
                logger.warning(f"Rescore: LLM Judge init failed: {e}")

    llm_calls = 0

    for cat in rescored.get("categories", []):
        for sc in cat.get("scenarios", []):
            runs = sc.get("runs", [])
            scores_a: list[float] = []
            scores_b: list[float] = []

            for run in runs:
                gt = run.get("ground_truth", "")

                # — Phase A (no_env) —
                ne = run["no_env"]
                if ne.get("error"):
                    s_a = 0.0
                    reason_a = "error"
                else:
                    s_a, reason_a = combined_label_score(
                        ne.get("label", ""), gt, client, model_name
                    )
                    if "LLM" in reason_a:
                        llm_calls += 1
                ne["score"] = s_a
                ne["correct"] = s_a >= 0.8
                ne["partial"] = 0.3 <= s_a < 0.8
                ne["explanation"] = reason_a
                scores_a.append(s_a)

                # — Phase B (with_env) —
                we = run["with_env"]
                if we.get("error"):
                    s_b = 0.0
                    reason_b = "error"
                else:
                    s_b, reason_b = combined_label_score(
                        we.get("label", ""), gt, client, model_name
                    )
                    if "LLM" in reason_b:
                        llm_calls += 1
                we["score"] = s_b
                we["correct"] = s_b >= 0.8
                we["partial"] = 0.3 <= s_b < 0.8
                we["explanation"] = reason_b
                scores_b.append(s_b)

            n = len(runs)
            if n == 0:
                continue

            sc["scores_no_env"] = scores_a
            sc["scores_with_env"] = scores_b
            acc_a = round(sum(scores_a) / n * 100, 1)
            acc_b = round(sum(scores_b) / n * 100, 1)
            sc["accuracy_no_env"] = acc_a
            sc["accuracy_with_env"] = acc_b
            sc["accuracy_delta"] = round(acc_b - acc_a, 1)

            std_a = round(_stats.stdev(scores_a), 3) if n > 1 else 0.0
            std_b = round(_stats.stdev(scores_b), 3) if n > 1 else 0.0
            sc["robustness_no_env"] = round(max(0.0, 1.0 - std_a / 0.5) * 100, 1)
            sc["robustness_with_env"] = round(max(0.0, 1.0 - std_b / 0.5) * 100, 1)
            sc["std_no_env"] = std_a
            sc["std_with_env"] = std_b

            sc["breakdown_no_env"] = {
                "exact": sum(1 for s in scores_a if s >= 0.8),
                "partial": sum(1 for s in scores_a if 0.3 <= s < 0.8),
                "miss": sum(1 for s in scores_a if s < 0.3),
            }
            sc["breakdown_with_env"] = {
                "exact": sum(1 for s in scores_b if s >= 0.8),
                "partial": sum(1 for s in scores_b if 0.3 <= s < 0.8),
                "miss": sum(1 for s in scores_b if s < 0.3),
            }

        cat["summary"] = EvaluationRunner._category_summary(cat)

    rescored["overall"] = EvaluationRunner._overall_summary(
        rescored.get("categories", [])
    )
    rescored["rescore_info"] = {
        "llm_enabled": client is not None,
        "llm_calls": llm_calls,
        "model": model_name if client else None,
    }
    logger.info(f"Rescore complete: {llm_calls} LLM calls")
    return rescored


# ─────────────────────────────────────────────────────────────
# Scenarios / Results I/O
# ─────────────────────────────────────────────────────────────
def load_scenarios(path: Optional[str] = None) -> Dict:
    p = Path(path) if path else SCENARIO_FILE
    if not p.exists():
        return {"categories": [], "config": {}}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_scenarios(data: Dict, path: Optional[str] = None):
    p = Path(path) if path else SCENARIO_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_saved_results() -> List[Dict]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(RESULTS_DIR.glob("*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            files.append({
                "filename": f.name, "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "record_count": len(data.get("categories", [])),
            })
        except Exception:
            files.append({"filename": f.name, "path": str(f), "error": True})
    return files


def save_evaluation_results(results: Dict) -> str:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"eval_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    return str(path)


def load_result_file(filename: str) -> Any:
    path = RESULTS_DIR / filename
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
