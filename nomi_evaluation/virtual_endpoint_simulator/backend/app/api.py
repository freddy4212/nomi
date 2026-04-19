from __future__ import annotations

import json
import logging
import socket
import threading
import time
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .config import DALTON_DIR, DEFAULT_DATASET_DIR, ORANGE4HOME_DIR
from .models import (ActionInfo, EnvironmentItem, FileItem, FrameMeta,
                     HealthResponse, PlaylistItem, PlaylistRequest,
                     PreviewResponse, SendRequest, SendResult)
from .services.dalton_service import DaltonService
from .services.orange4home_service import Orange4HomeService
from .services.sender_service import PacketSender
from .services.skeleton_service import skeleton_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["simulator"])
sender = PacketSender()
o4h_service = Orange4HomeService(str(ORANGE4HOME_DIR))
dalton_service = DaltonService(str(DALTON_DIR))


class SendingManager:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._is_running = False

    def start_sending(self, req: SendRequest, packet: dict):
        if self._is_running:
            self.stop_sending()
            if self._thread:
                self._thread.join(timeout=2.0)

        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._sending_loop, args=(req, packet))
        self._thread.daemon = True
        self._thread.start()

    def stop_sending(self):
        self._stop_event.set()
        self._is_running = False

    def is_running(self):
        return self._is_running

    def _sending_loop(self, req: SendRequest, packet: dict):
        logger.info(f"Starting sending loop for {req.file_name}, repeat={req.repeat}")
        sent_count = 0
        try:
            for index in range(req.repeat):
                if self._stop_event.is_set():
                    logger.info("Sending stopped by user")
                    break

                success, status = sender.send_packet(packet, req.target_ip, req.target_port)
                if not success:
                    logger.error(f"Failed to send packet: {status}")
                    # Decide if we want to stop on error or continue. For UDP, maybe continue?
                    # But if network is down, maybe break. let's continue for now but log.
                
                sent_count += 1
                
                # frame looping logic if needed? 
                # The current logic just sends the SAME packet repeatedly because `packet` is built once.
                # Wait, the previous logic was:
                # packet = skeleton_service.build_packet(file_name=req.file_name, frame_no=req.frame_no)
                # loop repeat times... sending the SAME frame? 
                # That's what the code did: `packet` was built OUTSIDE the loop.
                # If the user wants to play usage sequence, they should probably send a sequence.
                # But the UI sends `frame_no`.
                
                # If the user intended to "Play" the file over UDP, the logical thing is to increment frame_no.
                # But the current backend implementation sends a static frame `req.repeat` times. 
                # I will stick to the existing logic for now (sending static frame repeatedly), 
                # or maybe the user implies "broadcast this frame continuously".
                
                if req.interval_ms > 0:
                    time.sleep(req.interval_ms / 1000.0)
                    
        except Exception as e:
            logger.error(f"Error in sending loop: {e}")
        finally:
            self._is_running = False
            logger.info(f"Sending loop finished. Total sent: {sent_count}")

manager = SendingManager()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    logger.info("Health check requested")
    logger.info(f"Current dataset_dir: {DEFAULT_DATASET_DIR}")
    return HealthResponse(status="ok", dataset_dir=str(DEFAULT_DATASET_DIR))


@router.get("/actions", response_model=list[ActionInfo])
def get_actions() -> list[ActionInfo]:
    logger.info("Requesting all action summaries")
    actions = skeleton_service.list_action_summary()
    return [ActionInfo(**item) for item in actions]


@router.get("/actions/{action_code}/files", response_model=list[FileItem])
def get_files_by_action(action_code: str) -> list[FileItem]:
    logger.info(f"Requesting files for action: {action_code}")
    files = skeleton_service.list_files_by_action(action_code)
    return [FileItem(**item) for item in files]


@router.get("/files/{file_name}/meta", response_model=FrameMeta)
def get_file_meta(file_name: str) -> FrameMeta:
    try:
        return FrameMeta(**skeleton_service.get_file_meta(file_name))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

# --- Orange4Home Endpoints ---

@router.get("/environment/days", response_model=list[str])
def get_environment_days() -> list[str]:
    return o4h_service.get_days()

@router.get("/environment/locations", response_model=list[str])
def get_environment_locations() -> list[str]:
    return ["Living Room", "Kitchen", "Bedroom", "Bathroom", "Entrance", "Office"]

@router.get("/environment/activity-tags", response_model=list[str])
def get_environment_activity_tags() -> list[str]:
    return o4h_service.get_activity_tags()

