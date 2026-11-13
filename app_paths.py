"""应用资源与用户数据路径：支持源码、Windows EXE 和 macOS APP。"""

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "WoWFishing"
VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parent


def resource_path(relative):
    """内置资源只读；不受双击启动时工作目录影响。"""
    return Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / relative


def data_dir():
    """返回用户可写目录，可用环境变量覆盖以便测试和迁移。"""
    override = os.environ.get("WOW_FISHING_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / APP_NAME
    return Path.home() / ".local/share" / APP_NAME


def output_path(value):
    """配置中的相对输出路径统一位于用户数据目录。"""
    path = Path(value).expanduser()
    return path if path.is_absolute() else data_dir() / path


def ensure_user_config():
    """首次启动复制完整默认配置，后续启动保留用户配置。"""
    target = data_dir() / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(resource_path("resources/default_config.json"), target)
    return target


def default_model_path():
    """发布包使用构建时指定的权重；源码使用私有仓库当前权重。"""
    bundled = resource_path("models/best.pt")
    if bundled.is_file():
        return bundled
    return resource_path("models/best_v4.pt")
