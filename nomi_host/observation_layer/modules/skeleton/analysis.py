"""
analysis.py - 骨架分析輔助函式
"""

from collections import deque
from typing import Any, Dict

import numpy as np


def _empty_visibility_result() -> Dict[str, Any]:
    return {
        "upper_visible": 0,
        "lower_visible": 0,
        "upper_ratio": 0.0,
        "lower_ratio": 0.0,
        "is_sitting_likely": False,
        "is_full_body": False,
    }


def analyze_visibility(interpolated_buffer: deque, person_id: int) -> Dict[str, Any]:
    """分析指定人物的骨架可見性"""
    if not interpolated_buffer:
        return _empty_visibility_result()

    latest_frame = interpolated_buffer[-1]
    target_person = None
    for person in latest_frame.persons:
        if person.person_id == person_id:
            target_person = person
            break

    if target_person is None:
        return _empty_visibility_result()

    keypoints = target_person.get_keypoints(use_smoothed=True)

    # COCO 格式: 0=鼻子, 1-4=眼睛耳朵, 5-10=肩膀手肘手腕, 11-12=髖部, 13-14=膝蓋, 15-16=腳踝
    upper_body_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    lower_body_indices = [11, 12, 13, 14, 15, 16]

    confidence_threshold = 0.3

    upper_visible = sum(1 for i in upper_body_indices if keypoints[i, 2] >= confidence_threshold)
    lower_visible = sum(1 for i in lower_body_indices if keypoints[i, 2] >= confidence_threshold)

    upper_ratio = upper_visible / len(upper_body_indices)
    lower_ratio = lower_visible / len(lower_body_indices)

    is_sitting_likely = False

    # 方法 1: 下半身不可見（被桌子等遮擋）
    if upper_ratio >= 0.5 and lower_ratio < 0.6:
        is_sitting_likely = True

    # 方法 2: 基於關鍵點位置判斷（髖、膝、踝的相對位置）
    if not is_sitting_likely and lower_ratio >= 0.5:
        left_hip = keypoints[11]
        right_hip = keypoints[12]
        left_knee = keypoints[13]
        right_knee = keypoints[14]
        left_ankle = keypoints[15]
        right_ankle = keypoints[16]

        hip_valid = left_hip[2] >= confidence_threshold or right_hip[2] >= confidence_threshold
        knee_valid = left_knee[2] >= confidence_threshold or right_knee[2] >= confidence_threshold
        ankle_valid = left_ankle[2] >= confidence_threshold or right_ankle[2] >= confidence_threshold

        if hip_valid and knee_valid:
            hip_y = 0
            hip_count = 0
            if left_hip[2] >= confidence_threshold:
                hip_y += left_hip[1]
                hip_count += 1
            if right_hip[2] >= confidence_threshold:
                hip_y += right_hip[1]
                hip_count += 1
            hip_y = hip_y / hip_count if hip_count > 0 else 0

            knee_y = 0
            knee_count = 0
            if left_knee[2] >= confidence_threshold:
                knee_y += left_knee[1]
                knee_count += 1
            if right_knee[2] >= confidence_threshold:
                knee_y += right_knee[1]
                knee_count += 1
            knee_y = knee_y / knee_count if knee_count > 0 else 0

            nose_y = keypoints[0][1] if keypoints[0][2] >= confidence_threshold else 0
            if nose_y == 0:
                left_shoulder = keypoints[5]
                right_shoulder = keypoints[6]
                if left_shoulder[2] >= confidence_threshold:
                    nose_y = left_shoulder[1]
                elif right_shoulder[2] >= confidence_threshold:
                    nose_y = right_shoulder[1]

            hip_knee_dist = abs(knee_y - hip_y)
            body_height = abs(hip_y - nose_y) if nose_y > 0 else 100
            hip_knee_ratio = hip_knee_dist / body_height if body_height > 0 else 0

            is_thigh_horizontal = False
            if hip_valid and knee_valid:
                if left_hip[2] >= confidence_threshold and left_knee[2] >= confidence_threshold:
                    l_dx = abs(left_knee[0] - left_hip[0])
                    l_dy = abs(left_knee[1] - left_hip[1])
                    if l_dx > l_dy * 1.0:
                        is_thigh_horizontal = True
                if not is_thigh_horizontal and right_hip[2] >= confidence_threshold and right_knee[2] >= confidence_threshold:
                    r_dx = abs(right_knee[0] - right_hip[0])
                    r_dy = abs(right_knee[1] - right_hip[1])
                    if r_dx > r_dy * 1.0:
                        is_thigh_horizontal = True

            if ankle_valid and knee_count > 0:
                ankle_y = 0
                ankle_count = 0
                if left_ankle[2] >= confidence_threshold:
                    ankle_y += left_ankle[1]
                    ankle_count += 1
                if right_ankle[2] >= confidence_threshold:
                    ankle_y += right_ankle[1]
                    ankle_count += 1
                ankle_y = ankle_y / ankle_count if ankle_count > 0 else 0

                knee_ankle_dist = abs(ankle_y - knee_y)

                if hip_knee_ratio < 0.55 and knee_ankle_dist < body_height * 0.55:
                    is_sitting_likely = True
                elif hip_knee_ratio < 0.35:
                    is_sitting_likely = True
                elif is_thigh_horizontal:
                    is_sitting_likely = True
            elif hip_knee_ratio < 0.45:
                is_sitting_likely = True
            elif is_thigh_horizontal:
                is_sitting_likely = True

            # 強制站立檢查
            if hip_knee_ratio > 0.7:
                is_sitting_likely = False

    # 方法 3: 基於邊界框比例判斷
    if not is_sitting_likely and target_person.box is not None:
        _, _, w, h = target_person.box
        if w > 0:
            aspect_ratio = h / w
            if aspect_ratio < 1.35:
                if lower_ratio < 0.6:
                    is_sitting_likely = True
                elif aspect_ratio < 1.0:
                    is_sitting_likely = True

    is_full_body = upper_ratio >= 0.7 and lower_ratio >= 0.7

    visible_mask = keypoints[:, 2] >= confidence_threshold
    visible_count = int(np.sum(visible_mask))
    avg_conf = float(np.mean(keypoints[visible_mask, 2])) if visible_count > 0 else 0.0
    is_valid = visible_count >= 5 and avg_conf >= 0.4

    return {
        "upper_visible": upper_visible,
        "lower_visible": lower_visible,
        "upper_ratio": upper_ratio,
        "lower_ratio": lower_ratio,
        "is_sitting_likely": is_sitting_likely,
        "is_full_body": is_full_body,
        "visible_count": visible_count,
        "avg_conf": avg_conf,
        "is_valid": is_valid,
    }