@router.get("/environment/activity-list")
def get_environment_activity_list():
    """Return structured activity list: [{tag, room, activity}]"""
    return o4h_service.get_activity_list()

@router.get("/environment/activity-list/grouped")
def get_environment_activity_list_grouped():
    """Return activities grouped by room: { room: [activity, ...] }"""
    return o4h_service.get_activity_list_grouped()

@router.get("/environment/activity-segments")
def get_environment_activity_segments(room: str = None, activity: str = None):
    """
    Return concrete START/STOP-matched activity segments with real time windows.
    Each segment has: room, activity, tag, date, start_sec, end_sec, duration_sec.
    """
    return o4h_service.get_activity_segments(room_filter=room, activity_filter=activity)

# --- DALTON Endpoints ---

@router.get("/dalton/sites")
def get_dalton_sites():
    """Return all DALTON sites with their device/location info."""
    return dalton_service.get_site_list()

@router.get("/dalton/sites/{site_id}/devices")
def get_dalton_site_devices(site_id: str):
    """Return devices for a specific DALTON site."""
    return dalton_service.get_site_devices(site_id)

@router.get("/dalton/sites/{site_id}/days")
def get_dalton_site_days(site_id: str):
    """Return available dates for a DALTON site."""
    return dalton_service.get_site_days(site_id)

@router.get("/dalton/sites/{site_id}/locations")
def get_dalton_site_locations(site_id: str):
    """Return locations within a DALTON site."""
    return dalton_service.get_site_locations(site_id)

@router.get("/dalton/sites/{site_id}/annotations")
def get_dalton_annotations(site_id: str, date: str = None):
    """Return activity annotations for a DALTON site."""
    return dalton_service.get_annotations(site_id, date)

@router.get("/dalton/sites/{site_id}/state")
def get_dalton_env_state(site_id: str, date: str, offset_sec: float = 0, location: str = None):
    """Query DALTON environmental state at a point in time."""
    return dalton_service.get_environment_state(site_id, date, offset_sec, location)

@router.get("/dalton/sites/{site_id}/timeseries")
def get_dalton_timeseries(
    site_id: str, date: str,
    start_sec: float = 0, end_sec: float = 3600,
    location: str = None
):
    """Get DALTON time series for preview/charting."""
    return dalton_service.get_time_series(site_id, date, start_sec, end_sec, location)

@router.get("/dalton/suggest/{action_code}")
def suggest_dalton_environment(action_code: str):
    """Suggest DALTON site/location combinations matching an NTU action."""
    return dalton_service.suggest_environment_for_action(action_code.upper())
    
