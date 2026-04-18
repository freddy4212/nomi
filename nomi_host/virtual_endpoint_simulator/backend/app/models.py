from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionInfo(BaseModel):
    code: str
    label: str
    file_count: int


class FileItem(BaseModel):
    file_name: str
    action_code: str
    total_frames: int = 0


class FrameMeta(BaseModel):
    file_name: str
    action_code: str
    total_frames: int


class PreviewResponse(BaseModel):
    file_name: str
    action_code: str
    frame_no: int
    packet: Dict[str, Any]


class SendRequest(BaseModel):
    file_name: str
    frame_no: int = Field(ge=0)
    target_ip: str
    target_port: int = Field(ge=1, le=65535)
    repeat: int = Field(default=1, ge=1, le=1000000)
    interval_ms: int = Field(default=0, ge=0, le=60000)
    protocol: str = Field(default="tcp", description="Protocol to use: 'tcp' or 'udp'")


class PlaylistItem(BaseModel):
    file_name: str
    start_frame: int = 0
    end_frame: int = -1  # -1 means send until the end
    repeat: int = 1       # Number of times to loop this segment
    speed_factor: float = 1.0 # 1.0 = normal speed
    
    # --- New Fields for Multi-Track ---
    start_time_offset: int = 0 # Milliseconds from start of timeline
    duration_ms: int = 0
    

class EnvironmentItem(BaseModel):
    type: str  # "day", "location", "sensor", "activity", "dalton_sensor", "o4h_segment", "manual"
    content: str  # "2017-01-30" or "Living Room" or "H1/Kitchen"
    start_time_offset: int  # Milliseconds
    duration_ms: int  # Duration of this block
    # For O4H Day / Segment items:
    data_offset_sec: float = 0.0    # For 'day': seconds into day; for 'o4h_segment': segment start_sec
    data_end_sec: float = 0.0       # For 'o4h_segment': segment end_sec
    activity_label: str = ""        # Human-readable label for o4h_segment
    # For DALTON items:
    dataset_source: str = "o4h"     # "o4h" or "dalton"
    site_id: str = ""               # DALTON site ID, e.g. "H1"
    location: str = ""              # Room name, e.g. "Kitchen"
    # For manual/evaluation environment override:
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    co2: Optional[float] = None
    light: Optional[float] = None
    sound_event: Optional[str] = None
    time_of_day: Optional[str] = None
    duration_min: Optional[float] = None
    entry_context: Optional[str] = None
    tv_on: Optional[bool] = None
    motion_detected: Optional[bool] = None


class PlaylistRequest(BaseModel):
    items: List[PlaylistItem] # Keeps backward compatibility if empty
    environment_items: List[EnvironmentItem] = [] # New track
    target_ip: str
    target_port: int = Field(default=9527, ge=1, le=65535)
    protocol: str = Field(default="tcp", description="Protocol to use: 'tcp' or 'udp'")
    interval_ms: int = Field(default=33, ge=0, le=60000)
    loop_playlist: bool = Field(default=False)


class SendResult(BaseModel):
    sent_count: int
    target: str
    last_status: str


class HealthResponse(BaseModel):
    status: str
    dataset_dir: str
