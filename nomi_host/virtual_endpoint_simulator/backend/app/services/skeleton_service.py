from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from ..config import DEFAULT_DATASET_DIR

logger = logging.getLogger(__name__)

ACTION_PATTERN = re.compile(r"A(\d{3})")

JOINT_COLUMNS = [
    "x",
    "y",
    "z",
    "depthX",
    "depthY",
    "colorX",
    "colorY",
    "orientationW",
    "orientationX",
    "orientationY",
    "orientationZ",
    "trackingState",
]

COCO_TO_NTU = {
    0: 3,   # Nose -> Head
    1: 3,   # LEye -> Head
    2: 3,   # REye -> Head
    3: 3,   # LEar -> Head
    4: 3,   # REar -> Head
    5: 4,   # LShoulder -> LShoulder
    6: 8,   # RShoulder -> RShoulder
    7: 5,   # LElbow -> LElbow
    8: 9,   # RElbow -> RElbow
    9: 6,   # LWrist -> LWrist
    10: 10, # RWrist -> RWrist
    11: 12, # LHip -> LHip
    12: 16, # RHip -> RHip
    13: 13, # LKnee -> LKnee
    14: 17, # RKnee -> RKnee
    15: 14, # LAnkle -> LAnkle
    16: 18, # RAnkle -> RAnkle
}

FACE_POINTS = {0, 1, 2, 3, 4}

NTU_ACTION_LABELS = {
    "A001": "drink water",
    "A002": "eat meal",
    "A003": "brush teeth",
    "A004": "brush hair",
    "A005": "drop",
    "A006": "pick up",
    "A007": "throw",
    "A008": "sit down",
    "A009": "stand up",
    "A010": "clapping",
    "A011": "reading",
    "A012": "writing",
    "A013": "tear up paper",
    "A014": "put on jacket",
    "A015": "take off jacket",
    "A016": "put on a shoe",
    "A017": "take off a shoe",
    "A018": "put on glasses",
    "A019": "take off glasses",
    "A020": "put on a hat/cap",
    "A021": "take off a hat/cap",
    "A022": "cheer up",
    "A023": "hand waving",
    "A024": "kicking something",
    "A025": "reach into pocket",
    "A026": "hopping",
    "A027": "jump up",
    "A028": "phone call",
    "A029": "play with phone/tablet",
    "A030": "type on a keyboard",
    "A031": "point to something",
    "A032": "taking a selfie",
    "A033": "check time (from watch)",
    "A034": "rub two hands",
    "A035": "nod head/bow",
    "A036": "shake head",
    "A037": "wipe face",
    "A038": "salute",
    "A039": "put palms together",
    "A040": "cross hands in front",
    "A041": "sneeze/cough",
    "A042": "staggering",
    "A043": "falling down",
    "A044": "headache",
    "A045": "chest pain",
    "A046": "back pain",
    "A047": "neck pain",
    "A048": "nausea/vomiting",
    "A049": "fan self",
    "A050": "punch/slap",
    "A051": "kicking",
    "A052": "pushing",
    "A053": "pat on back",
    "A054": "point finger",
    "A055": "hugging",
    "A056": "giving object",
    "A057": "touch pocket",
    "A058": "shaking hands",
    "A059": "walking towards",
    "A060": "walking apart",
}


@dataclass
class SkeletonFrame:
    frame_no: int
    people: List[List[Any]]


