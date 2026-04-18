"""
reid_extractor.py - ReID 人物重識別特徵提取器

使用 person-reidentification-retail-0300 模型提取人員特徵向量
流程與邏輯參考 WiseEye2 tflm_yolov8n_pose_reid

模型資訊：
- 輸入尺寸: 256x128 (HxW)
- 輸出維度: 256 維特徵向量
- 來源: OpenVINO Model Zoo

使用方式：
    extractor = ReIDExtractor()
    feature = extractor.extract_features(person_crop)
"""

import os
from typing import Optional, Tuple

import cv2
import numpy as np

# ReID 模型參數（person_reid_int8）
REID_INPUT_HEIGHT = 256
REID_INPUT_WIDTH = 128
REID_FEATURE_DIM = 512  # int8 模型輸出 512 維


class ReIDExtractor:
    """ReID 人物重識別特徵提取器"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        初始化 ReID 提取器
        
        Args:
            model_path: TFLite 模型路徑（可選）
        """
        self.model = None
        self.ready = False
        self.mode = "simulated"  # "tflite" 或 "simulated"
        
        # 尋找模型路徑
        if model_path is None:
            model_path = self._find_model_path()
        
        self.model_path = model_path
        self._init_model()
    
    def _find_model_path(self) -> Optional[str]:
        """尋找 ReID 模型路徑"""
        search_paths = [
            # 1. reid/models 目錄下（int8 模型，與 WE2 相同）
            os.path.join(os.path.dirname(__file__), 'models', 'person_reid_int8.tflite'),
            # 2. model_zoo 目錄下
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                        'model_zoo', 'person_reid_int8_vela_64_0x600000.tflite'),
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _init_model(self):
        """初始化 TFLite 模型"""
        if self.model_path is None or not os.path.exists(self.model_path):
            print(f"⚠ ReID 模型未找到，使用模擬模式")
            self.mode = "simulated"
            self.ready = True
            return
        
        try:
            import tensorflow as tf

            # 載入 TFLite 模型
            self.interpreter = tf.lite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            
            # 獲取輸入輸出資訊
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # 驗證模型
            input_shape = self.input_details[0]['shape']
            print(f"✓ 已載入 ReID 模型: {self.model_path}")
            print(f"  輸入形狀: {input_shape}")
            print(f"  輸出形狀: {self.output_details[0]['shape']}")
            
            self.mode = "tflite"
            self.ready = True
            
        except ImportError:
            print("⚠ TensorFlow 未安裝，使用模擬模式")
            self.mode = "simulated"
            self.ready = True
        except Exception as e:
            print(f"⚠ ReID 模型載入失敗: {e}，使用模擬模式")
            import traceback
            traceback.print_exc()
            self.mode = "simulated"
            self.ready = True
    
    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        預處理影像（與 WiseEye2 相同的方式）
        
        Args:
            image: BGR 影像
            
        Returns:
            預處理後的影像，格式根據模型需求（int8 或 float32）
        """
        # 調整尺寸到模型輸入大小
        resized = cv2.resize(image, (REID_INPUT_WIDTH, REID_INPUT_HEIGHT))
        
        # BGR -> RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # 檢查模型輸入類型
        if hasattr(self, 'input_details') and self.input_details:
            input_dtype = self.input_details[0]['dtype']
            
            if input_dtype == np.int8:
                # INT8 量化模型：與 WiseEye2 相同的預處理方式
                # 正規化到 [-1, 1] 然後量化到 [-127, 127]
                normalized = (rgb.astype(np.float32) / 255.0 - 0.5) * 2.0
                quantized = (normalized * 127.0).astype(np.int8)
                batched = np.expand_dims(quantized, axis=0)
                return batched
            
            elif input_dtype == np.uint8:
                # UINT8 量化模型：直接使用 0-255 範圍
                batched = np.expand_dims(rgb, axis=0).astype(np.uint8)
                return batched
        
        # 預設：float32
        normalized = rgb.astype(np.float32) / 255.0
        batched = np.expand_dims(normalized, axis=0)
        return batched
    
    def extract_features(self, person_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        從人員裁切影像提取 ReID 特徵向量
        
        Args:
            person_crop: BGR 影像（人員區域裁切）
            
        Returns:
            256 維特徵向量，或 None（如果失敗）
        """
        if not self.ready:
            return None
        
        if person_crop is None or person_crop.size == 0:
            return None
        
        if self.mode == "tflite":
            return self._extract_tflite(person_crop)
        else:
            return self._extract_simulated(person_crop)
    
    def _extract_tflite(self, person_crop: np.ndarray) -> Optional[np.ndarray]:
        """使用 TFLite 模型提取特徵"""
        try:
            # 預處理
            input_data = self.preprocess(person_crop)
            
            # 設置輸入
            input_index = self.input_details[0]['index']
            self.interpreter.set_tensor(input_index, input_data)
            
            # 執行推理
            self.interpreter.invoke()
            
            # 獲取輸出
            output_index = self.output_details[0]['index']
            output_data = self.interpreter.get_tensor(output_index)
            
            # 扁平化
            output_flat = output_data.flatten()
            
            # 如果輸出是 int8，需要反量化（與 WiseEye2 相同方式）
            output_dtype = self.output_details[0]['dtype']
            if output_dtype == np.int8:
                # 獲取量化參數
                quant_params = self.output_details[0].get('quantization_parameters', {})
                scale = quant_params.get('scales', [1.0])[0] if quant_params.get('scales') else 1.0
                zero_point = quant_params.get('zero_points', [0])[0] if quant_params.get('zero_points') else 0
                
                # 反量化：(output - zero_point) * scale
                feature = (output_flat.astype(np.float32) - zero_point) * scale
            else:
                feature = output_flat.astype(np.float32)
            
            # L2 正規化
            norm = np.linalg.norm(feature)
            if norm > 0:
                feature = feature / norm
            
            return feature
            
        except Exception as e:
            print(f"ReID TFLite Error: {e}")
            import traceback
            traceback.print_exc()
            return self._extract_simulated(person_crop)
    
    def _extract_simulated(self, person_crop: np.ndarray) -> np.ndarray:
        """
        模擬特徵提取（當沒有真實模型時使用）
        
        基於影像內容生成偽隨機但一致的特徵向量
        同一張影像會產生相同的特徵
        """
        # 調整尺寸
        resized = cv2.resize(person_crop, (REID_INPUT_WIDTH, REID_INPUT_HEIGHT))
        
        # 使用影像的統計特徵生成偽隨機種子
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        
        # 計算多個統計量作為種子
        mean_val = np.mean(gray)
        std_val = np.std(gray)
        
        # 將影像分成區域計算特徵
        h, w = gray.shape
        block_h, block_w = h // 8, w // 4
        
        features = []
        for i in range(8):
            for j in range(4):
                block = gray[i*block_h:(i+1)*block_h, j*block_w:(j+1)*block_w]
                features.append(np.mean(block))
                features.append(np.std(block))
                features.append(np.max(block) - np.min(block))
                features.append(np.median(block))
        
        # 填充到 256 維
        feature = np.array(features[:REID_FEATURE_DIM], dtype=np.float32)
        if len(feature) < REID_FEATURE_DIM:
            # 使用 histogram 填充剩餘維度
            hist = cv2.calcHist([gray], [0], None, [REID_FEATURE_DIM - len(feature)], [0, 256])
            feature = np.concatenate([feature, hist.flatten()])
        
        # L2 正規化
        norm = np.linalg.norm(feature)
        if norm > 0:
            feature = feature / norm
        
        return feature[:REID_FEATURE_DIM]
    
    def crop_person(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
                   padding: float = 0.1) -> Optional[np.ndarray]:
        """
        從影像中裁切人員區域
        
        Args:
            frame: 完整 BGR 影像
            x1, y1, x2, y2: 邊界框座標
            padding: 邊緣填充比例
            
        Returns:
            裁切後的人員影像
        """
        h, w = frame.shape[:2]
        
        # 計算填充
        box_w = x2 - x1
        box_h = y2 - y1
        pad_w = int(box_w * padding)
        pad_h = int(box_h * padding)
        
        # 擴展邊界框（加入填充）
        x1_pad = max(0, x1 - pad_w)
        y1_pad = max(0, y1 - pad_h)
        x2_pad = min(w, x2 + pad_w)
        y2_pad = min(h, y2 + pad_h)
        
        # 裁切
        crop = frame[y1_pad:y2_pad, x1_pad:x2_pad]
        
        if crop.size == 0:
            return None
        
        return crop
    
    def compute_similarity(self, feature1: np.ndarray, feature2: np.ndarray) -> float:
        """
        計算兩個特徵向量的相似度（餘弦相似度）
        
        Args:
            feature1: 第一個特徵向量
            feature2: 第二個特徵向量
            
        Returns:
            相似度分數 [0, 1]
        """
        if feature1 is None or feature2 is None:
            return 0.0
        
        # 餘弦相似度
        dot_product = np.dot(feature1, feature2)
        norm1 = np.linalg.norm(feature1)
        norm2 = np.linalg.norm(feature2)
        
        if norm1 > 0 and norm2 > 0:
            similarity = dot_product / (norm1 * norm2)
            # 映射到 [0, 1]
            return float((similarity + 1) / 2)
        
        return 0.0
    
    def get_info(self) -> dict:
        """獲取模型資訊"""
        return {
            "mode": self.mode,
            "model_path": self.model_path,
            "ready": self.ready,
            "input_size": (REID_INPUT_HEIGHT, REID_INPUT_WIDTH),
            "feature_dim": REID_FEATURE_DIM,
        }
