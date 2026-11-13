"""macOS/Windows 游戏窗口截图与坐标转换。

Windows 使用 DPI-aware 客户区物理像素；macOS 使用 Quartz 桌面逻辑点，
截图统一缩放为对应窗口矩形尺寸。截图失败不会切换坐标系后继续点击。
"""

import sys
import cv2
import numpy as np
from utils.platform_setup import setup_dpi_awareness

setup_dpi_awareness()
import pyautogui

MACOS = sys.platform == 'darwin'
WINDOWS = sys.platform == 'win32'
if MACOS:
    import Quartz
if WINDOWS:
    from utils import windows_window


class WindowUnavailable(RuntimeError):
    """游戏窗口不存在、失去焦点或无法截图。"""


def get_screen_scale():
    if MACOS:
        mode = Quartz.CGDisplayCopyDisplayMode(Quartz.CGMainDisplayID())
        return Quartz.CGDisplayModeGetPixelWidth(mode) / Quartz.CGDisplayModeGetWidth(mode)
    return 1.0


def _mac_info(window_id=None, title_contains=None, owner_name=None):
    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
    for info in windows:
        if info.get('kCGWindowLayer', 0) != 0:
            continue
        if window_id is not None:
            if info.get('kCGWindowNumber') == window_id:
                return info
        else:
            owner, title = info.get('kCGWindowOwnerName', ''), info.get('kCGWindowName', '')
            if ((owner_name and owner.casefold() == owner_name.casefold()) or
                    (title_contains and title_contains.casefold() in title.casefold())):
                bounds = info.get('kCGWindowBounds', {})
                if bounds.get('Width', 0) > 0 and bounds.get('Height', 0) > 0:
                    return info
    return None


class GameWindow:
    """保持截图坐标和点击坐标一致，并检查游戏前台状态。"""

    def __init__(self, config):
        self.enabled = config.get('window.enabled')
        self.title_contains = config.get('window.title_contains')
        self.owner_name = config.get('window.owner_name')
        self.manual_offset = config.get('window.manual_offset')
        self.window_id = None
        self.window_info = None
        self.bounds = None
        self.scale = get_screen_scale()
        self.last_capture_rect = None

    def find(self):
        if WINDOWS:
            result = windows_window.find_window(self.title_contains, self.owner_name)
            if result:
                self.window_id, _, _, self.bounds = result
                return True
        elif MACOS:
            info = _mac_info(title_contains=self.title_contains, owner_name=self.owner_name)
            if info:
                self.window_info = info
                self.window_id = info['kCGWindowNumber']
                return True
        self.window_id = None
        print('⚠️ 未找到游戏窗口，请打开游戏后按 F11 重试。')
        return False

    def is_foreground(self):
        if not self.window_id:
            return False
        if WINDOWS:
            return windows_window.is_foreground(self.window_id)
        if MACOS:
            from AppKit import NSWorkspace
            active = NSWorkspace.sharedWorkspace().frontmostApplication()
            info = _mac_info(window_id=self.window_id)
            return bool(info and active and active.processIdentifier() == info.get('kCGWindowOwnerPID'))
        return False

    def require_foreground(self):
        if not self.is_foreground():
            raise WindowUnavailable('游戏不在前台或已最小化；已暂停，请切回游戏后按 F11。')

    def get_window_rect(self):
        if not self.enabled:
            return None
        if WINDOWS:
            rect = windows_window.client_rect(self.window_id) if self.window_id else None
        elif MACOS:
            info = _mac_info(window_id=self.window_id) if self.window_id else None
            bounds = info.get('kCGWindowBounds', {}) if info else {}
            rect = tuple(int(round(bounds[key])) for key in ('X', 'Y', 'Width', 'Height')) if bounds else None
        else:
            rect = None
        if rect and self.manual_offset is not None:
            return (int(self.manual_offset[0]), int(self.manual_offset[1]), rect[2], rect[3])
        return rect

    def screenshot(self):
        self.require_foreground()
        if not self.enabled:
            screenshot = pyautogui.screenshot()
            logical_size = tuple(pyautogui.size())
            img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            self.last_capture_rect = (0, 0, *logical_size)
            return cv2.resize(img, logical_size) if (img.shape[1], img.shape[0]) != logical_size else img
        rect = self.get_window_rect()
        if rect is None:
            raise WindowUnavailable('无法读取游戏窗口位置。')
        x, y, width, height = rect
        if WINDOWS:
            from PIL import ImageGrab
            img = cv2.cvtColor(np.array(ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)), cv2.COLOR_RGB2BGR)
        elif MACOS:
            image = Quartz.CGWindowListCreateImage(
                Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow,
                self.window_id, Quartz.kCGWindowImageBoundsIgnoreFraming)
            if image is None:
                raise WindowUnavailable('窗口截图失败，请检查系统设置中的屏幕录制权限。')
            pixel_width, pixel_height = Quartz.CGImageGetWidth(image), Quartz.CGImageGetHeight(image)
            stride = Quartz.CGImageGetBytesPerRow(image)
            data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image))
            pixels = np.frombuffer(data, dtype=np.uint8).reshape(pixel_height, stride // 4, 4)
            img = cv2.cvtColor(pixels[:, :pixel_width], cv2.COLOR_BGRA2BGR)
        else:
            raise WindowUnavailable('当前仅支持 Windows 和 macOS。')
        if (img.shape[1], img.shape[0]) != (width, height):
            img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
        self.last_capture_rect = rect
        return img

    def window_to_screen(self, x, y):
        rect = self.get_window_rect() if self.enabled else self.last_capture_rect
        if rect is None:
            raise WindowUnavailable('没有有效的窗口坐标。')
        if self.enabled and self.last_capture_rect and rect != self.last_capture_rect:
            raise WindowUnavailable('游戏窗口位置或大小发生变化，请按 F11 重新识别。')
        if not (0 <= x < rect[2] and 0 <= y < rect[3]):
            raise WindowUnavailable('识别位置超出游戏窗口。')
        return rect[0] + x, rect[1] + y

    def screen_to_window(self, screen_x, screen_y):
        rect = self.get_window_rect()
        if rect:
            x, y = screen_x - rect[0], screen_y - rect[1]
            if 0 <= x < rect[2] and 0 <= y < rect[3]:
                return x, y
        return None
