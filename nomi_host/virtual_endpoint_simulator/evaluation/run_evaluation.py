#!/usr/bin/env python3
"""
NOMI Host Evaluation Harness
=============================

自動化評估 nomi_host 的動作辨識準確度：
1. 比較純骨架 vs 骨架+環境資料的推論差異
2. 測試不同動作組合下的魯棒性

使用方式:
    # 確保 nomi_host (port 8000) 和 simulator backend (port 8001) 都已啟動
    python evaluation/run_evaluation.py

    # 指定自訂場景檔
    python evaluation/run_evaluation.py --scenarios evaluation/scenarios.json

    # 只跑 A/B 比較（不跑魯棒性測試）
    python evaluation/run_evaluation.py --mode ab

    # 只跑魯棒性測試
    python evaluation/run_evaluation.py --mode robustness

    # 指定 port
    python evaluation/run_evaluation.py --sim-port 8001 --nomi-port 8000
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

from dotenv import load_dotenv

# Load .env from nomi_host root (two levels up from evaluation/)
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SIMULATOR_URL = "http://127.0.0.1:{port}/api"
DEFAULT_NOMI_URL = "http://127.0.0.1:{port}"
DEFAULT_SIM_PORT = 8001
DEFAULT_NOMI_PORT = 8000
TARGET_IP = "127.0.0.1"
TARGET_PORT = 9527

SCENARIO_FILE = Path(__file__).parent / "scenarios.json"
OUTPUT_DIR = Path(__file__).parent / "results"

# How long to wait for each skeleton clip to play (seconds)
CLIP_PLAY_SECONDS = 5.0
# Polling interval for status check
POLL_INTERVAL = 0.5
# Wait time after playlist finishes before calling inference (let memory layer flush)
POST_PLAY_WAIT = 3.0
# Timeout for waiting playlist to finish
PLAYLIST_TIMEOUT = 60.0


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ENDC = '\033[0m'


def cprint(text: str, color: str = ""):
    print(f"{color}{text}{Colors.ENDC}")


# ---------------------------------------------------------------------------
# LLM as a Judge
# ---------------------------------------------------------------------------

JUDGE_PROMPT_TEMPLATE = """\
你是一位動作辨識系統的評審。請根據以下資訊，判斷系統的推論結果是否正確。
請用繁體中文回答，並嚴格以 JSON 格式輸出。

## 場景描述
- 場景名稱: {scenario_name}
- 動作代碼: {action_code}
- Ground Truth（正確答案）: {ground_truth}
- 場景類別: {category}

## 環境條件
{environment_desc}

## 系統推論結果
- 預測標籤: {predicted_label}
- 分析內容: {analysis}
- 環境影響評估: {environment_impact}
- 安全旗標: {safety_flag}

## 評分標準
請依據以下維度進行評分：

1. **label_correct** (boolean): 預測標籤是否與 Ground Truth 語意一致？
   - 允許同義詞（如「跌倒」=「摔倒」,「用餐」=「吃飯」）
   - 如果預測更具體但包含正確意思也算正確（如「在浴室跌倒」 vs GT「摔倒」→ 正確）
   - 完全不相關的標籤則為錯誤

2. **env_utilized** (boolean): 系統是否有效利用了環境資料？
   - 分析中有沒有提到房間位置、溫度、CO2 等環境因素？
   - 環境資訊有沒有影響最終判斷？（如「浴室跌倒比客廳更危險」）
   - 如果此次沒有提供環境資料，則填 null

3. **safety_appropriate** (boolean): 安全旗標是否合理？
   - 跌倒、打架、胸痛、嘔吐等危險場景應標記安全警告
   - 走路、坐著、閱讀等日常場景不應標記
   - 如果系統沒有輸出安全旗標，根據場景判斷是否該標記

4. **reasoning_quality** (1-5 的整數):
   - 5 = 推理過程完整、邏輯清晰、結合環境做出有洞察力的判斷
   - 4 = 推理正確但缺少一些細節
   - 3 = 基本正確但推理過於簡單
   - 2 = 有部分錯誤推理
   - 1 = 推理完全錯誤或矛盾

5. **explanation** (string): 一句話簡述你的評判理由

