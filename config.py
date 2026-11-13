"""
配置管理 - 严格从 config.json 读取，无默认值
支持带注释的 JSON (// 单行注释, /* */ 多行注释)
"""

import json
import os
import re


class FishingConfig:
    """钓鱼配置类 - 所有参数必须从 config.json 提供"""
    
    REQUIRED_SECTIONS = [
        'keys',
        'detection',
        'anti_detection',
        'bait',
        'window',
        'general',
        'logging'
    ]
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self._load_strict()
    
    def _remove_comments(self, text):
        """去除 JSON 中的注释"""
        # 保留字符串中的 // 和 /*，例如 Windows 路径和 URL。
        pattern = r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/'
        return re.sub(pattern, lambda match: match.group(0) if match.group(0).startswith('"') else ' ', text)
    
    def _load_strict(self):
        """严格加载配置，任何缺失都报错"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 去除注释后解析
        content = self._remove_comments(content)
        config = json.loads(content)
        
        # 检查必需的顶级章节
        for section in self.REQUIRED_SECTIONS:
            if section not in config:
                raise KeyError(f"配置缺少必需章节: {section}")
        
        return config
    
    def get(self, key_path):
        """
        获取配置值，支持点号路径
        例如: get("keys.cast") 获取 keys["cast"]
        任何缺失都报错
        """
        keys = key_path.split('.')
        value = self.config
        path = []
        
        for key in keys:
            path.append(key)
            if not isinstance(value, dict):
                raise KeyError(f"配置路径无效: {'.'.join(path)} 不是字典")
            if key not in value:
                raise KeyError(f"配置缺少参数: {'.'.join(path)}")
            value = value[key]
        
        return value
    
    def set(self, key_path, value):
        """设置配置值"""
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
    
    def save(self):
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)


def get_config(config_path="config.json"):
    """获取配置实例"""
    return FishingConfig(config_path)
