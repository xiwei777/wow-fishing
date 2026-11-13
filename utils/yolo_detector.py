"""
YOLOv8 鱼漂检测器
使用训练好的 YOLO 模型预测鱼漂位置
"""

import cv2
import numpy as np
import os
import hashlib
from pathlib import Path
from app_paths import default_model_path

# 尝试导入 ultralytics
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️  ultralytics 未安装，YOLO 检测不可用")
    print("   安装命令: pip install ultralytics")


class YOLOFloatDetector:
    """YOLO 鱼漂检测器"""
    
    def __init__(self, model_path=None):
        """
        初始化 YOLO 检测器
        :param model_path: 模型文件路径
        """
        self.model = None
        self.available = False
        self.model_path = Path(model_path).expanduser().resolve() if model_path else default_model_path()
        self.model_info = {}
        
        if not YOLO_AVAILABLE:
            return
            
        # 不自动下载或静默切换模型，避免误用不同权重。
        if not self.model_path.is_file():
            raise FileNotFoundError(f"未找到权重: {self.model_path}；源码运行请指定 --model，发布包请重新构建。")
        
        try:
            self.model = YOLO(str(self.model_path), task="detect")
            self.model_info = {
                "name": self.model_path.name,
                "sha256": hashlib.sha256(self.model_path.read_bytes()).hexdigest(),
                "size_bytes": self.model_path.stat().st_size,
            }
            self.available = True
            print(f"✅ YOLO 模型加载成功: {self.model_path.name}")
        except Exception as e:
            print(f"⚠️  YOLO 模型加载失败: {e}")
    
    def detect(self, screenshot, conf_threshold=0.5):
        """
        检测鱼漂位置
        :param screenshot: 屏幕截图 (numpy array)
        :param conf_threshold: 置信度阈值
        :return: (x, y, w, h, confidence) 或 None
        """
        if not self.available or self.model is None:
            return None
        
        try:
            # YOLO 推理
            results = self.model(screenshot, conf=conf_threshold, verbose=False, device="cpu")
            
            # 解析结果
            for result in results:
                boxes = result.boxes
                if len(boxes) == 0:
                    continue
                
                # 取置信度最高的框
                best_box = None
                best_conf = 0
                
                for box in boxes:
                    conf = float(box.conf[0])
                    if conf > best_conf:
                        best_conf = conf
                        best_box = box
                
                if best_box is not None:
                    # 获取坐标
                    x1, y1, x2, y2 = best_box.xyxy[0].cpu().numpy()
                    x, y = int(x1), int(y1)
                    w, h = int(x2 - x1), int(y2 - y1)
                    conf = float(best_box.conf[0])
                    
                    return (x, y, w, h, conf)
            
            return None
            
        except Exception as e:
            print(f"YOLO 检测错误: {e}")
            return None
    
    def is_available(self):
        """检查检测器是否可用"""
        return self.available
