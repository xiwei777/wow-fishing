"""Windows 窗口查找与客户区坐标；仅在 Windows 平台导入。"""

import ctypes
from ctypes import wintypes
from pathlib import PureWindowsPath

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _signature(library, name, arguments, result):
    function = getattr(library, name)
    function.argtypes = arguments
    function.restype = result
    return function


_signature(user32, 'EnumWindows', [CALLBACK, wintypes.LPARAM], wintypes.BOOL)
_signature(user32, 'IsWindow', [wintypes.HWND], wintypes.BOOL)
_signature(user32, 'IsWindowVisible', [wintypes.HWND], wintypes.BOOL)
_signature(user32, 'IsIconic', [wintypes.HWND], wintypes.BOOL)
_signature(user32, 'GetForegroundWindow', [], wintypes.HWND)
_signature(user32, 'GetWindowTextLengthW', [wintypes.HWND], ctypes.c_int)
_signature(user32, 'GetWindowTextW', [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int)
_signature(user32, 'GetClientRect', [wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL)
_signature(user32, 'ClientToScreen', [wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL)
_signature(user32, 'GetWindowThreadProcessId', [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD)
_signature(kernel32, 'OpenProcess', [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)
_signature(kernel32, 'QueryFullProcessImageNameW', [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL)
_signature(kernel32, 'CloseHandle', [wintypes.HANDLE], wintypes.BOOL)


def client_rect(hwnd):
    """返回虚拟桌面物理像素中的客户区 (x, y, width, height)。"""
    if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd):
        return None
    rect, origin = wintypes.RECT(), wintypes.POINT(0, 0)
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    return (origin.x, origin.y, width, height) if width > 0 and height > 0 else None


def _owner(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = kernel32.OpenProcess(0x1000, False, pid.value)
    if not process:
        return ''
    try:
        length = wintypes.DWORD(32768)
        name = ctypes.create_unicode_buffer(length.value)
        if kernel32.QueryFullProcessImageNameW(process, 0, name, ctypes.byref(length)):
            return PureWindowsPath(name.value).stem
        return ''
    finally:
        kernel32.CloseHandle(process)


def find_window(title_contains, owner_name):
    """按进程名或标题选择游戏窗口，优先前台窗口。"""
    matches = []
    @CALLBACK
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        rect = client_rect(hwnd)
        if not rect:
            return True
        title = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
        user32.GetWindowTextW(hwnd, title, len(title))
        owner = _owner(hwnd)
        owner_match = owner_name and owner.casefold() == PureWindowsPath(owner_name).stem.casefold()
        title_match = title_contains and title_contains.casefold() in title.value.casefold()
        if owner_match or title_match:
            matches.append((hwnd, owner, title.value, rect))
        return True
    user32.EnumWindows(visit, 0)
    foreground = user32.GetForegroundWindow()
    matches.sort(key=lambda item: (item[0] != foreground, -(item[3][2] * item[3][3])))
    return matches[0] if matches else None


def is_foreground(hwnd):
    return bool(user32.IsWindow(hwnd) and not user32.IsIconic(hwnd) and user32.GetForegroundWindow() == hwnd)
