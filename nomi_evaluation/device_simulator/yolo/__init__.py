"""
yolo/__init__.py - YOLO 姿態估計模組

提供 YOLO-Pose 骨架提取功能
支援 YOLOv8n-pose 和 YOLO11n-pose
"""

from .pose_extractor import PoseExtractor, YOLOModel

__all__ = ['PoseExtractor', 'YOLOModel']
