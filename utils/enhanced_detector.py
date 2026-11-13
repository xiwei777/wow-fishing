"""
咬钩检测器
只使用像素差异检测鱼漂晃动
"""

import cv2
import numpy as np
from collections import deque
from datetime import datetime
from pathlib import Path

def ts_print(*args, **kwargs):
    """带时间戳的打印"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}]", *args, **kwargs)


class EnhancedBiteDetector:
    """
    像素差异咬钩检测器
    只使用像素变化检测鱼漂晃动，不使用轮廓检测
    """
    
    def __init__(self, 
                 pixel_threshold=30,      # 像素差异阈值
                 consecutive_frames=2,    # 连续检测帧数
                 trigger_ratio=0.015,     # 像素变化触发比例
                 min_ratio=0.00001,       # 最小记录比例
                 history_size=10,
                 output_dir=None):
        """
        :param pixel_threshold: 像素差异阈值（0-255）
        :param consecutive_frames: 连续检测帧数
        :param trigger_ratio: 像素变化触发比例（如0.015表示1.5%）
        :param min_ratio: 最小记录比例（用于调试打印）
        :param history_size: 历史帧数
        """
        self.pixel_threshold = pixel_threshold
        self.consecutive_frames = consecutive_frames
        self.trigger_ratio = trigger_ratio
        self.min_ratio = min_ratio
        self.history_size = history_size
        self.output_dir = Path(output_dir) if output_dir else None
        
        self.prev_frame = None
        self.change_count = 0
        self.frame_history = deque(maxlen=history_size)
        self.last_metrics = {}
    
    def reset(self):
        """重置检测器"""
        self.prev_frame = None
        self.change_count = 0
        self.frame_history.clear()
        self.last_metrics = {}
    
    def detect(self, screenshot, float_position, screen_width=None, screen_height=None):
        """
        检测是否咬钩 - 只使用像素差异
        :param screenshot: 屏幕截图
        :param float_position: 鱼漂位置 (x, y, w, h, conf, method)
        :param screen_width: 屏幕宽度（用于计算ROI）
        :param screen_height: 屏幕高度（用于计算ROI）
        :return: True/False 是否咬钩
        """
        if float_position is None:
            return False
        
        x, y, w, h = float_position[:4]
        
        # 提取鱼漂周围区域（扩大一点范围）
        roi_size = max(w, h) * 3
        roi_x1 = max(0, int(x + w/2 - roi_size/2))
        roi_y1 = max(0, int(y + h/2 - roi_size/2))
        roi_x2 = min(screenshot.shape[1], roi_x1 + roi_size)
        roi_y2 = min(screenshot.shape[0], roi_y1 + roi_size)
        
        roi = screenshot[roi_y1:roi_y2, roi_x1:roi_x2]
        
        if roi.size == 0:
            return False
        
        # 转换为灰度并缩小尺寸加快处理
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray, (gray.shape[1], gray.shape[0]))
        
        # 像素差异检测
        pixel_trigger = False
        change_ratio = 0
        if self.prev_frame is not None and self.prev_frame.shape == gray_small.shape:
            diff = cv2.absdiff(self.prev_frame, gray_small)
            non_zero = np.count_nonzero(diff > self.pixel_threshold)
            change_ratio = non_zero / diff.size
            pixel_trigger = change_ratio > self.trigger_ratio
        
        self.prev_frame = gray_small
        
        # 保存历史
        self.frame_history.append({
            'roi': gray.copy(),
            'pixel_change': change_ratio,
            'pixel_trigger': pixel_trigger
        })
        
        # 判断是否触发
        trigger_count = 1 if pixel_trigger else 0
        
        # 调试时打印检测数据
        if change_ratio > self.min_ratio:
            ts_print(f"      [检测数据] 像素变化:{change_ratio:.2%} 触发:{pixel_trigger} 连续帧:{self.change_count}")
            
            # 保存检测区域图片
            if self.output_dir is not None:
                self.output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = self.output_dir / f"roi_{timestamp}_{change_ratio:.3f}.png"
                from utils.image_io import write_image
                write_image(filename, gray)
        
        # 更新连续检测计数
        if trigger_count > 0:
            self.change_count += 1
        else:
            self.change_count = 0
        
        # 保存指标供调试
        self.last_metrics = {
            'change_ratio': change_ratio,
            'pixel_trigger': pixel_trigger,
            'trigger_count': trigger_count,
            'consecutive_count': self.change_count
        }
        
        # 触发条件：连续N帧检测到变化
        is_bite = self.change_count >= self.consecutive_frames
        
        return is_bite
    
    def get_debug_info(self):
        """获取调试信息"""
        return self.last_metrics.copy()
