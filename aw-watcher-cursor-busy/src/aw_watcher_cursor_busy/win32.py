from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

from aw_watcher_cursor_busy.core import BusySample

IDC_WAIT = 32514
IDC_APPSTARTING = 32650
CURSOR_SHOWING = 0x00000001
GA_ROOT = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", POINT),
    ]


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = wintypes.BOOL
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.WindowFromPoint.argtypes = [POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def _make_int_resource(resource_id: int) -> wintypes.LPCWSTR:
    return ctypes.cast(resource_id, wintypes.LPCWSTR)


def _load_standard_cursor(resource_id: int) -> int:
    return int(user32.LoadCursorW(None, _make_int_resource(resource_id)) or 0)


STANDARD_BUSY_CURSORS = {
    _load_standard_cursor(IDC_WAIT): "wait",
    _load_standard_cursor(IDC_APPSTARTING): "appstarting",
}


def get_current_cursor_name() -> str | None:
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not (info.flags & CURSOR_SHOWING):
        return None
    return STANDARD_BUSY_CURSORS.get(int(info.hCursor or 0))


def get_window_under_cursor() -> wintypes.HWND:
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    hwnd = user32.WindowFromPoint(info.ptScreenPos)
    root = user32.GetAncestor(hwnd, GA_ROOT) if hwnd else None
    return root or hwnd


def get_window_title(hwnd: wintypes.HWND) -> str:
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def get_window_pid(hwnd: wintypes.HWND) -> int | None:
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value) or None


def get_process_image_path(pid: int | None) -> str | None:
    if not pid:
        return None
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def get_busy_sample() -> BusySample | None:
    cursor = get_current_cursor_name()
    if cursor is None:
        return None

    hwnd = get_window_under_cursor()
    pid = get_window_pid(hwnd)
    image_path = get_process_image_path(pid)
    app = Path(image_path).name if image_path else "unknown"
    return BusySample(
        cursor=cursor,
        app=app,
        title=get_window_title(hwnd),
        pid=pid,
    )

