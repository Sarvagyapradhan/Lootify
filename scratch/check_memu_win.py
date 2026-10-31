import win32gui
import re

def callback(hwnd, extra):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if re.search(r"MEmu|Clash", title, re.IGNORECASE):
            print(f"HWND: {hwnd}, Title: '{title}'")
            print(f"  WindowRect: {win32gui.GetWindowRect(hwnd)}")
            print(f"  ClientRect: {win32gui.GetClientRect(hwnd)}")
            client_screen = win32gui.ClientToScreen(hwnd, (0, 0))
            print(f"  ClientToScreen: {client_screen}")

win32gui.EnumWindows(callback, None)

