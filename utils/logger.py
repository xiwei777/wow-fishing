"""
日志模块 - 支持文件和控制台双输出
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from app_paths import output_path


class FishingLogger:
    """钓鱼机器人日志器"""
    
    def __init__(self, config):
        """
        初始化日志器
        :param config: 配置对象，需要支持 get 方法
        """
        self.enabled = config.get("logging.enabled")
        self.level = config.get("logging.level")
        self.log_dir = output_path(config.get("logging.log_dir"))
        self.max_files = config.get("logging.max_files")
        
        self.logger = logging.getLogger("fishing_bot")
        self.logger.setLevel(self._parse_level(self.level))
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
        
        if self.enabled:
            self._setup_handlers()
            self._cleanup_old_logs()
    
    def _parse_level(self, level_str):
        """解析日志级别字符串"""
        levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR
        }
        return levels.get(level_str.lower(), logging.INFO)
    
    def _setup_handlers(self):
        """设置日志处理器"""
        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 文件处理器 - 按日期命名
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(self.log_dir, f"fishing_{today}.log")
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
    
    def _cleanup_old_logs(self):
        """清理旧日志文件，只保留最近 N 天"""
        try:
            log_files = sorted(
                Path(self.log_dir).glob("fishing_*.log"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            for old_file in log_files[self.max_files:]:
                old_file.unlink()
        except Exception:
            pass  # 清理失败不影响运行
    
    def debug(self, msg):
        """调试日志"""
        self.logger.debug(msg)
    
    def info(self, msg):
        """信息日志"""
        self.logger.info(msg)
    
    def warning(self, msg):
        """警告日志"""
        self.logger.warning(msg)
    
    def error(self, msg):
        """错误日志"""
        self.logger.error(msg)
    
    def log_fishing_event(self, event_type, **kwargs):
        """
        记录钓鱼事件
        :param event_type: 事件类型 (cast/catch/miss/bait)
        :param kwargs: 额外信息
        """
        if not self.enabled:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if event_type == "cast":
            self.info(f"[{timestamp}] 🎣 甩竿 #{kwargs.get('cast_num', 0)}")
        elif event_type == "catch":
            self.info(f"[{timestamp}] ✅ 钓到鱼！耗时 {kwargs.get('duration', 0):.1f}s")
        elif event_type == "miss":
            self.info(f"[{timestamp}] ❌ 未检测到鱼漂")
        elif event_type == "bait":
            self.info(f"[{timestamp}] 🎣 自动上饵 (按键: {kwargs.get('key', '5')})")
        elif event_type == "float_found":
            self.info(f"[{timestamp}] 🎯 发现鱼漂 ({kwargs.get('method', 'unknown')}) 置信度:{kwargs.get('conf', 0):.2f}")
        elif event_type == "bite":
            self.info(f"[{timestamp}] 🐟 检测到咬钩！点击收竿")
