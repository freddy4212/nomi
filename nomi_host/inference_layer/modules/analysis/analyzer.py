import os
import json
from typing import List, Dict, Any
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ActivityAnalyzer:
    def __init__(self, db_connector):
        self.db = db_connector
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            print("[ActivityAnalyzer] Warning: GEMINI_API_KEY not found.")
            self.model = None

    async def analyze_period(self, member_id: int, start_time: float, end_time: float) -> Dict[str, Any]:
        if not self.model:
            return {"error": "LLM not configured (missing API key)"}

        # Ensure start_time is the earlier one
        actual_start = min(start_time, end_time)
        actual_end = max(start_time, end_time)
        
        print(f"[ActivityAnalyzer] Analyzing member {member_id} from {actual_start} to {actual_end}")

        # 1. Fetch data
        try:
            events = self.db.get_events_in_range(member_id, actual_start, actual_end)
            print(f"[ActivityAnalyzer] Found {len(events)} events")
        except Exception as e:
             print(f"[ActivityAnalyzer] Query error: {e}")
             return {"error": f"Database query failed: {str(e)}"}
             
        if not events:
            return {"error": "No events found in the specified range"}

        # 2. Format data for prompt
        member_name = events[0].get('member_name', 'Unknown')
        formatted_events = []
        for e in events:
            # Handle environment field which might be a JSON string or dict
            env = e.get('environment', {})
            if isinstance(env, str):
                try:
                    env = json.loads(env)
                except:
                    env = {}
            
            formatted_events.append({
                "time": e['timestamp'].strftime("%Y-%m-%d %H:%M:%S") if hasattr(e['timestamp'], 'strftime') else str(e['timestamp']),
                "action": e['action_label'],
                "confidence": f"{e['action_confidence']:.2f}",
                "location": env.get('room', 'Unknown'),
                "duration": f"{e.get('action_duration', 0):.2f}s"
            })
        
        prompt = f"""
        Analyze the following sequence of actions for user "{member_name}".
        
        Data:
        {json.dumps(formatted_events, indent=2, ensure_ascii=False)}
        
        Please provide a concise summary of what the person is doing.
        Focus on the sequence and flow of actions.
        If there are any anomalies or interesting patterns, mention them.
        Respond in Traditional Chinese (zh-TW).
        """

        # 3. Call LLM
        try:
            response = await self.model.generate_content_async(prompt)
            return {
                "summary": response.text,
                "event_count": len(events),
                "member_name": member_name,
                "period": {
                    "start": formatted_events[0]['time'],
                    "end": formatted_events[-1]['time']
                }
            }
        except Exception as e:
            return {"error": f"LLM analysis failed: {str(e)}"}
