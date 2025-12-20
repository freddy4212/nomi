"""
config.py - 動作識別相關配置
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _resolve_model_path_internal(relative_path: str) -> str:
    """內部使用的路徑解析工具，避免循環導入"""
    if not relative_path:
        return ""
        
    if os.path.isabs(relative_path) or relative_path.startswith(("http://", "https://")):
        return relative_path
    
    from pathlib import Path

    # 1. 優先嘗試在模組內部的 models/ 目錄下尋找 (observation_layer/modules/action/models/)
    action_module_dir = Path(__file__).parent
    internal_models_dir = action_module_dir / "models"
    full_path = internal_models_dir / os.path.basename(relative_path)
    if full_path.exists():
        return str(full_path)
    
    # 2. 嘗試在 observation_layer/ 目錄下尋找 (針對 submodule)
    base_dir = action_module_dir.parent.parent  # observation_layer/
    submodule_path = base_dir / relative_path
    if submodule_path.exists():
        return str(submodule_path)
    
    # 3. 嘗試舊版路徑 (we_mma_2/mmaction2/...)
    project_root = base_dir.parent
    legacy_path = project_root / "we_mma_2" / relative_path
    if legacy_path.exists():
        return str(legacy_path)
    
    return str(full_path)  # 返回預期的內部路徑，即使目前不存在

@dataclass
class ActionRecognizerConfig:
    """MMAction2 動作識別配置"""
    config_file: str = ""
    checkpoint_file: str = ""
    device: str = "cpu"
    action_labels: List[str] = field(default_factory=lambda: [
        "喝水", "吃東西", "刷牙", "梳頭", "掉落物品", "撿起物品", "丟東西", "坐下", "站起", "拍手",
        "閱讀", "寫字", "撕紙", "穿外套", "脫外套", "穿鞋", "脫鞋", "戴眼鏡", "脫眼鏡", "戴帽子",
        "脫帽子", "歡呼", "揮手", "踢東西", "摸口袋", "單腳跳", "跳躍", "打電話", "玩手機", "打字",
        "指向", "拍照", "看時間", "搓手", "點頭/鞠躬", "搖頭", "擦臉", "敬禮", "合十", "交叉雙手",
        "打噴嚏/咳嗽", "踉蹌", "跌倒", "摸頭", "摸胸", "摸背", "摸頸", "噁心/嘔吐", "扇風", "打拳",
        "踢人", "推人", "拍背", "指人", "擁抱", "給東西", "摸他人口袋", "握手", "走向他人", "走離他人"
    ])
    
    def __post_init__(self):
        """初始化後處理：解析模型路徑"""
        # 官方預設 URL (ST-GCN++)
        STGCNPP_URL = "https://download.openmmlab.com/mmaction/v1.0/skeleton/stgcnpp/stgcnpp_8xb16-joint-u100-80e_ntu60-xsub-keypoint-2d/stgcnpp_8xb16-joint-u100-80e_ntu60-xsub-keypoint-2d_20221228-86e1e77a.pth"
        
        if not self.config_file:
            self.config_file = _resolve_model_path_internal(
                "mmaction2/configs/skeleton/stgcnpp/stgcnpp_8xb16-joint-u100-80e_ntu60-xsub-keypoint-2d.py"
            )
        elif not os.path.isabs(self.config_file):
            self.config_file = _resolve_model_path_internal(self.config_file)
            
        if not self.checkpoint_file:
            self.checkpoint_file = STGCNPP_URL
        elif not os.path.isabs(self.checkpoint_file) and not self.checkpoint_file.startswith(("http://", "https://")):
            resolved = _resolve_model_path_internal(self.checkpoint_file)
            # 如果本地檔案不存在，且是 stgcnpp 相關模型，則自動轉向 URL 觸發自動下載
            # 下載後 MMAction2 通常會放在 ~/.cache/torch，但我們這裡的邏輯是為了讓 init_recognizer 知道去哪抓
            if not os.path.exists(resolved) and "stgcnpp" in self.checkpoint_file:
                self.checkpoint_file = STGCNPP_URL
            else:
                self.checkpoint_file = resolved

@dataclass
class SimplifiedActionConfig:
    """簡化動作識別配置"""
    labels: List[str] = field(default_factory=lambda: [
        "坐著", "站立", "走路", "跑步", "跳躍",
        "運動/伸展", "打架/衝突", "蹲下/低姿態", "躺下/跌倒", "靜止/等待"
    ])
    mapping: Dict[int, int] = field(default_factory=lambda: {
        7: 0, 10: 0, 11: 0, 28: 0, 29: 0,
        8: 1, 4: 1, 5: 1, 6: 1, 9: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1,
        18: 1, 19: 1, 20: 1, 24: 1, 31: 1, 34: 1, 35: 1, 36: 1, 39: 1,
        53: 1, 54: 1, 55: 1, 56: 1, 57: 1,
        58: 2, 59: 2,
        25: 4, 26: 4, 27: 4,
        21: 5, 22: 5, 23: 5, 32: 5, 33: 5,
        49: 6, 50: 6, 51: 6, 52: 6,
        41: 8, 42: 8,
        0: 9, 1: 9, 2: 9, 3: 9, 12: 9, 30: 9, 37: 9, 38: 9,
        40: 9, 43: 9, 44: 9, 45: 9, 46: 9, 47: 9, 48: 9
    })

@dataclass
class MotionConfig:
    """動作強度配置"""
    threshold_low: float = 10.0
    threshold_high: float = 30.0
