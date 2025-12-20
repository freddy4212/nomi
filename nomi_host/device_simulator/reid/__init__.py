"""
reid/__init__.py - ReID 人物重識別模組

提供與 WiseEye2 tflm_yolov8_pose_reid 相容的 ReID 功能
"""

from .reid_extractor import ReIDExtractor

__all__ = ['ReIDExtractor']
