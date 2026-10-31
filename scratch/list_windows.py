import win32gui

def callback(hwnd, extra):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title.strip():
            print(f"{hwnd}: '{title}'")

win32gui.EnumWindows(callback, None)