@router.get("/preview", response_model=PreviewResponse)
def preview_packet(file_name: str, frame_no: int = 0, protocol: str = "tcp") -> PreviewResponse:
    try:
        packet = skeleton_service.build_packet(file_name=file_name, frame_no=frame_no)
        
        # If protocol is UDP, convert to YOLO format so frontend sees what will be sent
        if protocol.lower() == "udp":
            packet = skeleton_service.convert_to_yolo_format(packet)

        # Handle 'action' retrieval safely since structure might change
        # In Rich format: packet['data']['frame_info']['action']
        # In YOLO format: packet['frame_info']['action'] (top level, no data wrapper if converted)
        
        action_code = "UNKNOWN"
        if "data" in packet and "frame_info" in packet["data"]:
             action_code = packet["data"]["frame_info"].get("action", "UNKNOWN")
        elif "frame_info" in packet:
             action_code = packet["frame_info"].get("action", "UNKNOWN")

        return PreviewResponse(
            file_name=file_name,
            action_code=action_code,
            frame_no=frame_no,
            packet=packet,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Global Sending Manager
class GlobalSendingManager:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._is_running = False
        self._socket_is_healthy = False
        self._last_target = (None, None)
        self._current_frame_status = None  # Stores { file_name, frame_no, packet, sent_packet }

    def get_status(self):
        return {
            "is_running": self._is_running,
            "current_frame": self._current_frame_status
        }

    def start_sending(self, req: SendRequest, initial_packet: dict):
        self._last_target = (req.target_ip, req.target_port)
        # Stop existing if any
        if self._is_running:
            self.stop_sending()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0) # Wait a bit

        self._stop_event.clear()
        self._is_running = True
        self._socket_is_healthy = False
        
        # Decide format based on protocol
        packet_to_send = initial_packet
        
        # CHANGED: Convert to YOLO format for BOTH UDP and TCP now
        try:
            print(f"DEBUG: Attempting conversion for {req.protocol}")
            packet_to_send = skeleton_service.convert_to_yolo_format(initial_packet)
        except Exception as e:
            logger.error(f"Failed to convert packet to YOLO format: {e}")
            import traceback
            traceback.print_exc()
            packet_to_send = initial_packet

        self._thread = threading.Thread(target=self._card_loop, args=(req, packet_to_send), name="single")
        self._thread.daemon = True
        self._thread.start()

    def start_playlist(self, req: PlaylistRequest):
        self._last_target = (req.target_ip, req.target_port)
        if self._is_running:
            self.stop_sending()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0) # Wait a bit

        self._stop_event.clear()
        self._is_running = True
        self._socket_is_healthy = False
        
        self._thread = threading.Thread(target=self._playlist_loop, args=(req,), name="playlist")
        self._thread.daemon = True
        self._thread.start()

    def stop_sending(self):
        self._stop_event.set()
        # The thread will exit its loop
        self._is_running = False
        self._socket_is_healthy = False

    def is_running(self):
        # Check if thread is actually alive
        if self._thread and self._thread.is_alive():
            return True
        self._is_running = False
        self._socket_is_healthy = False
        return False
    
    def _playlist_loop(self, req: PlaylistRequest):
        # Time-based mixer implementation
        logger.info(f"Playlist playback started. Items: {len(req.items)} skeleton, {len(req.environment_items)} env")
        protocol = req.protocol.lower()
        sock = None
        if protocol != "udp":
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((req.target_ip, req.target_port))
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._socket_is_healthy = True
                logger.info(f"TCP Connected to {req.target_ip}:{req.target_port}")
            except Exception as e:
                logger.error(f"Failed to connect to TCP target: {e}")
                self._is_running = False
                self._socket_is_healthy = False
                return
        else:
            self._socket_is_healthy = True 

        # --- PRE-CALCULATION PHASE ---
        try:
            # 1. Determine total duration & Build Segments
            max_duration = 0
            skel_segments = [] 
            current_offset = 0
            
            # Process Skeleton Track to build segments
            for item in req.items:
                dur = 0
                if item.duration_ms > 0:
                     dur = item.duration_ms
                else:
                     dur = 3300 
                
                start = item.start_time_offset
                if start == 0 and len(req.items) > 1: 
                    start = current_offset
                
                end = start + dur
                skel_segments.append({"start": start, "end": end, "item": item, "duration": dur})
                current_offset = end
                if end > max_duration: max_duration = end

            # Process Environment Track
            env_segments = []
            for e_item in req.environment_items:
                start = e_item.start_time_offset
                if e_item.duration_ms <= 0: e_item.duration_ms = 5000 
                end = start + e_item.duration_ms
                env_segments.append({"start": start, "end": end, "item": e_item})
                if end > max_duration: max_duration = end

            logger.info(f"Timeline Duration: {max_duration}ms. Segments: {len(skel_segments)} skel, {len(env_segments)} env")
            file_meta_cache = {}
            
            # --- PLAYBACK LOOP ---
            start_wall_time = time.time() * 1000
            
            while self._is_running and not self._stop_event.is_set():
                now_wall = time.time() * 1000
                simulation_time = now_wall - start_wall_time
                
                if simulation_time > max_duration:
                    if req.loop_playlist:
                        start_wall_time = now_wall
                        simulation_time = 0
                        try:
                            blank = {
                                "frame_info": {"frame_no": 0, "algo_tick": int(now_wall)}, 
                                "basic_info": {"name": "VIRTUAL_WE2"}, 
                                "keypoints": []
                            }
                            if protocol == "udp": sender.send_packet(blank, req.target_ip, req.target_port, "udp")
                        except: pass
                    else:
                        break
                
                # Active Skeleton
                active_skel = None
                for seg in skel_segments:
                    if seg["start"] <= simulation_time < seg["end"]:
                        active_skel = seg
                        break 
                
                # Active Environment
                active_env = None
                for seg in env_segments:
                    if seg["start"] <= simulation_time < seg["end"]:
                        active_env = seg
                
                # Build Data
                current_packet = None
                frame_label = 0
                item_name = "None"
                
                if active_skel:
                    item = active_skel["item"]
                    item_name = item.file_name
                    clip_time = simulation_time - active_skel["start"]
                    segment_duration = max(1, int(active_skel.get("duration", item.duration_ms or 1)))

                    if item.file_name not in file_meta_cache:
                        try:
                            file_meta_cache[item.file_name] = skeleton_service.get_file_meta(item.file_name)
                        except Exception:
                            file_meta_cache[item.file_name] = {"total_frames": 1}

                    total_frames = int(file_meta_cache[item.file_name].get("total_frames", 1))
                    clip_start = max(0, int(item.start_frame))
                    clip_end = int(item.end_frame) if int(item.end_frame) != -1 else max(0, total_frames - 1)
                    if clip_end < clip_start:
                        clip_end = clip_start

                    clip_len = max(1, clip_end - clip_start + 1)
                    effective_time = max(0.0, float(clip_time)) * max(0.01, float(item.speed_factor))
                    raw_offset = int((effective_time / float(segment_duration)) * clip_len)

                    if int(item.repeat) > 1:
                        frame_offset = raw_offset % clip_len
                    else:
                        frame_offset = min(raw_offset, clip_len - 1)

                    target_frame = clip_start + frame_offset
                    
                    frame_label = target_frame
                    try:
                        pk = skeleton_service.build_packet(item.file_name, target_frame)
                        current_packet = skeleton_service.convert_to_yolo_format(pk)
                        if "frame_info" in current_packet: 
                            current_packet["frame_info"]["algo_tick"] = int(now_wall)
                    except: pass
                
                if current_packet is None:
                     current_packet = {
                         "frame_info": {"frame_no": 0, "count": 0, "algo_tick": int(now_wall)},
                         "basic_info": {"name": "VIRTUAL_WE2", "ver": "1.0", "device_id": "8538000D"},
                         "image": "", "keypoints": [], "reid_results": []
                     }

                # Inject ground truth action code into environment for evaluation
                gt_action = current_packet.get("frame_info", {}).get("action")
                if gt_action:
                    if "environment" not in current_packet:
                        current_packet["environment"] = {}
                    current_packet["environment"]["ground_truth_action"] = gt_action

                # Environment
                if active_env:
                    e_item = active_env["item"]
                    env_data = None
                    clip_time_ms = simulation_time - active_env["start"]

                    # --- DALTON source ---
                    if getattr(e_item, 'dataset_source', 'o4h') == 'dalton' and dalton_service:
                        site_id = e_item.site_id
                        location = e_item.location or None
                        if e_item.type == "dalton_sensor" and site_id:
                            # content = "YYYY-MM-DD" (the date to query)
                            day_offset_sec = e_item.data_offset_sec + (clip_time_ms / 1000.0)
                            env_data = dalton_service.get_environment_state(
                                site_id, e_item.content, day_offset_sec, location
                            )
                        elif e_item.type == "dalton_activity" and site_id:
                            # content = annotation label text
                            env_data = {
                                "activity_label": e_item.content,
                                "activity": e_item.content,
                                "room": e_item.location or "",
                                "source": "dalton",
                                "site": site_id,
                            }

                    # --- Orange4Home source ---
                    elif e_item.type == "o4h_segment" and o4h_service:
                        # content = "YYYY-MM-DD", data_offset_sec = segment's start_sec
                        seg_start_sec = e_item.data_offset_sec       # actual start in day
                        seg_end_sec = getattr(e_item, 'data_end_sec', seg_start_sec + e_item.duration_ms / 1000.0)
                        elapsed_in_seg = clip_time_ms / 1000.0
                        query_sec = seg_start_sec + elapsed_in_seg
                        # Clamp to segment window
                        query_sec = min(query_sec, seg_end_sec)
                        env_data = o4h_service.get_state_for_room(
                            e_item.content, query_sec, room=e_item.location or "livingroom"
                        )
                        if env_data:
                            env_data["source"] = "o4h"
                            env_data["activity_label"] = getattr(e_item, 'activity_label', None)
                            env_data["room"] = e_item.location or env_data.get("room", "")
                    elif e_item.type == "day" and o4h_service:
                        day_offset_sec = e_item.data_offset_sec + (clip_time_ms / 1000.0)
                        env_data = o4h_service.get_environment_state(e_item.content, day_offset_sec)
                    elif e_item.type == "activity" and o4h_service:
                        parsed = o4h_service.parse_activity_label(e_item.content)
                        if parsed:
                            env_data = {
                                "activity_label": parsed.get("tag"),
                                "activity": parsed.get("activity"),
                                "sound_event": parsed.get("activity"),
                            }
                            if parsed.get("room"):
                                env_data["room"] = parsed.get("room")
                    elif e_item.type in ["location", "sensor"]:
                        env_data = {"room": e_item.content}
                    elif e_item.type == "manual":
                        # Manual environment override for evaluation
                        env_data = {"room": e_item.content or e_item.location or "Room"}
                        if e_item.temperature is not None: env_data["temperature"] = e_item.temperature
                        if e_item.humidity is not None: env_data["humidity"] = e_item.humidity
                        if e_item.co2 is not None: env_data["co2"] = e_item.co2
                        if e_item.light is not None: env_data["light"] = e_item.light
                        if e_item.activity_label: env_data["activity_label"] = e_item.activity_label
                        if e_item.sound_event: env_data["sound_event"] = e_item.sound_event
                        if e_item.time_of_day: env_data["time_of_day"] = e_item.time_of_day
                        if e_item.duration_min is not None: env_data["duration_min"] = e_item.duration_min
                        if e_item.entry_context: env_data["entry_context"] = e_item.entry_context
                        if e_item.tv_on is not None: env_data["tv_on"] = e_item.tv_on
                        if e_item.motion_detected is not None: env_data["motion_detected"] = e_item.motion_detected
                    
                    if env_data:
                        if "environment" not in current_packet: current_packet["environment"] = {}
                        current_packet["environment"].update(env_data)

                # Send
                try:
                    if protocol == "udp":
                        sender.send_packet(current_packet, req.target_ip, req.target_port, "udp")
                    elif sock and self._socket_is_healthy:
                        payload = (json.dumps(current_packet, ensure_ascii=False) + "\n").encode("utf-8")
                        sock.sendall(payload)
                    
                    self._current_frame_status = {
                        "file_name": item_name,
                        "frame_no": frame_label,
                        "playlist_index": 0, 
                        "packet": current_packet,
                        "sent_packet": current_packet,
                        "simulation_time": int(simulation_time),
                        "total_duration": int(max_duration)
                    }
                except Exception as e:
                    logger.error(f"Send error: {e}")
                    if protocol != "udp": self._socket_is_healthy = False
                
                elapsed = (time.time() * 1000) - now_wall
                sleep_ms = req.interval_ms - elapsed
                if sleep_ms > 0: time.sleep(sleep_ms / 1000.0)

            if sock: sock.close()

        except Exception as e:
            logger.error(f"Playlist Error: {e}")
        finally:
            if sock:
                try: sock.close()
                except: pass
            self._is_running = False
            self._socket_is_healthy = False
            logger.info("Playlist finished")


    def is_socket_healthy(self, target_ip: str, target_port: int) -> bool:
        """
        Check if the current active sending thread has a healthy socket to the target.
        """
        if not self.is_running():
            return False
        
        # Only return true if target matches current sending session
        if self._last_target == (target_ip, target_port):
            return self._socket_is_healthy
        return False

    def _card_loop(self, req: SendRequest, packet: dict):
        logger.info(f"Background sending started for {req.file_name}")
        
        # Determine protocol from request
        protocol = req.protocol.lower()
        
        import json
        import socket
        
        sock = None
        if protocol != "udp":
            # For TCP, establish a persistent connection
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((req.target_ip, req.target_port))
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._socket_is_healthy = True
                logger.info(f"TCP Connected to {req.target_ip}:{req.target_port}")
            except Exception as e:
                logger.error(f"Failed to connect to TCP target: {e}")
                self._is_running = False
                self._socket_is_healthy = False
                return
        else:
            # UDP is always assumed 'healthy' if thread is running
            self._socket_is_healthy = True

        try:
            # Reconstruct packet if we want to iterate frames? 
            # For now, use the static packet logic from before.
            # If we want to iterate, we would need to know total frames and build packets here.
            
            # --- IMPROVEMENT: Play forward logic ---
            # If repeat is large (>1), we assume the user wants to PLAY the file, not just repeat one frame.
            # We need to know how many frames are in total.
            # To do this efficiently without re-querying meta every time, let's just increment frame_no
            # and wrap around if we catch an IndexError. But IndexError is raised by build_packet.
            # Let's try to fetch frame 0 to see if it works.
            
            current_frame_no = req.frame_no
            
            for i in range(req.repeat):
                if self._stop_event.is_set():
                    logger.info("Sending stopped by user signal")
                    break
                
                start_time = time.time()
                
                # Fetch Current Frame Data (Dynamic)
                try:
                     # This creates file read overhead every frame, but ensures we play the file
                     current_packet = skeleton_service.build_packet(file_name=req.file_name, frame_no=current_frame_no)

                     # Update frame status for frontend polling (visualization + sent packet)
                     self._current_frame_status = {
                         "file_name": req.file_name,
                         "frame_no": current_frame_no,
                         "packet": current_packet,
                         "sent_packet": None
                     }
                     
                     # 1. Update basic info to simulate live stream ticks
                     if "frame_info" in current_packet:
                          current_packet["frame_info"]["algo_tick"] = int(time.time() * 1000)
                     elif "data" in current_packet and "frame_info" in current_packet["data"]:
                          current_packet["data"]["frame_info"]["algo_tick"] = int(time.time() * 1000)

                     # 2. Convert to YOLO
                     packet_to_send = skeleton_service.convert_to_yolo_format(current_packet)

                     if self._current_frame_status is not None:
                         self._current_frame_status["sent_packet"] = packet_to_send
                     
                except (IndexError, FileNotFoundError):
                     # Loop back to 0
                     current_frame_no = 0
                     continue
                except Exception as e:
                     logger.error(f"Error building frame {current_frame_no}: {e}")
                     break

                # Send logic
                if protocol == "udp":
                     # UDP is stateless, use the sender service helper or direct
                     sender.send_packet(packet_to_send, req.target_ip, req.target_port, protocol="udp")
                else:
                     # TCP Persistent
                     try:
                         payload = (json.dumps(packet_to_send, ensure_ascii=False) + "\n").encode("utf-8")
                         sock.sendall(payload)
                         self._socket_is_healthy = True
                     except (BrokenPipeError, ConnectionResetError) as e:
                         # Try to reconnect once
                         logger.warning(f"TCP connection broken, reconnecting... {e}")
                         self._socket_is_healthy = False
                         try:
                             sock.close()
                             sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                             sock.settimeout(3.0)
                             sock.connect((req.target_ip, req.target_port))
                             sock.sendall(payload)
                             self._socket_is_healthy = True
                         except Exception as reconnect_err:
                             logger.error(f"Reconnect failed: {reconnect_err}")
                             break
                     except Exception as e:
                         logger.error(f"TCP Send Error: {e}")
                         self._socket_is_healthy = False
                         break

                # Advance frame
                current_frame_no += 1
                
                # Wait for next frame
                if req.interval_ms > 0:
                    elapsed = time.time() - start_time
                    sleep_time = (req.interval_ms / 1000.0) - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"Error in background sending: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
            self._is_running = False
            self._socket_is_healthy = False
            logger.info("Background sending finished")

