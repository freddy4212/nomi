import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

class Orange4HomeService:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.df = None
        self.days = []
        self.activity_tags = []
        self.activity_list = []
        # Pre-load or lazy load? CSV is 700k lines, maybe 50MB. Loads fine in memory.
        self._load_data()

    def _load_data(self):
        csv_file = self.dataset_path / "o4h_all_events.csv"
        if not csv_file.exists():
            logger.error(f"O4H CSV not found at {csv_file}")
            return

        try:
            # Columns: Time, ItemName, Value
            # Parse dates
            self.df = pd.read_csv(csv_file)
            self.df['Time'] = pd.to_datetime(self.df['Time'])
            self.df = self.df.sort_values('Time')
            
            # Extract unique days for asset listing
            self.days = self.df['Time'].dt.date.unique().tolist()
            self.days.sort()

            # Extract activity labels from "label" stream
            label_rows = self.df[self.df['ItemName'].astype(str).str.lower() == 'label']
            tags = set()
            for raw in label_rows['Value'].astype(str).tolist():
                parsed = self.parse_activity_label(raw)
                if parsed and parsed.get("tag"):
                    tags.add(parsed["tag"])
            self.activity_tags = sorted(tags)

            # Build structured activity list grouped by room
            seen = {}
            for raw in label_rows['Value'].astype(str).tolist():
                parsed = self.parse_activity_label(raw)
                if parsed and parsed.get("tag") and parsed["tag"] not in seen:
                    seen[parsed["tag"]] = parsed
            self.activity_list = sorted(seen.values(), key=lambda x: (x.get("room") or "", x.get("activity") or ""))
            
            logger.info(f"Loaded O4H dataset. {len(self.df)} events. {len(self.days)} unique days.")
        except Exception as e:
            logger.error(f"Failed to load O4H dataset: {e}")
            self.activity_list = []

    def get_days(self) -> List[str]:
        return [d.strftime("%Y-%m-%d") for d in self.days]

    def get_activity_tags(self) -> List[str]:
        return list(self.activity_tags)

    def get_activity_list(self) -> List[Dict[str, Any]]:
        """Return structured activity list with room and activity fields."""
        return [
            {"tag": a["tag"], "room": a.get("room", ""), "activity": a.get("activity", "")}
            for a in self.activity_list
        ]

    def get_activity_list_grouped(self) -> Dict[str, List[str]]:
        """Return activities grouped by room: { room: [activity, ...] }"""
        groups: Dict[str, List[str]] = {}
        for a in self.activity_list:
            room = a.get("room") or "Unknown"
            act = a.get("activity") or ""
            if room not in groups:
                groups[room] = []
            if act and act not in groups[room]:
                groups[room].append(act)
        # Sort activities within each room
        for room in groups:
            groups[room].sort()
        return dict(sorted(groups.items()))

    def get_activity_segments(
        self,
        room_filter: Optional[str] = None,
        activity_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Parse START/STOP label pairs to produce concrete activity time segments.
        Each segment has: room, activity, tag, date, start_sec, end_sec, duration_sec.
        These can be used to query real sensor data for that exact time window.
        """
        if self.df is None:
            return []

        label_rows = self.df[
            self.df['ItemName'].astype(str).str.lower() == 'label'
        ].copy().sort_values('Time')

        # Build START/STOP pairs per (day, tag)
        pending: Dict[str, Any] = {}  # key = (date_str, tag) -> start row
        segments: List[Dict[str, Any]] = []

        for _, row in label_rows.iterrows():
            raw = str(row['Value']).strip()
            parsed = self.parse_activity_label(raw)
            if not parsed.get('tag'):
                continue

            tag = parsed['tag']
            room = parsed.get('room', '')
            activity = parsed.get('activity', '')
            phase = parsed.get('phase')
            ts = row['Time']
            date_str = ts.date().isoformat()
            key = (date_str, tag)

            midnight = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            offset_sec = (ts - midnight).total_seconds()

            if phase == 'START':
                pending[key] = {
                    'room': room, 'activity': activity, 'tag': tag,
                    'date': date_str,
                    'start_sec': offset_sec,
                }
            elif phase == 'STOP' and key in pending:
                seg = pending.pop(key)
                seg['end_sec'] = offset_sec
                seg['duration_sec'] = max(1.0, offset_sec - seg['start_sec'])
                segments.append(seg)

        # Apply filters
        if room_filter:
            rf = room_filter.lower()
            segments = [s for s in segments if rf in s['room'].lower()]
        if activity_filter:
            af = activity_filter.lower()
            segments = [s for s in segments if af in s['activity'].lower()]

        # Sort by room > activity > date
        segments.sort(key=lambda s: (s['room'], s['activity'], s['date'], s['start_sec']))
        return segments

    def parse_activity_label(self, raw: str) -> Dict[str, Any]:
        value = str(raw or "").strip()
        if not value:
            return {}

        phase = None
        payload = value
        if value.startswith("START:"):
            phase = "START"
            payload = value[len("START:"):]
        elif value.startswith("STOP:"):
            phase = "STOP"
            payload = value[len("STOP:"):]

        if "|" in payload:
            room_raw, act_raw = payload.split("|", 1)
            room = room_raw.strip().replace("_", " ")
            activity = act_raw.strip().replace("_", " ")
            tag = f"{room}|{activity}"
        else:
            room = None
            activity = payload.strip().replace("_", " ")
            tag = activity

        result = {
            "raw": value,
            "phase": phase,
            "room": room,
            "activity": activity,
            "tag": tag,
        }
        return result

    def get_environment_state(self, date_str: str, time_offset_sec: float) -> Dict[str, Any]:
        """
        Get the environment state (latest sensor values) for a specific day + offset.
        offset 0 = start of that day (00:00:00).
        """
        if self.df is None:
            return {}

        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        target_time = datetime.combine(target_date, datetime.min.time()) + timedelta(seconds=time_offset_sec)

        # Optimization: Filter roughly around the target time?
        # Or just use `asof` if we pivot?
        # The data is "events". To get the state at time T, we need the *last known value* for each sensor before or at T.
        
        # Filter for data BEFORE target_time
        # We can optimize this by maintaining a state per day or something.
        # But for simulator, queries are sequential.
        
        # Let's perform a filtering on the whole DF? might be slow (700k rows).
        # Better: Filter by day first.
        day_df = self.df[self.df['Time'].dt.date == target_date]
        
        # Now filter up to target_time
        relevant = day_df[day_df['Time'] <= target_time]
        
        # Group by ItemName and take the last value
        state = relevant.groupby('ItemName')['Value'].last().to_dict()
        
        return self._map_to_nomi_schema(state)

    def _map_to_nomi_schema(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps O4H item names to Nomi EnvironmentData schema.
        Schema: temperature, humidity, co2, light, sound_event, room
        """
        env_data = {
            "temperature": None,
            "humidity": None,
            "co2": None,
            "light": None,
            "sound_event": None,
            "room": None
        }

        # Heuristic mapping based on common sensors
        # We need to decide WHICH room's data to pick if multiple are present?
        # Or maybe the user wants *global* environment? 
        # Nomi schema seems singular: `environment` -> one set of values.
        # So we should probably pick the "Living Room" or dominant room, OR average them?
        # Let's pick "Living Room" as default or the room detected by location sensors (if any).
        
        # For simplicity, let's prioritize Living Room > Kitchen > Bedroom
        
        rooms = ["livingroom", "kitchen", "bedroom", "bathroom", "entrance", "office"]
        
        for r in rooms:
            # Temp
            if f"{r}_temperature" in state:
                env_data["temperature"] = float(state[f"{r}_temperature"])
            elif f"{r}_heater_temperature" in state: # fallbacks
                 env_data["temperature"] = float(state[f"{r}_heater_temperature"])
            
            # Humidity
            if f"{r}_humidity" in state:
                env_data["humidity"] = float(state[f"{r}_humidity"])
            
            # CO2
            if f"{r}_CO2" in state:
                env_data["co2"] = float(state[f"{r}_CO2"])
            
            # Light / Luminosity
            if f"{r}_luminosity" in state:
                env_data["light"] = float(state[f"{r}_luminosity"])
            elif f"{r}_light" in state:
                 env_data["light"] = float(state[f"{r}_light"])

            # Noise -> sound_event?
            # Noise is float. sound_event is string.
            # Maybe map high noise to "noise"?
            
            # Break if we found specific room data? 
            # The issue is O4H has data for ALL rooms simultaneously.
            # We assume the "Location Tag" sets the room context.
            # If no location tag, we might default to one.
            pass
            
        # Refined Logic:
        # If the user drags a "Location Tag" (e.g. Kitchen), we filter for that room.
        # This service method should probably accept a `room_filter`.
        
        return env_data

    def get_state_for_room(self, date_str: str, time_offset_sec: float, room: str = "livingroom") -> Dict[str, Any]:
        if self.df is None: return {}
        
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        target_time = datetime.combine(target_date, datetime.min.time()) + timedelta(seconds=time_offset_sec)
        
        # Filter strictly by day and time
        # To speed up, we can cache the day's dataframe
        mask = (self.df['Time'].dt.date == target_date) & (self.df['Time'] <= target_time)
        relevant = self.df.loc[mask]
        
        # Get only items starting with room name or global
        # item name ex: "livingroom_temperature"
        
        # Filter by room prefix
        # "global_" items might be useful too?
        
        # We need efficient lookup.
        # Let's just get everything and filter in python dict
        state = relevant.groupby('ItemName')['Value'].last().to_dict()
        
        env_data = {
            "temperature": None,
            "humidity": None,
            "co2": None,
            "light": None,
            "sound_event": None,
            "room": room
        }
        
        # Room specific keys
        r = room.lower().replace(" ", "")
        
        # Temp
        if f"{r}_temperature" in state:
            env_data["temperature"] = float(state[f"{r}_temperature"])
        
        # Humidity
        if f"{r}_humidity" in state:
            env_data["humidity"] = float(state[f"{r}_humidity"])
            
        # CO2
        if f"{r}_CO2" in state: # Note: CSV uses "CO2" (case sensitive?) grep showed "CO2"
             env_data["co2"] = float(state[f"{r}_CO2"])
             
        # Light
        if f"{r}_luminosity" in state:
             env_data["light"] = float(state[f"{r}_luminosity"])
        
        # Check Noise for sound event
        if f"{r}_noise" in state: # "livingroom_table_noise"?
             # grep showed "livingroom_table_noise"
             # also "entrance_noise"
             pass
             
        return env_data

