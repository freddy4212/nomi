import json
from pathlib import Path
from typing import Any, Dict, List

from google import genai
from google.genai import types

from .llm_utils import load_llm_config, parse_llm_response
from .prompts import build_multimodal_prompt, build_skeleton_only_prompt

class ActivityAnalyzer:
    def __init__(self, db_connector):
        self.db = db_connector
        config_path = Path(__file__).resolve().parents[3] / "config.yaml"
        llm_config = load_llm_config(config_path)
        self.api_key = str(llm_config.get("api_key", "")).strip()
        self.model_name = str(llm_config.get("model_name", "gemini-1.5-flash")).strip()
        
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            print("[ActivityAnalyzer] Warning: llm.api_key not found in config.yaml.")
            self.client = None

    async def analyze_period(
        self,
        member_id: int,
        start_time: float,
        end_time: float,
        skeleton_only: bool = False,
    ) -> Dict[str, Any]:
        """
        分析指定成員在時間段內的活動。

        Args:
            member_id: 成員 ID（-1 = 查詢所有人）
            start_time: 開始 Unix 時間戳
            end_time: 結束 Unix 時間戳
            skeleton_only: 若為 True，完全剝除環境資料，LLM 只能依據骨架動作推論
        """
        if not self.client:
            return {"error": "LLM not configured (missing API key)"}

        # Ensure start_time is the earlier one
        actual_start = min(start_time, end_time)
        actual_end = max(start_time, end_time)

        mode_tag = "[Skeleton-Only]" if skeleton_only else "[Skeleton+Env]"
        print(f"[ActivityAnalyzer]{mode_tag} Analyzing member {member_id} from {actual_start} to {actual_end}")

        # 1. Fetch data
        try:
            events = self.db.get_events_in_range(member_id, actual_start, actual_end)
            print(f"[ActivityAnalyzer]{mode_tag} Found {len(events)} events")
        except Exception as e:
             print(f"[ActivityAnalyzer] Query error: {e}")
             return {"error": f"Database query failed: {str(e)}"}
             
        if not events:
            return {"error": "No events found in the specified range"}

        # 2. Format data for prompt
        member_name = events[0].get('member_name', 'Unknown')
        formatted_events = []
        env_summary = {"rooms": set(), "temp_range": [], "humidity_range": [], "co2_range": [], "activity_labels": set(), "sound_events": set()}
        
        for e in events:
            # Handle environment field which might be a JSON string or dict
            env = e.get('environment', {})
            if isinstance(env, str):
                try:
                    env = json.loads(env)
                except:
                    env = {}
            
            # Handle keypoints
            keypoints = e.get('keypoints')
            if isinstance(keypoints, str):
                try:
                    keypoints = json.loads(keypoints)
                except:
                    keypoints = None

            # Build per-event data
            event_data = {
                "time": e['timestamp'].strftime("%Y-%m-%d %H:%M:%S") if hasattr(e['timestamp'], 'strftime') else str(e['timestamp']),
                "action": e.get('action_label', 'unknown'),
                "confidence": round(float(e.get('action_confidence', 0)), 2),
                "duration": f"{e.get('action_duration', 0):.2f}s",
                "motion_magnitude": e.get('motion_magnitude', 0),
                "keypoints": keypoints,
            }
            
            # Only attach environment context when NOT in skeleton-only mode
            if not skeleton_only and env:
                event_env = {}
                if env.get('room'):
                    event_env['room'] = env['room']
                    env_summary['rooms'].add(env['room'])
                if env.get('temperature') is not None:
                    event_env['temperature'] = env['temperature']
                    env_summary['temp_range'].append(float(env['temperature']))
                if env.get('humidity') is not None:
                    event_env['humidity'] = env['humidity']
                    env_summary['humidity_range'].append(float(env['humidity']))
                if env.get('co2') is not None:
                    event_env['co2'] = env['co2']
                    env_summary['co2_range'].append(float(env['co2']))
                if env.get('light') is not None:
                    event_env['light'] = env['light']
                    env_summary.setdefault('light_range', []).append(float(env['light']))
                if env.get('sound_event'):
                    event_env['sound_event'] = env['sound_event']
                    env_summary['sound_events'].add(env['sound_event'])
                if env.get('activity_label'):
                    event_env['activity_label'] = env['activity_label']
                    env_summary['activity_labels'].add(env['activity_label'])
                # ── Critical context fields for time/duration scenarios ──
                if env.get('time_of_day'):
                    event_env['time_of_day'] = env['time_of_day']
                    env_summary.setdefault('time_of_day', set()).add(env['time_of_day'])
                if env.get('duration_min') is not None:
                    event_env['duration_min'] = env['duration_min']
                    env_summary['duration_min'] = env['duration_min']
                if env.get('entry_context'):
                    event_env['entry_context'] = env['entry_context']
                    env_summary['entry_context'] = env['entry_context']
                if env.get('tv_on') is not None:
                    event_env['tv_on'] = env['tv_on']
                    env_summary['tv_on'] = env['tv_on']
                if env.get('motion_detected') is not None:
                    event_env['motion_detected'] = env['motion_detected']
                    env_summary['motion_detected'] = env['motion_detected']
                if event_env:
                    event_data['environment'] = event_env
            
            formatted_events.append(event_data)

        # ── Build prompt ────────────────────────────────────────────────
        if skeleton_only:
            prompt = build_skeleton_only_prompt(formatted_events)
        else:
            prompt = build_multimodal_prompt(formatted_events, env_summary)

        # 3. Call LLM
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    http_options=types.HttpOptions(timeout=60_000),   # 60s
                ),
            )
            parsed = parse_llm_response(response.text, skeleton_only)
            summary = parsed["summary"]
            detail = parsed["detail"]
            env_impact = parsed["environment_impact"]
            safety_flag = parsed["safety_flag"]

            result = {
                "summary": summary,
                "detail": detail,
                "environment_impact": env_impact,
                "event_count": len(events),
                "member_name": member_name,
                "skeleton_only": skeleton_only,
                "period": {
                    "start": formatted_events[0]['time'],
                    "end": formatted_events[-1]['time']
                }
            }
            if safety_flag:
                result["safety_flag"] = safety_flag
            
            env_rooms = list(env_summary['rooms']) if env_summary['rooms'] else ['(none)']
            print(f"[ActivityAnalyzer]{mode_tag} Result: {summary} | Rooms: {env_rooms} | Env impact: {env_impact}")
            
            return result
        except Exception as e:
            return {"error": f"LLM analysis failed: {str(e)}"}

    # 保留既有私有方法名稱，避免外部呼叫端受影響
    @staticmethod
    def _build_skeleton_only_prompt(events: list) -> str:
        return build_skeleton_only_prompt(events)

    # 保留既有私有方法名稱，避免外部呼叫端受影響
    @staticmethod
    def _build_multimodal_prompt(events: list, env_summary: dict) -> str:
        return build_multimodal_prompt(events, env_summary)