def compute_motion_magnitude(interpolated_buffer: deque, person_id: int) -> float:
    """計算指定人物的動作幅度（歸一化後位移）"""
    if len(interpolated_buffer) < 5:
        return 0.0

    recent_keypoints = []
    frames_to_check = list(interpolated_buffer)[-min(15, len(interpolated_buffer)) :]

    target_person_latest = None
    for frame in frames_to_check:
        for person in frame.persons:
            if person.person_id == person_id:
                recent_keypoints.append(person.get_keypoints(use_smoothed=True))
                target_person_latest = person
                break

    if len(recent_keypoints) < 2 or target_person_latest is None:
        return 0.0

    _, _, w, h = target_person_latest.box
    bbox_diag = np.sqrt(w ** 2 + h ** 2)
    if bbox_diag < 10:
        bbox_diag = 100.0

    stable_points = [5, 6, 11, 12]

    total_motion = 0.0
    count = 0

    for i in range(1, len(recent_keypoints)):
        prev_kp = recent_keypoints[i - 1]
        curr_kp = recent_keypoints[i]

        frame_motion = 0.0
        frame_count = 0

        for j in range(17):
            if prev_kp[j, 2] > 0.3 and curr_kp[j, 2] > 0.3:
                dist = np.linalg.norm(curr_kp[j, :2] - prev_kp[j, :2])
                weight = 2.0 if j in stable_points else 0.5
                frame_motion += dist * weight
                frame_count += weight

        if frame_count > 0:
            normalized_motion = (frame_motion / frame_count) / bbox_diag * 1000
            total_motion += normalized_motion
            count += 1

    if count == 0:
        return 0.0

    return total_motion / count
