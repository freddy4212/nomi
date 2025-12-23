"""
processor.py - 資料處理器

負責影像渲染、編碼以及狀態資訊的收集。
"""

import base64
import socket
import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
from memory_layer.config import memory_config
from observation_layer.modules.network.receiver import FrameData
from observation_layer.modules.visualization.visualizer import Visualizer


class DataProcessor:
    @staticmethod
    def render_frame(frame_data: FrameData, skeleton_frame, observation_core, view_mode: str = "overlay", skeleton_player=None) -> Any:
        """渲染骨架到影像"""
        if not frame_data or frame_data.image is None:
            return None
        
        # 根據 view_mode 決定底圖
        if view_mode == "yolo_only" or view_mode == "interpolated":
            image = np.zeros_like(frame_data.image)
        else:
            image = frame_data.image.copy()
            
        # 如果是 original 模式，直接返回原圖
        if view_mode == "original":
            return image

        # 決定要使用的骨架資料
        skeletons = skeleton_frame
        
        # 如果是 interpolated 模式且外部沒有傳入 skeleton_frame，才嘗試從 player 或 processor 獲取
        if view_mode == "interpolated" and skeletons is None:
            if skeleton_player:
                skeletons = skeleton_player.get_next_frame()
            elif observation_core and observation_core.skeleton_processor:
                interp = observation_core.skeleton_processor.get_interpolated_frames()
                if interp:
                    skeletons = interp[-1]
        
        if skeletons and hasattr(skeletons, 'persons'):
            for person in skeletons.persons:
                # yolo_only 模式不使用平滑
                use_smoothed = (view_mode != "yolo_only")
                kpts = person.smoothed_keypoints if use_smoothed and person.smoothed_keypoints is not None else person.keypoints
                
                if kpts is not None and kpts.shape == (17, 3):
                    Visualizer.draw_skeleton(image, kpts, person_id=person.person_id, box=person.box)
        return image

    @staticmethod
    def encode_image(image) -> str:
        """影像轉 Base64"""
        if image is None: return ""
        try:
            _, buf = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buf).decode('utf-8')
        except: return ""

    @staticmethod
    def collect_status(
        frame_data: Any,
        observation_core: Any,
        memory_core: Any,
        device_info: Any,
        last_active_time: Dict[str, float],
        last_db_events_written: int,
        memory_config: Any = None
    ) -> tuple[Dict, int]:
        """收集各層狀態"""
        tcp_connected = tcp_active = False
        tcp_port = fps = frame_no = algo_tick = 0
        buffer_status = {}
        
        if observation_core:
            if observation_core.network_receiver:
                nr = observation_core.network_receiver
                tcp_connected = nr.is_connected
                tcp_port = nr.port
                fps = nr.get_fps()
                if nr.is_connected and frame_data:
                    last_active_time["tcp"] = time.time()
            if observation_core.skeleton_processor:
                buffer_status = observation_core.skeleton_processor.get_buffer_status()
        
        # tcp_active = time.time() - last_active_time.get("tcp", 0) < 0.3
        tcp_last_active = last_active_time.get("tcp", 0)
        
        if frame_data:
            frame_no = getattr(frame_data, 'frame_no', 0)
            if frame_data.frame_info:
                algo_tick = int(frame_data.frame_info.get("algo_tick", 0))
        
        db_connected = db_active = False
        current_events_written = last_db_events_written

        if memory_core:
            status = memory_core.get_status()
            db_connected = status.is_db_connected and status.is_running
            current_events_written = status.events_written
            if current_events_written > last_db_events_written:
                last_active_time["db"] = time.time()
            # db_active = time.time() - last_active_time.get("db", 0) < 0.3
            db_last_active = last_active_time.get("db", 0)
        else:
            db_last_active = 0
        
        db_port = 0
        if memory_config and hasattr(memory_config, 'database'):
            db_port = memory_config.database.port

        return {
            "host_ip": get_local_ip(),
            "fps": fps, "algo_tick": algo_tick, "frame_no": frame_no,
            "device_id": device_info.id, "device_name": device_info.name,
            "device_version": device_info.version, "device_model": device_info.model,
            "memory_connected": db_connected, "db_last_active": db_last_active,
            "tcp_connected": tcp_connected, "tcp_last_active": tcp_last_active, "tcp_port": tcp_port,
            "db_port": db_port, "buffer_status": buffer_status
        }, current_events_written
