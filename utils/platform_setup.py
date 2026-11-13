"""在导入界面和鼠标库前初始化 Windows DPI 坐标系统。"""

import sys


def setup_dpi_awareness():
    """打包程序使用 manifest；源码运行时尽早设置 Per Monitor V2。"""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        function = user32.SetProcessDpiAwarenessContext
        function.argtypes = [ctypes.c_void_p]
        function.restype = ctypes.c_int
        if function(ctypes.c_void_p(-4)) or ctypes.get_last_error() == 5:
            return  # manifest 已设置时返回 ACCESS_DENIED，无需覆盖。
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