## 輸出格式
只輸出 JSON，不要加其他文字：
```json
{{
  "label_correct": true/false,
  "env_utilized": true/false/null,
  "safety_appropriate": true/false,
  "reasoning_quality": 1-5,
  "explanation": "..."
}}
```
"""


class LLMJudge:
    """Use a separate LLM call to evaluate nomi_host inference results."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        self.client = None
        self.enabled = False
        self._call_count = 0

        if not HAS_GENAI:
            cprint("  ⚠️  google-genai not installed, LLM Judge disabled", Colors.YELLOW)
            return
        if not self.api_key:
            cprint("  ⚠️  GEMINI_API_KEY not found, LLM Judge disabled", Colors.YELLOW)
            return

        try:
            self.client = genai.Client(api_key=self.api_key)
            self.enabled = True
            cprint(f"  ✅ LLM Judge initialized (model: {self.model_name})", Colors.GREEN)
        except Exception as e:
            cprint(f"  ⚠️  LLM Judge init failed: {e}", Colors.YELLOW)

    def evaluate(
        self,
        scenario: Dict,
        predicted_label: str,
        analysis: str,
        environment_impact: str,
        safety_flag: Optional[str],
        had_environment: bool,
    ) -> Dict:
        """
        Ask LLM to judge whether the prediction is correct.

        Returns:
            {
                "label_correct": bool,
                "env_utilized": bool | None,
                "safety_appropriate": bool,
                "reasoning_quality": int (1-5),
                "explanation": str,
                "judge_error": str | None,
            }
        """
        # Fallback: use simple label_match if LLM judge is unavailable
        if not self.enabled:
            gt = scenario.get("ground_truth", "")
            return {
                "label_correct": label_match(predicted_label, gt),
                "env_utilized": None,
                "safety_appropriate": None,
                "reasoning_quality": None,
                "explanation": "(LLM Judge unavailable, used string matching)",
                "judge_error": None,
                "judge_mode": "string_match",
            }

        # Build environment description
        env = scenario.get("environment", {})
        if had_environment and env:
            env_lines = []
            for k, v in env.items():
                env_lines.append(f"  - {k}: {v}")
            environment_desc = "\n".join(env_lines)
        else:
            environment_desc = "（此次未提供環境資料）"

        prompt = JUDGE_PROMPT_TEMPLATE.format(
            scenario_name=scenario.get("name", "N/A"),
            action_code=scenario.get("skeleton", {}).get("action_code", "N/A"),
            ground_truth=scenario.get("ground_truth", "N/A"),
            category=scenario.get("category", "N/A"),
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

            # Extract JSON from response (handle ```json ... ``` wrapping)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            verdict = json.loads(text)
            verdict["judge_error"] = None
            verdict["judge_mode"] = "llm"

            # Validate & coerce types
            verdict["label_correct"] = bool(verdict.get("label_correct", False))
            verdict["reasoning_quality"] = max(1, min(5, int(verdict.get("reasoning_quality", 3))))
            if verdict.get("env_utilized") is not None:
                verdict["env_utilized"] = bool(verdict["env_utilized"])
            verdict["safety_appropriate"] = bool(verdict.get("safety_appropriate", True))
            verdict.setdefault("explanation", "")

            return verdict

        except json.JSONDecodeError as e:
            return {
                "label_correct": label_match(predicted_label, scenario.get("ground_truth", "")),
                "env_utilized": None,
                "safety_appropriate": None,
                "reasoning_quality": None,
                "explanation": f"LLM Judge returned invalid JSON: {text[:200]}",
                "judge_error": str(e),
                "judge_mode": "string_match_fallback",
            }
        except Exception as e:
            return {
                "label_correct": label_match(predicted_label, scenario.get("ground_truth", "")),
                "env_utilized": None,
                "safety_appropriate": None,
                "reasoning_quality": None,
                "explanation": f"LLM Judge call failed: {e}",
                "judge_error": str(e),
                "judge_mode": "string_match_fallback",
            }

    @property
    def call_count(self) -> int:
        return self._call_count


# ---------------------------------------------------------------------------
# API Helpers
# ---------------------------------------------------------------------------

class SimulatorAPI:
    """Virtual Endpoint Simulator API client"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def list_actions(self) -> List[Dict]:
        """GET /skeleton/actions → [{action_code, label, count}]"""
        r = requests.get(f"{self.base_url}/skeleton/actions", timeout=10)
        r.raise_for_status()
        return r.json()

    def list_files_by_action(self, action_code: str) -> List[Dict]:
        """GET /skeleton/files/{action_code} → [{file_name, total_frames, ...}]"""
        r = requests.get(f"{self.base_url}/skeleton/files/{action_code}", timeout=10)
        r.raise_for_status()
        return r.json()

    def start_playlist(self, request: Dict) -> Dict:
        """POST /playlist/start"""
        r = requests.post(f"{self.base_url}/playlist/start", json=request, timeout=10)
        r.raise_for_status()
        return r.json()

    def stop_playlist(self) -> Dict:
        """POST /playlist/stop"""
        r = requests.post(f"{self.base_url}/playlist/stop", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_status(self) -> Dict:
        """GET /status"""
        r = requests.get(f"{self.base_url}/status", timeout=10)
        r.raise_for_status()
        return r.json()

    def wait_for_completion(self, timeout: float = PLAYLIST_TIMEOUT) -> bool:
        """Poll status until playlist finishes. Returns True if completed."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                status = self.get_status()
                if not status.get("is_running", False):
                    return True
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)
        return False


