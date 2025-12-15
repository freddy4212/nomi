"""
config.py - 集中管理所有配置參數

這個模組包含：
- 串口連接設定
- GUI 介面設定
- MMAction2 模型設定
- 補幀設定
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class SerialConfig:
    """串口連接配置"""
    default_port: str = "/dev/tty.usbmodem5A4B0478511"
    baudrate: int = 921600
    timeout: float = 1.0


@dataclass
class GUIConfig:
    """GUI 介面配置"""
    window_title: str = "WiseEye2 Visualizer + MMAction2"
    window_size: str = "1200x900"
    canvas_width: int = 640
    canvas_height: int = 480
    action_panel_height: int = 150  # 動作描述區域高度


@dataclass
class ActionRecognizerConfig:
    """MMAction2 動作識別配置"""
    # 模型配置檔案路徑（使用絕對路徑）
    # 推薦使用 NTU RGB+D 60 資料集訓練的模型
    config_file: str = "/Users/freddy/Documents/251006_WiseEye2/sscma-example-we2/we_mma_2/mmaction2/configs/skeleton/posec3d/slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint.py"
    # 模型權重檔案路徑（使用絕對路徑）
    checkpoint_file: str = "/Users/freddy/Documents/251006_WiseEye2/sscma-example-we2/we_mma_2/mmaction2/checkpoints/slowonly_r50_8xb16-u48-240e_ntu60-xsub-keypoint_20220815-38db104b.pth"
    # 設備：'cuda:0' 或 'cpu' 或 'mps'（Apple Silicon）
    device: str = "cpu"
    
    # NTU RGB+D 60 動作標籤（60 類日常動作）
    # 這些動作適合室內場景，與 WiseEye2 的應用情境相符
    action_labels: List[str] = field(default_factory=lambda: [
        # A001-A010: 日常動作
        "喝水", "吃東西", "刷牙", "梳頭", "掉落物品",
        "撿起物品", "丟東西", "穿衣服", "脫衣服", "穿鞋",
        # A011-A020: 日常動作續
        "脫鞋", "穿眼鏡", "脫眼鏡", "戴帽子", "脫帽子",
        "拍手", "閱讀", "寫字", "撕紙", "揮手",
        # A021-A030: 手部動作
        "踢腿", "觸碰口袋", "打電話", "玩手機", "打字",
        "指向", "拍照", "檢查時間", "搓手", "點頭",
        # A031-A040: 身體動作
        "搖頭", "扇風", "打拳", "伸展", "打噴嚏/咳嗽",
        "摀嘴打呵欠", "踉蹌", "頭痛", "胸痛", "背痛",
        # A041-A050: 姿態變化
        "頸痛", "嘔吐", "吹鼻子", "擦臉", "觸摸頭",
        "觸摸胸", "觸摸背", "觸摸頸", "站起", "坐下",
        # A051-A060: 移動與互動
        "行走", "跳躍", "跑步", "蹲下", "揮手致意",
        "抱胸", "鞠躬", "握手", "擁抱", "推/拉"
    ])


@dataclass
class FrameInterpolationConfig:
    """補幀配置"""
    # 目標 FPS（MMAction2 通常需要 30 FPS 的輸入）
    target_fps: int = 15
    # WiseEye2 實際 FPS（1-2 FPS）
    source_fps: float = 1.5
    # 補幀方法：'linear' 或 'copy'
    interpolation_method: str = "linear"
    # 動作識別所需的幀數序列長度
    sequence_length: int = 48
    # 緩衝區大小（保存多少原始幀用於補幀）
    buffer_size: int = 10
    # 骨架平滑係數 (0-1)，越小越平滑但延遲越大
    smoothing_alpha: float = 0.25  # 降低以增強平滑效果
    # 最大速度限制（像素/幀），超過則視為異常跳動
    max_velocity: float = 40.0  # 降低以更嚴格過濾異常跳動
    # 異常跳動時的置信度閾值
    velocity_confidence_threshold: float = 0.6


@dataclass
class SkeletonConfig:
    """骨架配置"""
    # COCO 骨架連接定義
    skeleton_connections: List[Tuple[int, int]] = field(default_factory=lambda: [
        (0, 1), (0, 2), (1, 3), (2, 4),      # 頭部
        (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),  # 手臂
        (5, 11), (6, 12), (11, 12),          # 軀幹
        (11, 13), (13, 15), (12, 14), (14, 16)  # 腿部
    ])
    # 關鍵點數量（COCO 格式）
    num_keypoints: int = 17
    # 關鍵點信心閾值
    confidence_threshold: float = 0.5  # 提高閾值以過濾低置信度的雜訊點


@dataclass
class SimplifiedActionConfig:
    """簡化動作識別配置"""
    # 簡化動作標籤（7類基本動作）
    labels: List[str] = field(default_factory=lambda: [
        "坐著/靜止",      # 0: 靜態姿勢
        "站立/動作",      # 1: 站著做事
        "走動",          # 2: 行走相關
        "跳躍",          # 3: 跳躍動作
        "蹲下/彎腰",     # 4: 彎腰撿東西等
        "打鬥/推擠",     # 5: 衝突動作
        "跌倒/異常",     # 6: 危險狀況
    ])
    
    # NTU60 → 簡化類別映射
    # 索引對應 config.action.action_labels 的順序 (0-59)
    mapping: Dict[int, int] = field(default_factory=lambda: {
        # === 坐著/靜止 (0) ===
        # 喝水, 吃東西, 刷牙, 梳頭, 閱讀, 寫字, 打電話, 玩手機
        0: 0, 1: 0, 2: 0, 3: 0, 16: 0, 17: 0, 22: 0, 23: 0,
        # === 站立/動作 (1) ===
        # 掉落物品, 撿起物品, 丟東西, 穿衣, 脫衣, 穿鞋, 脫鞋, 穿眼鏡, 脫眼鏡, 戴帽, 脫帽
        4: 1, 5: 1, 6: 1, 7: 1, 8: 1, 9: 1, 10: 1, 11: 1, 12: 1, 13: 1, 14: 1,
        # 拍手, 撕紙, 揮手, 踢腿, 摸口袋, 打字, 指向, 拍照, 看時間, 搓手, 點頭
        15: 1, 18: 1, 19: 1, 20: 1, 21: 1, 24: 1, 25: 1, 26: 1, 27: 1, 28: 1, 29: 1,
        # 搖頭, 扇風, 打拳, 伸展, 咳嗽, 哈欠, 頭痛, 胸痛, 背痛, 頸痛, 嘔吐, 吹鼻, 擦臉
        30: 1, 31: 1, 32: 1, 33: 1, 34: 1, 35: 1, 37: 1, 38: 1, 39: 1, 40: 1, 41: 1, 42: 1, 43: 1,
        # 摸頭, 摸胸, 摸背, 摸頸, 站起, 坐下, 揮手致意, 抱胸, 鞠躬, 握手, 擁抱, 推拉
        44: 1, 45: 1, 46: 1, 47: 1, 48: 1, 49: 1, 54: 1, 55: 1, 56: 1, 57: 1, 58: 1, 59: 1,
        # === 走動 (2) ===
        50: 2, # 行走
        # === 跳躍 (3) ===
        51: 3, # 跳躍
        # === 蹲下/彎腰 (4) ===
        53: 4, # 蹲下
        # === 打鬥/推擠 (5) ===
        # (NTU60 中打鬥類較少，部分歸類在站立動作)
        # === 跌倒/異常 (6) ===
        36: 6, # 踉蹌
        # 注意：NTU60 原始標籤中沒有明確的"跌倒"，通常用踉蹌代替
    })


@dataclass
class MotionConfig:
    """動作強度配置"""
    threshold_low: float = 2.0   # 低於此為靜止
    threshold_high: float = 8.0  # 高於此為劇烈


@dataclass
class WebcamConfig:
    """Webcam 測試配置"""
    camera_id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    yolo_model: str = "yolov8n-pose.pt"
    yolo_conf: float = 0.5


@dataclass
class AppConfig:
    """應用程式總配置"""
    serial: SerialConfig = field(default_factory=SerialConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)
    action: ActionRecognizerConfig = field(default_factory=ActionRecognizerConfig)
    interpolation: FrameInterpolationConfig = field(default_factory=FrameInterpolationConfig)
    skeleton: SkeletonConfig = field(default_factory=SkeletonConfig)
    simplified: SimplifiedActionConfig = field(default_factory=SimplifiedActionConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    webcam: WebcamConfig = field(default_factory=WebcamConfig)
    
    # 除錯模式
    debug: bool = True


# 全局配置實例
config = AppConfig()
