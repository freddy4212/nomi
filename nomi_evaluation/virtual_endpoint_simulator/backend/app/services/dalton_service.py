"""
DALTON Dataset Service
======================
Loads indoor air quality sensor data from the DALTON dataset.

DALTON provides per-second environmental readings:
  - T (temperature °C), H (humidity %RH), CO2 (ppm)
  - PMS1, PMS2_5, PMS10 (particulate matter μg/m³)
  - NO2, CO, VoC, C2H5OH (gas sensors)

Each CSV file corresponds to one sensor device deployed at a specific location
within a site (H1=Home1, A1=Apartment1, R1=ResearchLab1, etc.).

Additionally, Metadata/Annotations.csv provides free-text activity labels
timestamped per site.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Columns in raw Data/*.csv
DALTON_COLUMNS = [
    "ts", "T", "H", "PMS1", "PMS2_5", "PMS10",
    "CO2", "NO2", "CO", "VoC", "C2H5OH",
    "ID", "Loc", "Customer", "Ph"
]

# Mapping of NTU RGB+D actions → likely rooms/contexts in DALTON
# This helps the UI suggest relevant sensor data for each skeleton action
NTU_ACTION_ROOM_HINTS = {
    "A001": ["Kitchen"],                 # drink water
    "A002": ["Kitchen", "Dining"],       # eat meal
    "A003": ["Bathroom", "Bedroom"],     # brush teeth
    "A004": ["Bathroom", "Bedroom"],     # brush hair
    "A008": ["Living", "TV", "Dining", "Bedroom"],  # sit down
    "A009": ["Living", "TV", "Dining"],  # stand up
    "A011": ["Bedroom", "Study", "Desk"],  # reading
    "A012": ["Study", "Desk", "Office"],   # writing
    "A028": ["Living", "Bedroom"],       # phone call
    "A029": ["Living", "Bedroom"],       # play with phone
    "A030": ["Study", "Desk", "Office"],   # type on keyboard
    "A037": ["Bathroom"],                # wipe face
    "A043": ["Bedroom", "Living"],       # falling down
}


class DaltonSite:
    """Represents one DALTON site (e.g. H1, A1, R1) with its sensor devices."""
    def __init__(self, site_id: str, data_dir: Path):
        self.site_id = site_id
        self.data_dir = data_dir
        self.devices: List[Dict[str, Any]] = []  # [{id, location, file}]
        self.df: Optional[pd.DataFrame] = None
        self._loaded = False

    def scan_devices(self):
        """Scan CSV files in data_dir to discover devices."""
        self.devices = []
        if not self.data_dir.exists():
            return
        for csv_file in sorted(self.data_dir.glob("*.csv")):
            # filename pattern: {ID}_{Location}.csv  e.g. "41_Kitchen.csv"
            name = csv_file.stem
            parts = name.split("_", 1)
            dev_id = parts[0] if parts else name
            location = parts[1].replace("_", " ") if len(parts) > 1 else "Unknown"
            self.devices.append({
                "id": dev_id,
                "location": location,
                "file": csv_file.name,
                "path": str(csv_file),
            })

    def load_data(self, max_rows: int = 500_000):
        """Lazy-load and merge all device CSVs for this site."""
        if self._loaded:
            return
        frames = []
        for dev in self.devices:
            try:
                df = pd.read_csv(dev["path"], nrows=max_rows)
                # Ensure standard column names
                if "ts" in df.columns:
                    df["ts"] = pd.to_datetime(df["ts"], format="mixed", dayfirst=False)
                frames.append(df)
            except Exception as e:
                logger.warning(f"Failed to load {dev['path']}: {e}")
        if frames:
            self.df = pd.concat(frames, ignore_index=True)
            self.df.sort_values("ts", inplace=True)
            self.df.reset_index(drop=True, inplace=True)
        self._loaded = True

    def get_days(self) -> List[str]:
        """Return unique dates available in this site's data."""
        if self.df is None:
            self.load_data()
        if self.df is None or self.df.empty:
            return []
        days = self.df["ts"].dt.date.unique().tolist()
        days.sort()
        return [d.strftime("%Y-%m-%d") for d in days]

    def get_locations(self) -> List[str]:
        """Return unique locations within this site."""
        return sorted(set(d["location"] for d in self.devices))

    def get_environment_state(
        self,
        date_str: str,
        time_offset_sec: float,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query the environmental state at a specific point in time.
        
        Args:
            date_str: Date string "YYYY-MM-DD"
            time_offset_sec: Seconds from midnight
            location: Optional location filter (e.g. "Kitchen")
        
        Returns:
            Dict with temperature, humidity, co2, plus DALTON-specific sensors
        """
        if self.df is None:
            self.load_data()
        if self.df is None or self.df.empty:
            return {}

        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        target_time = datetime.combine(target_date, datetime.min.time()) + timedelta(seconds=time_offset_sec)

        mask = (self.df["ts"].dt.date == target_date) & (self.df["ts"] <= target_time)
        if location:
            # Fuzzy match location
            loc_lower = location.lower().replace(" ", "")
            mask = mask & self.df["Loc"].str.lower().str.replace(" ", "").str.contains(loc_lower, na=False)

        relevant = self.df.loc[mask]
        if relevant.empty:
            return {}

        # Get the most recent row per device (last reading before target_time)
        latest = relevant.sort_values("ts").drop_duplicates(subset=["ID"], keep="last")

        env_data = {
            "source": "dalton",
            "site": self.site_id,
            "temperature": None,
            "humidity": None,
            "co2": None,
            "pm2_5": None,
            "pm10": None,
            "voc": None,
            "room": location,
        }

        # Average across all matching devices
        for col, key in [("T", "temperature"), ("H", "humidity"), ("CO2", "co2"),
                         ("PMS2_5", "pm2_5"), ("PMS10", "pm10"), ("VoC", "voc")]:
            vals = pd.to_numeric(latest[col], errors="coerce").dropna()
            if not vals.empty:
                env_data[key] = round(float(vals.mean()), 2)

        # Include room/location info from the first matching device
        if not latest.empty:
            env_data["room"] = str(latest.iloc[0].get("Loc", location or ""))

        return env_data

    def get_time_series(
        self,
        date_str: str,
        start_sec: float,
        end_sec: float,
        location: Optional[str] = None,
        downsample_sec: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get a time series of env readings for charting/preview.
        
        Args:
            date_str: Date string "YYYY-MM-DD"
            start_sec: Start offset from midnight (seconds)
            end_sec: End offset from midnight (seconds)
            location: Optional location filter
            downsample_sec: Downsample interval in seconds
        
        Returns:
            List of {time_offset, temperature, humidity, co2, ...} dicts
        """
        if self.df is None:
            self.load_data()
        if self.df is None or self.df.empty:
            return []

        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        t_start = datetime.combine(target_date, datetime.min.time()) + timedelta(seconds=start_sec)
        t_end = datetime.combine(target_date, datetime.min.time()) + timedelta(seconds=end_sec)

        mask = (self.df["ts"].dt.date == target_date) & \
               (self.df["ts"] >= t_start) & (self.df["ts"] <= t_end)
        if location:
            loc_lower = location.lower().replace(" ", "")
            mask = mask & self.df["Loc"].str.lower().str.replace(" ", "").str.contains(loc_lower, na=False)

        chunk = self.df.loc[mask].copy()
        if chunk.empty:
            return []

        # Downsample by averaging over intervals
        chunk["bucket"] = ((chunk["ts"] - t_start).dt.total_seconds() // downsample_sec).astype(int)
        grouped = chunk.groupby("bucket").agg({
            "T": "mean", "H": "mean", "CO2": "mean",
            "PMS2_5": "mean", "PMS10": "mean", "VoC": "mean"
        }).reset_index()

        result = []
        for _, row in grouped.iterrows():
            result.append({
                "time_offset": float(start_sec + row["bucket"] * downsample_sec),
                "temperature": round(float(row["T"]), 1) if pd.notna(row["T"]) else None,
                "humidity": round(float(row["H"]), 1) if pd.notna(row["H"]) else None,
                "co2": round(float(row["CO2"]), 0) if pd.notna(row["CO2"]) else None,
                "pm2_5": round(float(row["PMS2_5"]), 0) if pd.notna(row["PMS2_5"]) else None,
                "pm10": round(float(row["PMS10"]), 0) if pd.notna(row["PMS10"]) else None,
                "voc": round(float(row["VoC"]), 0) if pd.notna(row["VoC"]) else None,
            })
        return result


class DaltonService:
    """
    Main service for the DALTON dataset.
    Manages sites, annotations, and provides query APIs.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.sites: Dict[str, DaltonSite] = {}
        self.annotations_df: Optional[pd.DataFrame] = None
        self._scan_sites()
        self._load_annotations()

    def _scan_sites(self):
        """Discover all sites under Data/."""
        data_dir = self.dataset_path / "Data"
        if not data_dir.exists():
            logger.error(f"DALTON Data/ not found at {data_dir}")
            return

        for site_dir in sorted(data_dir.iterdir()):
            if site_dir.is_dir() and not site_dir.name.startswith("."):
                site = DaltonSite(site_dir.name, site_dir)
                site.scan_devices()
                if site.devices:
                    self.sites[site_dir.name] = site
        logger.info(f"DALTON: Found {len(self.sites)} sites with data")

    def _load_annotations(self):
        """Load Metadata/Annotations.csv."""
        ann_file = self.dataset_path / "Metadata" / "Annotations.csv"
        if not ann_file.exists():
            logger.warning(f"DALTON annotations not found: {ann_file}")
            return
        try:
            self.annotations_df = pd.read_csv(ann_file)
            self.annotations_df["ts"] = pd.to_datetime(self.annotations_df["ts"], format="mixed")
            self.annotations_df.sort_values("ts", inplace=True)
            logger.info(f"DALTON: Loaded {len(self.annotations_df)} annotations")
        except Exception as e:
            logger.error(f"Failed to load DALTON annotations: {e}")

    # ---- Public API ----

    def get_site_list(self) -> List[Dict[str, Any]]:
        """Return list of all sites with their device info."""
        result = []
        for site_id, site in sorted(self.sites.items()):
            result.append({
                "site_id": site_id,
                "device_count": len(site.devices),
                "locations": site.get_locations(),
                "has_annotations": self._site_has_annotations(site_id),
            })
        return result

    def get_site_devices(self, site_id: str) -> List[Dict[str, Any]]:
        """Return devices for a specific site."""
        site = self.sites.get(site_id)
        if not site:
            return []
        return site.devices

    def get_site_days(self, site_id: str) -> List[str]:
        """Return available dates for a site."""
        site = self.sites.get(site_id)
        if not site:
            return []
        return site.get_days()

    def get_site_locations(self, site_id: str) -> List[str]:
        """Return locations within a site."""
        site = self.sites.get(site_id)
        if not site:
            return []
        return site.get_locations()

    def get_environment_state(
        self, site_id: str, date_str: str,
        time_offset_sec: float, location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query environmental state at a point in time for a site."""
        site = self.sites.get(site_id)
        if not site:
            return {}
        return site.get_environment_state(date_str, time_offset_sec, location)

    def get_time_series(
        self, site_id: str, date_str: str,
        start_sec: float, end_sec: float,
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get time series for preview/charting."""
        site = self.sites.get(site_id)
        if not site:
            return []
        return site.get_time_series(date_str, start_sec, end_sec, location)

    def get_annotations(
        self, site_id: Optional[str] = None,
        date_str: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get activity annotations, optionally filtered by site and date."""
        if self.annotations_df is None:
            return []

        df = self.annotations_df
        if site_id:
            # Annotations use Site column which may have sub-locations like "H2-Floor0"
            df = df[df["Site"].str.startswith(site_id, na=False)]
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            df = df[df["ts"].dt.date == target_date]

        result = []
        for _, row in df.iterrows():
            result.append({
                "timestamp": row["ts"].isoformat() if pd.notna(row["ts"]) else None,
                "time_offset_sec": (row["ts"] - datetime.combine(
                    row["ts"].date(), datetime.min.time()
                )).total_seconds() if pd.notna(row["ts"]) else 0,
                "label": str(row.get("Label", "")),
                "site": str(row.get("Site", "")),
                "participant": str(row.get("Customer", "")),
            })
        return result

    def get_activity_tags(self, site_id: Optional[str] = None) -> List[str]:
        """
        Extract unique activity labels from annotations.
        Normalizes common labels for matching with NTU actions.
        """
        annotations = self.get_annotations(site_id)
        tags = set()
        for ann in annotations:
            label = ann.get("label", "").strip()
            if label:
                # Normalize: lowercase, strip quotes
                clean = label.strip('"').strip()
                if clean and len(clean) > 2:
                    tags.add(clean)
        return sorted(tags)

    def _site_has_annotations(self, site_id: str) -> bool:
        """Check if a site has any annotations."""
        if self.annotations_df is None:
            return False
        return bool(self.annotations_df["Site"].str.startswith(site_id, na=False).any())

    def suggest_environment_for_action(self, action_code: str) -> List[Dict[str, Any]]:
        """
        Given an NTU action code (e.g. "A002"), suggest matching
        DALTON site/location combinations that would provide
        realistic environmental context.
        """
        hints = NTU_ACTION_ROOM_HINTS.get(action_code, [])
        if not hints:
            hints = ["Kitchen", "Bedroom", "Living"]  # defaults

        suggestions = []
        for site_id, site in self.sites.items():
            for loc in site.get_locations():
                for hint in hints:
                    if hint.lower() in loc.lower():
                        suggestions.append({
                            "site_id": site_id,
                            "location": loc,
                            "match_reason": f"'{loc}' matches room hint '{hint}' for {action_code}",
                        })
                        break
        return suggestions