class NomiHostAPI:
    """NOMI Host Control Panel API client"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def analyze(self, member_id: int, start_time: float, end_time: float) -> Dict:
        """POST /api/inference/analyze"""
        r = requests.post(
            f"{self.base_url}/api/inference/analyze",
            json={"member_id": member_id, "start_time": start_time, "end_time": end_time},
            timeout=90   # Gemini typically responds in 10-40s
        )
        r.raise_for_status()
        return r.json()

    def health_check(self) -> bool:
        """Check if nomi_host is running"""
        try:
            r = requests.get(f"{self.base_url}/api/status", timeout=5)
            return r.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Evaluation Logic
# ---------------------------------------------------------------------------

def find_skeleton_file(sim: SimulatorAPI, action_code: str) -> Optional[str]:
    """Find one skeleton file for the given action code"""
    try:
        files = sim.list_files_by_action(action_code)
        if files:
            # Pick the first file with reasonable frame count
            for f in files:
                total = f.get("total_frames", 0)
                if total > 10:  # Skip very short clips
                    return f["file_name"]
            return files[0]["file_name"]
    except Exception as e:
        cprint(f"  Warning: Could not find files for {action_code}: {e}", Colors.YELLOW)
    return None


def build_playlist_request(
    file_name: str,
    duration_ms: int = 5000,
    environment: Optional[Dict] = None,
    target_ip: str = TARGET_IP,
    target_port: int = TARGET_PORT,
) -> Dict:
    """Build a PlaylistRequest for one skeleton clip with optional environment"""
    items = [{
        "file_name": file_name,
        "start_frame": 0,
        "end_frame": -1,
        "repeat": 1,
        "speed_factor": 1.0,
        "start_time_offset": 0,
        "duration_ms": duration_ms,
    }]

    env_items = []
    if environment:
        # Use "manual" type to inject arbitrary sensor values
        env_items.append({
            "type": "manual",
            "content": environment.get("room", "Room"),
            "start_time_offset": 0,
            "duration_ms": duration_ms,
            "data_offset_sec": 0.0,
            "data_end_sec": 0.0,
            "activity_label": environment.get("activity_label", ""),
            "dataset_source": "manual",
            "temperature": environment.get("temperature"),
            "humidity": environment.get("humidity"),
            "co2": environment.get("co2"),
            "light": environment.get("light"),
        })

    return {
        "items": items,
        "environment_items": env_items,
        "target_ip": target_ip,
        "target_port": target_port,
        "protocol": "tcp",
        "interval_ms": 33,
        "loop_playlist": False,
    }


def run_single_scenario(
    sim: SimulatorAPI,
    nomi: NomiHostAPI,
    file_name: str,
    duration_ms: int,
    environment: Optional[Dict],
    label: str,
) -> Dict:
    """
    Run a single playlist and collect inference results.
    Returns: {label, analysis, environment_impact, safety_flag, error, timing}
    """
    result = {"label": None, "analysis": None, "environment_impact": None, "safety_flag": None, "error": None}

    # 1. Record start time
    start_time = time.time()

    # 2. Build and send playlist
    playlist = build_playlist_request(file_name, duration_ms, environment)

    # Inject environment data directly into packet if provided
    # (The simulator will send ground_truth from frame_info.action,
    #  and we also want to override the environment for the location-only item)
    if environment:
        pass  # Environment values are injected via "manual" type env item above

    try:
        sim.start_playlist(playlist)
    except Exception as e:
        result["error"] = f"Failed to start playlist: {e}"
        return result

    # 3. Wait for completion
    cprint(f"    ⏳ Playing '{label}'...", Colors.DIM)
    completed = sim.wait_for_completion(timeout=PLAYLIST_TIMEOUT)
    if not completed:
        sim.stop_playlist()
        result["error"] = "Playlist timed out"
        return result

    end_time = time.time()

    # 4. Wait for memory layer to flush
    time.sleep(POST_PLAY_WAIT)

    # 5. Call inference
    try:
        # Use member_id=1 as default (first detected person)
        inference = nomi.analyze(member_id=1, start_time=start_time, end_time=end_time)
        if "error" in inference:
            result["error"] = inference["error"]
        else:
            result["label"] = inference.get("summary", "N/A")
            result["analysis"] = inference.get("detail", "")
            result["environment_impact"] = inference.get("environment_impact", "")
            result["safety_flag"] = inference.get("safety_flag")
            result["event_count"] = inference.get("event_count", 0)
    except Exception as e:
        result["error"] = f"Inference failed: {e}"

    result["duration_sec"] = round(end_time - start_time, 1)
    return result


def label_match(predicted: str, ground_truth: str) -> bool:
    """
    Fuzzy match between predicted label and ground truth.
    Both are in Traditional Chinese, we check if one contains the other.
    """
    if not predicted or not ground_truth:
        return False
    predicted = predicted.strip()
    ground_truth = ground_truth.strip()

    # Exact match
    if predicted == ground_truth:
        return True

    # Containment (e.g., "在廚房料理" contains "料理")
    if ground_truth in predicted or predicted in ground_truth:
        return True

    # Common synonyms
    synonyms = {
        "摔倒": ["跌倒", "倒下", "摔"],
        "打架": ["衝突", "攻擊", "打人", "揮拳"],
        "走路": ["行走", "步行", "走"],
        "站立": ["站著", "站起"],
        "坐著": ["坐下", "就座", "坐"],
        "料理": ["做菜", "烹飪", "煮飯", "做飯"],
        "吃飯": ["用餐", "進食", "吃東西", "吃"],
        "喝水": ["飲水", "喝"],
        "閱讀": ["看書", "讀書"],
        "寫字": ["書寫", "寫作", "工作"],
        "打電話": ["通話", "講電話"],
        "踉蹌": ["不穩", "搖晃", "失去平衡"],
        "嘔吐": ["噁心"],
        "胸痛": ["胸部不適", "胸悶"],
        "拍手": ["鼓掌"],
        "運動": ["伸展", "鍛鍊"],
        "睡覺": ["休息", "躺下"],
    }

    for key, alts in synonyms.items():
        targets = [key] + alts
        pred_match = any(t in predicted for t in targets)
        gt_match = any(t in ground_truth for t in targets)
        if pred_match and gt_match:
            return True

    return False


# ---------------------------------------------------------------------------
# Main Evaluation Runs
# ---------------------------------------------------------------------------

def run_ab_comparison(
    sim: SimulatorAPI,
    nomi: NomiHostAPI,
    scenarios: List[Dict],
    judge: Optional["LLMJudge"] = None,
) -> List[Dict]:
    """
    Run A/B comparison: for each scenario, run once without environment, once with.
    Uses LLM Judge (if available) for semantic correctness evaluation.
    Returns list of result rows.
    """
    results = []

    cprint("\n" + "=" * 70, Colors.BOLD)
    cprint("  Phase 1: A/B Comparison (Skeleton Only vs Skeleton + Environment)", Colors.BOLD)
    cprint("=" * 70, Colors.BOLD)

    for i, scenario in enumerate(scenarios):
        sid = scenario["id"]
        name = scenario["name"]
        action_code = scenario["skeleton"]["action_code"]
        ground_truth = scenario["ground_truth"]

        cprint(f"\n  [{i+1}/{len(scenarios)}] {sid}: {name}", Colors.CYAN)
        cprint(f"    Action: {action_code} | GT: {ground_truth}", Colors.DIM)

        # Find skeleton file
        file_name = find_skeleton_file(sim, action_code)
        if not file_name:
            cprint(f"    ❌ No skeleton file found for {action_code}, skipping", Colors.RED)
            results.append({
                "scenario_id": sid,
                "scenario_name": name,
                "action_code": action_code,
                "ground_truth": ground_truth,
                "category": scenario.get("category", ""),
                "result_no_env": "SKIP",
                "result_with_env": "SKIP",
                "match_no_env": False,
                "match_with_env": False,
                "env_impact": "N/A",
                "safety_flag": None,
                "error": "No skeleton file",
            })
            continue

        cprint(f"    File: {file_name}", Colors.DIM)

        # --- Run A: Without environment ---
        cprint(f"\n    [A] Running WITHOUT environment...", Colors.YELLOW)
        result_a = run_single_scenario(
            sim, nomi, file_name, 5000,
            environment=None,
            label=f"{name} (no env)"
        )

        # Wait a bit between runs
        time.sleep(2.0)

        # --- Run B: With environment ---
        cprint(f"    [B] Running WITH environment...", Colors.GREEN)
        env_data = scenario.get("environment", {})
        result_b = run_single_scenario(
            sim, nomi, file_name, 5000,
            environment=env_data,
            label=f"{name} (with env)"
        )

        # --- Judge results ---
        label_a = result_a.get("label", "N/A")
        label_b = result_b.get("label", "N/A")

        if judge:
            # LLM Judge for Run A (no env)
            cprint(f"    🧑‍⚖️ Judging results...", Colors.DIM)
            verdict_a = judge.evaluate(
                scenario=scenario,
                predicted_label=label_a,
                analysis=result_a.get("analysis", ""),
                environment_impact=result_a.get("environment_impact", ""),
                safety_flag=result_a.get("safety_flag"),
                had_environment=False,
            )
            # LLM Judge for Run B (with env)
            verdict_b = judge.evaluate(
                scenario=scenario,
                predicted_label=label_b,
                analysis=result_b.get("analysis", ""),
                environment_impact=result_b.get("environment_impact", ""),
                safety_flag=result_b.get("safety_flag"),
                had_environment=True,
            )
            match_a = verdict_a["label_correct"]
            match_b = verdict_b["label_correct"]
        else:
            # Fallback to string matching
            match_a = label_match(label_a, ground_truth)
            match_b = label_match(label_b, ground_truth)
            verdict_a = {"judge_mode": "string_match"}
            verdict_b = {"judge_mode": "string_match"}

        status_a = "✅" if match_a else "❌"
        status_b = "✅" if match_b else "❌"
        improvement = ""
        if match_b and not match_a:
            improvement = " 📈 IMPROVED"
        elif not match_b and match_a:
            improvement = " 📉 DEGRADED"
        elif match_b and match_a:
            improvement = " ＝ SAME"

        cprint(f"\n    Results:", Colors.BOLD)
        cprint(f"      GT:      {ground_truth}")
        cprint(f"      No Env:  {label_a} {status_a}", Colors.YELLOW)
        cprint(f"      +Env:    {label_b} {status_b}{improvement}", Colors.GREEN)

        # Show judge details if using LLM
        if judge and verdict_b.get("judge_mode") == "llm":
            rq_a = verdict_a.get("reasoning_quality", "?")
            rq_b = verdict_b.get("reasoning_quality", "?")
            cprint(f"      Reasoning Quality:  A={rq_a}/5  B={rq_b}/5", Colors.CYAN)
            if verdict_b.get("env_utilized") is not None:
                env_used = "Yes" if verdict_b["env_utilized"] else "No"
                cprint(f"      Env Utilized:  {env_used}", Colors.CYAN)
            if verdict_b.get("safety_appropriate") is not None:
                safe_ok = "✅" if verdict_b["safety_appropriate"] else "⚠️ Inappropriate"
                cprint(f"      Safety Check:  {safe_ok}", Colors.CYAN)
            if verdict_b.get("explanation"):
                cprint(f"      Judge:   {verdict_b['explanation']}", Colors.DIM)

        if result_b.get("environment_impact"):
            cprint(f"      Impact:  {result_b['environment_impact']}", Colors.CYAN)
        if result_b.get("safety_flag"):
            cprint(f"      ⚠️ Safety: {result_b['safety_flag']}", Colors.RED)

        results.append({
            "scenario_id": sid,
            "scenario_name": name,
            "action_code": action_code,
            "ground_truth": ground_truth,
            "category": scenario.get("category", ""),
            "result_no_env": label_a,
            "result_with_env": label_b,
            "match_no_env": match_a,
            "match_with_env": match_b,
            "env_impact": result_b.get("environment_impact", ""),
            "safety_flag": result_b.get("safety_flag"),
            "error_a": result_a.get("error"),
            "error_b": result_b.get("error"),
            # LLM Judge details
            "judge_mode": verdict_b.get("judge_mode", "string_match"),
            "judge_a": verdict_a,
            "judge_b": verdict_b,
        })

        # Wait between scenarios
        time.sleep(2.0)

    return results


def run_robustness_test(
    sim: SimulatorAPI,
    nomi: NomiHostAPI,
    sequences: List[Dict],
) -> List[Dict]:
    """
    Run robustness test: play action sequences and check if each action is correctly recognized.
    """
    results = []

    cprint("\n" + "=" * 70, Colors.BOLD)
    cprint("  Phase 2: Robustness Test (Action Sequences)", Colors.BOLD)
    cprint("=" * 70, Colors.BOLD)

    for i, seq in enumerate(sequences):
        sid = seq["id"]
        name = seq["name"]
        actions = seq["actions"]
        expected = seq["expected_labels"]

        cprint(f"\n  [{i+1}/{len(sequences)}] {sid}: {name}", Colors.CYAN)
        cprint(f"    Sequence: {' → '.join(actions)}", Colors.DIM)
        cprint(f"    Expected: {' → '.join(expected)}", Colors.DIM)

        # Build multi-item playlist
        items = []
        total_duration = 0
        clip_duration = 4000  # 4 seconds per clip

        for action_code in actions:
            file_name = find_skeleton_file(sim, action_code)
            if not file_name:
                cprint(f"    ⚠️ No file for {action_code}", Colors.YELLOW)
                continue

            items.append({
                "file_name": file_name,
                "start_frame": 0,
                "end_frame": -1,
                "repeat": 1,
                "speed_factor": 1.0,
                "start_time_offset": total_duration,
                "duration_ms": clip_duration,
            })
            total_duration += clip_duration

        if not items:
            cprint(f"    ❌ No skeleton files found, skipping", Colors.RED)
            continue

        # Record time and play
        start_time = time.time()

        playlist = {
            "items": items,
            "environment_items": [],
            "target_ip": TARGET_IP,
            "target_port": TARGET_PORT,
            "protocol": "tcp",
            "interval_ms": 33,
            "loop_playlist": False,
        }

        try:
            sim.start_playlist(playlist)
        except Exception as e:
            cprint(f"    ❌ Failed to start: {e}", Colors.RED)
            continue

        cprint(f"    ⏳ Playing sequence ({len(items)} clips, {total_duration/1000:.1f}s)...", Colors.DIM)
        completed = sim.wait_for_completion(timeout=total_duration / 1000 + 30)
        if not completed:
            sim.stop_playlist()
            cprint(f"    ❌ Timed out", Colors.RED)
            continue

        end_time = time.time()
        time.sleep(POST_PLAY_WAIT)

        # Get inference for the whole sequence
        try:
            inference = nomi.analyze(member_id=1, start_time=start_time, end_time=end_time)
            overall_label = inference.get("summary", "N/A")
            analysis = inference.get("detail", "")
            cprint(f"\n    Overall inference: {overall_label}", Colors.BOLD)
            if analysis:
                # Truncate long analysis
                short = analysis[:200] + "..." if len(analysis) > 200 else analysis
                cprint(f"    Analysis: {short}", Colors.DIM)
        except Exception as e:
            overall_label = f"Error: {e}"
            analysis = ""

        results.append({
            "sequence_id": sid,
            "sequence_name": name,
            "actions": " → ".join(actions),
            "expected": " → ".join(expected),
            "overall_label": overall_label,
            "analysis_snippet": analysis[:300] if analysis else "",
            "total_clips": len(items),
            "duration_sec": round(end_time - start_time, 1),
        })

        time.sleep(2.0)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_ab_summary(results: List[Dict]):
    """Print summary table for A/B comparison"""
    cprint("\n" + "=" * 70, Colors.BOLD)
    cprint("  A/B COMPARISON SUMMARY", Colors.BOLD + Colors.CYAN)
    cprint("=" * 70, Colors.BOLD)

    total = len(results)
    correct_no_env = sum(1 for r in results if r.get("match_no_env"))
    correct_with_env = sum(1 for r in results if r.get("match_with_env"))
    improved = sum(1 for r in results if r.get("match_with_env") and not r.get("match_no_env"))
    degraded = sum(1 for r in results if not r.get("match_with_env") and r.get("match_no_env"))

    # Table header
    cprint(f"\n  {'Scenario':<25} {'GT':<8} {'No Env':<10} {'+ Env':<10} {'Δ':<8}", Colors.BOLD)
    cprint(f"  {'─' * 65}")

    for r in results:
        gt = r["ground_truth"][:7]
        no_env = r.get("result_no_env", "N/A")[:9]
        with_env = r.get("result_with_env", "N/A")[:9]

        m_a = "✅" if r.get("match_no_env") else "❌"
        m_b = "✅" if r.get("match_with_env") else "❌"

        delta = ""
        if r.get("match_with_env") and not r.get("match_no_env"):
            delta = "📈"
        elif not r.get("match_with_env") and r.get("match_no_env"):
            delta = "📉"
        elif r.get("match_with_env") and r.get("match_no_env"):
            delta = "＝"
        else:
            delta = "✗✗"

        name = r["scenario_name"][:24]
        print(f"  {name:<25} {gt:<8} {no_env} {m_a}  {with_env} {m_b}  {delta}")

    # Summary stats
    skip_count = sum(1 for r in results if r.get("result_no_env") == "SKIP")
    valid = total - skip_count
    
    cprint(f"\n  {'─' * 65}")
    acc_no = f"{correct_no_env}/{valid}" if valid > 0 else "N/A"
    acc_with = f"{correct_with_env}/{valid}" if valid > 0 else "N/A"
    pct_no = f"({correct_no_env/valid*100:.0f}%)" if valid > 0 else ""
    pct_with = f"({correct_with_env/valid*100:.0f}%)" if valid > 0 else ""

    cprint(f"\n  📊 Results ({valid} scenarios tested):", Colors.BOLD)
    cprint(f"     Skeleton Only Accuracy:  {acc_no} {pct_no}", Colors.YELLOW)
    cprint(f"     + Environment Accuracy:  {acc_with} {pct_with}", Colors.GREEN)
    cprint(f"     Improved by env:  {improved}  |  Degraded: {degraded}", Colors.CYAN)

    if valid > 0:
        delta_pct = (correct_with_env - correct_no_env) / valid * 100
        sign = "+" if delta_pct >= 0 else ""
        color = Colors.GREEN if delta_pct > 0 else (Colors.RED if delta_pct < 0 else Colors.DIM)
        cprint(f"     Environment Impact:  {sign}{delta_pct:.1f}%", color)

    # Safety analysis
    safety = [r for r in results if r.get("category") == "safety"]
    if safety:
        safety_correct = sum(1 for r in safety if r.get("match_with_env"))
        flagged = sum(1 for r in safety if r.get("safety_flag"))
        cprint(f"\n  🚨 Safety Scenarios:  {safety_correct}/{len(safety)} correct  |  {flagged} flagged", Colors.RED)

    # LLM Judge metrics (if available)
    judged = [r for r in results if r.get("judge_mode") == "llm"]
    if judged:
        cprint(f"\n  🧑\u200d⚖️ LLM Judge Metrics ({len(judged)} scenarios judged):", Colors.BOLD)

        # Average reasoning quality
        rq_a = [r["judge_a"]["reasoning_quality"] for r in judged if r.get("judge_a", {}).get("reasoning_quality")]
        rq_b = [r["judge_b"]["reasoning_quality"] for r in judged if r.get("judge_b", {}).get("reasoning_quality")]
        if rq_a:
            cprint(f"     Avg Reasoning Quality (no env):   {sum(rq_a)/len(rq_a):.1f}/5", Colors.YELLOW)
        if rq_b:
            cprint(f"     Avg Reasoning Quality (+env):     {sum(rq_b)/len(rq_b):.1f}/5", Colors.GREEN)

        # Environment utilization
        env_used = [r for r in judged if r.get("judge_b", {}).get("env_utilized") is True]
        env_not = [r for r in judged if r.get("judge_b", {}).get("env_utilized") is False]
        cprint(f"     Environment Utilized:  {len(env_used)}/{len(env_used)+len(env_not)}", Colors.CYAN)

        # Safety appropriateness
        safe_ok_a = sum(1 for r in judged if r.get("judge_a", {}).get("safety_appropriate") is True)
        safe_ok_b = sum(1 for r in judged if r.get("judge_b", {}).get("safety_appropriate") is True)
        cprint(f"     Safety Appropriate:  A={safe_ok_a}/{len(judged)}  B={safe_ok_b}/{len(judged)}", Colors.CYAN)


def print_robustness_summary(results: List[Dict]):
    """Print summary for robustness tests"""
    cprint("\n" + "=" * 70, Colors.BOLD)
    cprint("  ROBUSTNESS TEST SUMMARY", Colors.BOLD + Colors.CYAN)
    cprint("=" * 70, Colors.BOLD)

    for r in results:
        cprint(f"\n  {r['sequence_name']}", Colors.BOLD)
        cprint(f"    Sequence:  {r['actions']}", Colors.DIM)
        cprint(f"    Expected:  {r['expected']}", Colors.DIM)
        cprint(f"    Result:    {r['overall_label']}")
        cprint(f"    Duration:  {r['duration_sec']}s ({r['total_clips']} clips)")


def save_results(ab_results: List[Dict], robust_results: List[Dict], output_dir: Path):
    """Save results to CSV and JSON"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save A/B results
    if ab_results:
        # CSV (flat fields for easy spreadsheet viewing)
        csv_path = output_dir / f"ab_comparison_{timestamp}.csv"
        csv_rows = []
        for r in ab_results:
            row = {
                "scenario_id": r.get("scenario_id"),
                "scenario_name": r.get("scenario_name"),
                "action_code": r.get("action_code"),
                "ground_truth": r.get("ground_truth"),
                "category": r.get("category"),
                "result_no_env": r.get("result_no_env"),
                "result_with_env": r.get("result_with_env"),
                "match_no_env": r.get("match_no_env"),
                "match_with_env": r.get("match_with_env"),
                "env_impact": r.get("env_impact"),
                "safety_flag": r.get("safety_flag"),
                "error_a": r.get("error_a"),
                "error_b": r.get("error_b"),
                "judge_mode": r.get("judge_mode", ""),
            }
            # Flatten judge verdicts
            jb = r.get("judge_b", {})
            if jb:
                row["judge_label_correct"] = jb.get("label_correct")
                row["judge_env_utilized"] = jb.get("env_utilized")
                row["judge_safety_ok"] = jb.get("safety_appropriate")
                row["judge_reasoning_q"] = jb.get("reasoning_quality")
                row["judge_explanation"] = jb.get("explanation", "")
            csv_rows.append(row)

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
        cprint(f"\n  💾 A/B results saved to: {csv_path}", Colors.GREEN)

        # JSON (detailed, includes full judge verdicts)
        json_path = output_dir / f"ab_comparison_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(ab_results, f, ensure_ascii=False, indent=2, default=str)

    # Save robustness results
    if robust_results:
        json_path = output_dir / f"robustness_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(robust_results, f, ensure_ascii=False, indent=2)
        cprint(f"  💾 Robustness results saved to: {json_path}", Colors.GREEN)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NOMI Host Evaluation Harness")
    parser.add_argument("--scenarios", type=str, default=str(SCENARIO_FILE),
                        help="Path to scenarios JSON file")
    parser.add_argument("--mode", choices=["all", "ab", "robustness"], default="all",
                        help="Evaluation mode: ab=A/B comparison, robustness=sequence test, all=both")
    parser.add_argument("--sim-port", type=int, default=DEFAULT_SIM_PORT,
                        help="Simulator backend port")
    parser.add_argument("--nomi-port", type=int, default=DEFAULT_NOMI_PORT,
                        help="NOMI Host control panel port")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR),
                        help="Output directory for results")
    parser.add_argument("--no-judge", action="store_true",
                        help="Disable LLM Judge (use simple string matching instead)")

    args = parser.parse_args()

    # Initialize API clients
    sim_url = DEFAULT_SIMULATOR_URL.format(port=args.sim_port)
    nomi_url = DEFAULT_NOMI_URL.format(port=args.nomi_port)
    sim = SimulatorAPI(sim_url)
    nomi = NomiHostAPI(nomi_url)

    cprint("\n" + "=" * 70, Colors.BOLD + Colors.HEADER)
    cprint("  NOMI Host Evaluation Harness", Colors.BOLD + Colors.HEADER)
    cprint("=" * 70, Colors.BOLD + Colors.HEADER)
    cprint(f"  Simulator:  {sim_url}")
    cprint(f"  NOMI Host:  {nomi_url}")
    cprint(f"  Mode:       {args.mode}")

    # Initialize LLM Judge
    judge = None
    if not args.no_judge:
        cprint(f"\n  🧑\u200d⚖️ Initializing LLM Judge...", Colors.DIM)
        judge = LLMJudge()
        if not judge.enabled:
            cprint(f"  ⚠️  LLM Judge unavailable, falling back to string matching", Colors.YELLOW)
            judge = None
        else:
            cprint(f"  Judge mode: LLM (semantic evaluation)", Colors.DIM)
    else:
        cprint(f"\n  Judge mode: string matching (--no-judge)", Colors.DIM)

    # Health checks
    cprint(f"\n  🔍 Checking connectivity...", Colors.DIM)

    try:
        status = sim.get_status()
        cprint(f"  ✅ Simulator: connected (running={status.get('is_running', False)})", Colors.GREEN)
    except Exception as e:
        cprint(f"  ❌ Simulator not reachable at {sim_url}: {e}", Colors.RED)
        cprint(f"     Start it with: cd virtual_endpoint_simulator && bash start.sh", Colors.DIM)
        sys.exit(1)

    nomi_ok = nomi.health_check()
    if nomi_ok:
        cprint(f"  ✅ NOMI Host: connected", Colors.GREEN)
    else:
        cprint(f"  ❌ NOMI Host not reachable at {nomi_url}", Colors.RED)
        cprint(f"     Start it with: cd control_panel && python -m backend.main", Colors.DIM)
        sys.exit(1)

    # Stop any running playlist
    try:
        sim.stop_playlist()
    except Exception:
        pass

    # Load scenarios
    scenario_path = Path(args.scenarios)
    if not scenario_path.exists():
        cprint(f"  ❌ Scenario file not found: {scenario_path}", Colors.RED)
        sys.exit(1)

    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario_data = json.load(f)

    scenarios = scenario_data.get("scenarios", [])
    sequences = scenario_data.get("robustness_sequences", [])

    cprint(f"\n  📋 Loaded {len(scenarios)} scenarios + {len(sequences)} robustness sequences")

    # Check available skeleton actions
    try:
        available_actions = sim.list_actions()
        action_codes = {a["action_code"] for a in available_actions}
        cprint(f"  📁 Available actions: {len(action_codes)} types")
    except Exception as e:
        cprint(f"  ⚠️ Could not list available actions: {e}", Colors.YELLOW)
        action_codes = set()

    # Run evaluations
    ab_results = []
    robust_results = []

    if args.mode in ("all", "ab") and scenarios:
        ab_results = run_ab_comparison(sim, nomi, scenarios, judge=judge)
        print_ab_summary(ab_results)
        if judge:
            cprint(f"\n  🧑\u200d⚖️ LLM Judge API calls: {judge.call_count}", Colors.DIM)

    if args.mode in ("all", "robustness") and sequences:
        robust_results = run_robustness_test(sim, nomi, sequences)
        print_robustness_summary(robust_results)

    # Save results
    output_dir = Path(args.output)
    save_results(ab_results, robust_results, output_dir)

    cprint(f"\n  🏁 Evaluation complete!\n", Colors.BOLD + Colors.GREEN)


if __name__ == "__main__":
    main()