class SkeletonService:
    def __init__(self, dataset_dir: Path | None = None):
        self.dataset_dir = dataset_dir or DEFAULT_DATASET_DIR
        logger.info(f"Initializing SkeletonService with dataset_dir: {self.dataset_dir}")
        if not self.dataset_dir.exists():
            logger.error(f"Dataset directory NOT FOUND: {self.dataset_dir}")
        else:
            logger.info(f"Dataset directory exists: {self.dataset_dir}")
            # Perform a quick scan on init to verify
            try:
                count = len(list(self.dataset_dir.glob("*.skeleton")))
                logger.info(f"Startup Scan: Found {count} .skeleton files in {self.dataset_dir}")
            except Exception as e:
                logger.error(f"Startup Scan Failed: {e}")

    def _extract_action_code(self, file_name: str) -> str:
        match = ACTION_PATTERN.search(file_name)
        if not match:
            logger.debug(f"Could not extract action code from filename: {file_name}")
            return "A000"
        return f"A{int(match.group(1)):03d}"

    def list_action_summary(self) -> List[Dict[str, Any]]:
        counts = {f"A{i:03d}": 0 for i in range(1, 121)} # NTU Action 1-120
        logger.info(f"Scanning for actions in: {self.dataset_dir}/*.skeleton")
        total_found = 0
        sample_codes = []
        for path in self.dataset_dir.glob("*.skeleton"):
            total_found += 1
            action_code = self._extract_action_code(path.name)
            if len(sample_codes) < 5:
                sample_codes.append(f"{path.name} -> {action_code}")
            if action_code in counts:
                counts[action_code] += 1
        
        logger.info(f"Scan complete. Total files found: {total_found}")
        logger.info(f"Sample extractions: {sample_codes}")

        return [
            {
                "code": code,
                "label": f"{code}: {NTU_ACTION_LABELS.get(code, 'Action ' + code)}",
                "file_count": counts[code],
            }
            for code in sorted(counts.keys())
        ]

    def list_files_by_action(self, action_code: str) -> List[Dict[str, str]]:
        action_code = action_code.upper()
        logger.info(f"Listing files for action: {action_code}")
        matched = []
        for path in sorted(self.dataset_dir.glob("*.skeleton")):
            if self._extract_action_code(path.name) == action_code:
                try:
                    with path.open("r", encoding="utf-8") as fp:
                        total_frames = int(fp.readline().strip())
                except Exception:
                    total_frames = 0
                matched.append({
                    "file_name": path.name,
                    "action_code": action_code,
                    "total_frames": total_frames,
                })
        
        logger.info(f"Found {len(matched)} files for action {action_code}")
        return matched

    def get_frame_count(self, file_name: str) -> int:
        file_path = self.dataset_dir / file_name
        with file_path.open("r", encoding="utf-8") as fp:
            first = fp.readline().strip()
        return int(first)

    def build_packet(self, file_name: str, frame_no: int) -> Dict[str, Any]:
        action_code = self._extract_action_code(file_name)
        people = self._get_frame_people(file_name, frame_no)

        packet = {
            "type": 0,
            "name": "INVOKE",
            "code": 0,
            "data": {
                "image": "",
                "keypoints": people,
                "reid_results": [],
                "basic_info": {
                    "name": "VIRTUAL_WE2",
                    "ver": "1.0",
                    "device_id": "8538000D",
                },
                "frame_info": {
                    "frame_no": frame_no,
                    "count": 1,
                    "algo_tick": 0,
                    "action": action_code,
                    "file_name": file_name,
                    "source": "ntu_skeleton",
                },
            },
        }
        return packet

    def get_file_meta(self, file_name: str) -> Dict[str, Any]:
        return {
            "file_name": file_name,
            "action_code": self._extract_action_code(file_name),
            "total_frames": self.get_frame_count(file_name),
        }

    def _load_file_lines(self, file_name: str) -> List[str]:
        file_path = self.dataset_dir / file_name
        if not file_path.exists():
            logger.error(f"File NOT FOUND: {file_path}")
            raise FileNotFoundError(f"Skeleton file not found: {file_name}")
        return file_path.read_text(encoding="utf-8").splitlines()

    @lru_cache(maxsize=16)
    def _parse_all_frames(self, file_name: str) -> Tuple[SkeletonFrame, ...]:
        lines = self._load_file_lines(file_name)
        idx = 0
        frame_total = int(lines[idx].strip())
        idx += 1

        frames: List[SkeletonFrame] = []

        for frame_no in range(frame_total):
            body_count = int(lines[idx].strip())
            idx += 1

            people: List[List[Any]] = []

            for body_index in range(body_count):
                # Read Body Info Line
                body_info_line = lines[idx].strip()
                idx += 1
                
                # Check for joint count
                try:
                    joint_count = int(lines[idx].strip())
                except ValueError:
                    # Fallback or error handling if line is not integer
                    # Maybe previous line wasn't body info? 
                    # But per NTU format, it should be.
                    logger.error(f"Error parsing joint count at line {idx}: {lines[idx]}")
                    joint_count = 25 # Default NTU
                
                idx += 1

                joint_lines = lines[idx : idx + joint_count]
                idx += joint_count

                df = pd.read_csv(
                    StringIO("\n".join(joint_lines)),
                    sep=r"\s+",
                    header=None,
                    names=JOINT_COLUMNS,
                )

                # Use body_index (0 based) as target_id to ensure continuity across files
                # UNLESS the file actually has multiple bodies, then they will be 0, 1...
                # This ensures that simplistic single-person files always map to ID 0.
                person = self._ntu_to_coco17_person(df, body_index)
                if person:
                    people.append(person)

            frames.append(SkeletonFrame(frame_no=frame_no, people=people))

        return tuple(frames)

    def _get_frame_people(self, file_name: str, frame_no: int) -> List[List[Any]]:
        frames = self._parse_all_frames(file_name)
        if frame_no < 0 or frame_no >= len(frames):
            raise IndexError(f"frame_no out of range: {frame_no}")
        return frames[frame_no].people

    def _joint_conf(self, tracking_state: float) -> float:
            # trackingState: 0=Not Tracked, 1=Inferred, 2=Tracked
            # We map this to a confidence score 0.0-1.0 with some noise to simulate real detection
            base_conf = 0.0
            ts = int(tracking_state)
            if ts == 2:
                # Tracked: High confidence (0.85 - 0.99)
                base_conf = random.uniform(0.85, 0.99)
            elif ts == 1:
                # Inferred: Medium confidence (0.30 - 0.60)
                base_conf = random.uniform(0.30, 0.60)
            
            return base_conf

    def _ntu_to_coco17_person(self, joints_df: pd.DataFrame, target_id: int) -> List[Any]:
        keypoints: List[List[Any]] = []

        for coco_idx in range(17):
            ntu_idx = COCO_TO_NTU.get(coco_idx)
            if ntu_idx is None:
                continue

            # Ensure ntu_idx is within bounds of the joints_df
            if ntu_idx >= len(joints_df):
                logger.warning(f"ntu_idx {ntu_idx} out of bounds for joints_df (len: {len(joints_df)})")
                keypoints.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, int(target_id)])
                continue

            row = joints_df.iloc[ntu_idx]
            
            # NTU RGB-D raw joints_df typically uses columns 5, 6 for Color Space X, Y
            # Let's be safer and use positional index if column names are tricky
            # According to JOINT_COLUMNS: x(0), y(1), z(2), dX(3), dY(4), cX(5), cY(6)
            try:
                x = float(row["colorX"])
                y = float(row["colorY"])
                x_3d = float(row["x"])
                y_3d = float(row["y"])
                z_3d = float(row["z"])
                conf = self._joint_conf(row["trackingState"])
            except (KeyError, ValueError):
                # Fallback to positional if names fail
                x = float(row.iloc[5])
                y = float(row.iloc[6])
                x_3d = float(row.iloc[0])
                y_3d = float(row.iloc[1])
                z_3d = float(row.iloc[2])
                conf = self._joint_conf(row.iloc[11])

            if coco_idx in FACE_POINTS:
                conf = conf * 0.6

            # RESTORED: Full 3D coordinates for Visualization [x, y, conf, x3, y3, z3, target_id]
            # UDP Sending will strip this later.
            keypoints.append([x, y, conf, x_3d, y_3d, z_3d, int(target_id)])

        valid_points = [(point[0], point[1]) for point in keypoints if point[2] > 0.05]
        if not valid_points:
            return []

        xs = [point[0] for point in valid_points]
        ys = [point[1] for point in valid_points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        width = max(0.0, x_max - x_min)
        height = max(0.0, y_max - y_min)
        
        avg_conf = sum(point[2] for point in keypoints) / len(keypoints)
        bbox_conf = float(avg_conf * 100.0)

        # BBox
        bbox = [x_min, y_min, width, height, bbox_conf, int(target_id)]
        
        # We return the "Rich" format with BBox at index 0
        return [bbox] + keypoints

    def convert_to_yolo_format(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert the rich packet format to the specific YOLO JSON structure required by the user.
        Structure:
        {
            "frame_info": { "frame_no": 1, "count": 1, "algo_tick": 0 },
            "basic_info": { "name": "VIRTUAL_WE2", "ver": "1.0", "device_id": "8538000D" },
            "image": "",
            "keypoints": [ 
                [ 
                  [x1, y1, x2, y2, score, label_index], 
                  [x, y, s, i], 
                  [x, y, s, i], ... 
                ] 
            ],
            "reid_results": []
        }
        """
        # The input 'packet' from build_packet usually mimics the WE2 output wrapper:
        # { "type": 0, "name": "INVOKE", "code": 0, "data": { ... } }
        # The user wants ONLY the inner data part, formatted specifically.
        
        data = packet.get("data", packet) # Handle if it's already unwrapped or not
        
        # 1. Basic Info
        basic_info = {
            "name": "VIRTUAL_WE2",
            "ver": "1.0",
            "device_id": "8538000D"
        }
        
        # 2. Frame Info
        # Extract from existing data or use defaults
        fi = data.get("frame_info", {})
        frame_info = {
            "frame_no": fi.get("frame_no", 1),
            "count": fi.get("count", 1),
            "algo_tick": 0
        }
        # Preserve ground truth metadata for evaluation
        if fi.get("action"):
            frame_info["action"] = fi["action"]
        if fi.get("file_name"):
            frame_info["file_name"] = fi["file_name"]
        if fi.get("source"):
            frame_info["source"] = fi["source"]
        
        # 3. Keypoints Processing
        # Input 'data["keypoints"]' (Rich) -> Target 'keypoints' (YOLO)
        # Rich Format (from build_packet): 
        #   [ [bbox_x, bbox_y, bbox_w, bbox_h, conf, id], [x,y,conf,x3,y3,z3,id]... ]
        
        output_keypoints = []
        
        rich_people = data.get("keypoints", [])
        for person in rich_people:
            if not person: continue
            
            # --- Spec Check ---
            # User provided example:
            # "keypoints": [[[71, 66, 190, 174, 78, 0], [169, 120, 96, 0], ...]]
            #
            # Format Analysis:
            # Element 0 (BBox): [71, 66, 190, 174, 78, 0]
            #   -> [x, y, w, h, score(int), class(int)]
            #   This matches the provided sample format exactly.
            #
            # Element 1+ (Keypoints): [169, 120, 96, 0]
            #   -> [x, y, score(int), index(int)]
            
            person_out = []
            
            # 3a. Bounding Box
            rich_bbox = person[0] 
            # rich_bbox: [x, y, w, h, score(float 0-100), id]
            x = int(rich_bbox[0])
            y = int(rich_bbox[1])
            w = int(rich_bbox[2])
            h = int(rich_bbox[3])
            score_bbox = int(rich_bbox[4]) # Already 0-100 in build_packet
            class_id = 0 # Default person class
            
            bbox_yolo = [x, y, w, h, score_bbox, class_id]
            person_out.append(bbox_yolo)
            
            # 3b. Keypoints
            # Rich kpt: [x, y, conf(0-1), x3, y3, z3, id]
            for i, kpt in enumerate(person[1:]):
                k_x = int(kpt[0])
                k_y = int(kpt[1])
                k_score = int(kpt[2] * 100) # Convert 0.0-1.0 to 0-100
                if k_score > 100: k_score = 100
                k_idx = i # implicit index based on order
                
                # Format: [x, y, score, index]
                kpt_yolo = [k_x, k_y, k_score, k_idx]
                person_out.append(kpt_yolo)
            
            output_keypoints.append(person_out)

        # 4. Construct Final Dict
        yolo_packet = {
            "frame_info": frame_info,
            "basic_info": basic_info,
            "image": "",
            "keypoints": output_keypoints,
            "reid_results": []
        }
        
        return yolo_packet

skeleton_service = SkeletonService()
