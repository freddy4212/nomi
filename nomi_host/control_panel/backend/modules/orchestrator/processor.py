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
        # 檢查是否有足夠的資料可以渲染
        has_image = frame_data and frame_data.image is not None
        has_skeletons = skeleton_frame is not None
        # 檢查 frame_data 是否有 keypoints (Raw Keypoints)
        # 注意：即使是空列表 [] 也要視為存在 keypoints 欄位，只是內容為空
        # 但如果是None則視為不存在
        raw_kpts = frame_data.keypoints if frame_data else None
        has_raw_kpts = raw_kpts is not None

        # 如果既沒有影像資料也沒有骨架資料(平滑後或原始)，返回 None
        if not has_image and not has_skeletons and not has_raw_kpts:
            # 特例：如果是 dummy frame (source="dummy" in frame_info)，允許返回空黑畫面
            if frame_data and frame_data.frame_info and frame_data.frame_info.get("source") == "dummy":
                pass # Allow proceeding to create black canvas
            else:
                return None
        
        # [Canvas Size Logic]
        # Determine canvas size. If image exists, use image size.
        # If not, use a default size, but check if keypoints exceed it.
        canvas_w, canvas_h = 640, 480
        
        # Check raw keypoints for max coordinates to adjust canvas size if needed (for high-res simulator data)
        if not has_image and has_raw_kpts:
            try:
                max_x, max_y = 0, 0
                raw_kpts = frame_data.keypoints
                if isinstance(raw_kpts, list):
                    for person in raw_kpts:
                        if isinstance(person, list):
                            for pt in person:
                                if isinstance(pt, list) and len(pt) >= 2:
                                    # Check first two elements (x,y)
                                    x, y = pt[0], pt[1]
                                    if x > max_x: max_x = x
                                    if y > max_y: max_y = y
                
                # If coordinates exceed default 640x480, expand canvas
                if max_x > 640 or max_y > 480:
                    canvas_w = max(int(max_x) + 50, 640)
                    canvas_h = max(int(max_y) + 50, 480)
                    # Cap at reasonable max (e.g. 1920x1080) to prevent memory issues
                    canvas_w = min(canvas_w, 1920)
                    canvas_h = min(canvas_h, 1080)
            except:
                pass

        # 影像底圖處理
        if has_image:
            # 根據 view_mode 決定底圖
            if view_mode == "yolo_only" or view_mode == "interpolated":
                image = np.zeros_like(frame_data.image)
            else:
                image = frame_data.image.copy()
        else:
            # 無影像輸入但有骨架資料，建立黑色畫布
            image = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
            
        # 如果是 original 模式且有影像輸入，直接返回原圖
        if view_mode == "original" and frame_data and frame_data.image is not None:
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

        # 優先渲染結構化的骨架物件 (平滑/插值後的結果)
        if skeletons and hasattr(skeletons, 'persons'):
            for person in skeletons.persons:
                # yolo_only 模式不使用平滑
                use_smoothed = (view_mode != "yolo_only")
                kpts = person.smoothed_keypoints if use_smoothed and person.smoothed_keypoints is not None else person.keypoints
                
                if kpts is not None and kpts.shape == (17, 3):
                    Visualizer.draw_skeleton(image, kpts, person_id=person.person_id, box=person.box)
        
        # [Fallback Logic] 如果沒有結構化骨架 (skeletons is None)，但有原始 frame_data keypoints，則直接繪製原始點
        # 這樣可以確保在插值緩衝區尚未準備好時(或是純骨架模式下)，仍能顯示畫面
        elif frame_data and frame_data.keypoints:
             try:
                raw_kpts = frame_data.keypoints
                if isinstance(raw_kpts, list):
                    # Try to render raw keypoints directly
                    for i, person_data in enumerate(raw_kpts):
                        kpts_arr = None
                        box = None
                        
                        # Handle different formats
                        if isinstance(person_data, list):
                            kpts_arr = None
                            # 1. Simulator Format: [[box...], [kpt1...], [kpt2...]...]
                            # Usually 18 elements (1 box + 17 keypoints) or more
                            if len(person_data) >= 18 and isinstance(person_data[0], list):
                                try:
                                    # Extract box from first element: [x, y, w, h, score, class]
                                    bd = person_data[0]
                                    if len(bd) >= 4:
                                        x, y, w, h = bd[0], bd[1], bd[2], bd[3]
                                        box = (int(x), int(y), int(w), int(h))
                                    
                                    # Extract keypoints from index 1 to 17
                                    # Each keypoint: [x, y, score, id]
                                    kpts_list = []
                                    # Take next 17 elements
                                    raw_pts = person_data[1:18]
                                    for pt in raw_pts:
                                        # Handle [x, y, w, id] or [x, y, w] formats from simulator
                                        # The simulator sends [x, y, score, id]
                                        if isinstance(pt, list) and len(pt) >= 3:
                                            # x, y, score
                                            # Normalize score if needed (e.g. 0-100 -> 0-1)
                                            # Also check if it's integer coordinates
                                            px, py = pt[0], pt[1]
                                            s = pt[2]
                                            # Simulator might send score as integer 0-100 or float 0-1
                                            if s > 1.0: s /= 100.0
                                            
                                            # IMPORTANT: If coordinates are 0,0 and score is low, visualizer might filter it out
                                            # But simulator sends valid coordinates
                                            kpts_list.append([px, py, s])
                                        else:
                                            kpts_list.append([0, 0, 0])
                                    
                                    kpts_arr = np.array(kpts_list)
                                    
                                    # [DEBUG] Force high confidence if seemingly valid
                                    # Simulator sometimes sends valid points but low confidence?
                                    # Let's trust the score from simulator for now.

                                except Exception as e:
                                    print(f"[DataProcessor] Error parsing simulator format: {e}")

                            # 2. Standard [[x,y,c], [x,y,c]...] format
                            if kpts_arr is None:
                                try:
                                    arr = np.array(person_data)
                                    if arr.shape == (17, 3):
                                        kpts_arr = arr
                                    elif arr.shape == (17, 2):
                                        # Add confidence 1.0
                                        kpts_arr = np.hstack([arr, np.ones((17, 1))])
                                except:
                                    pass

                        elif isinstance(person_data, dict):
                            # Dict format with "keypoints" key
                            if "keypoints" in person_data:
                                arr = np.array(person_data["keypoints"])
                                if arr.shape == (17, 3):
                                    kpts_arr = arr
                            if "box" in person_data:
                                box = person_data["box"]
                                
                        if kpts_arr is not None:
                             # 使用負數 ID 或特殊 ID 來區分這是原始資料
                             Visualizer.draw_skeleton(image, kpts_arr, person_id=i, box=box)
             except Exception as e:
                print(f"[DataProcessor] Error rendering raw keypoints: {e}")

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