manager = GlobalSendingManager()


@router.post("/send", response_model=SendResult)
def send_packet(req: SendRequest, background_tasks: BackgroundTasks) -> SendResult:
    try:
        # Build the packet once to validate
        packet = skeleton_service.build_packet(file_name=req.file_name, frame_no=req.frame_no)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Start background task
    manager.start_sending(req, packet)

    # Return immediately
    return SendResult(
        sent_count=0, # Asynchronous
        target=f"{req.target_ip}:{req.target_port}",
        last_status="started_async",
    )

@router.post("/playlist/start", response_model=SendResult)
def start_playlist(req: PlaylistRequest, background_tasks: BackgroundTasks) -> SendResult:
    if not req.items:
        raise HTTPException(status_code=400, detail="Playlist is empty")
        
    manager.start_playlist(req)
    
    return SendResult(
        sent_count=0,
        target=f"{req.target_ip}:{req.target_port}",
        last_status="playlist_started",
    )


@router.post("/stop")
def stop_sending():
    manager.stop_sending()
    return {"status": "stopped"}

@router.get("/status")
def get_status():
    status = manager.get_status()
    status["mode"] = "playlist" if manager.is_running() and hasattr(manager, '_thread') and manager._thread.name == 'playlist' else "single"
    return status



@router.get("/connection/status")
def check_connection_status(target_ip: str, target_port: int, api_timeout: float = 0.5) -> dict:
    """
    Check if a connection can be established to the target.
    If we are currently sending to this target via TCP, we report based on the active socket.
    """
    # If the manager is already sending to this target, avoid opening a new connection
    if manager.is_socket_healthy(target_ip, target_port):
        return {"connected": True, "message": "Connection active (streaming)"}

    # Otherwise, perform a manual ping/connect check
    is_connected = sender.check_connection(target_ip, target_port, timeout=api_timeout)
    message = "Connection successful" if is_connected else "Connection failed"
    return {"connected": is_connected, "message": message}

