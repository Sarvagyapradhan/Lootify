"""
High-Precision Screen Capture Engine.
Supports direct ADB frame buffer capture (guarantees pixel-perfect 1280x720 without window borders)
with fallback to fast Windows desktop/window grabber.
"""

import time
import threading
import numpy as np
import mss
import cv2

try:
    import win32gui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class ScreenCapture:
    def __init__(self, target_title_pattern="MEmu|LDPlayer|BlueStacks", adb_controller=None, default_res=(1280, 720)):
        self.title_pattern = target_title_pattern
        self.adb = adb_controller
        self.default_res = default_res
        self.sct = mss.mss()
        self.hwnd = None
        self.window_rect = None
        self._lock = threading.Lock()
        self._last_frame = None
        self._last_frame_time = 0
        self._consecutive_adb_fails = 0
        self._find_window()

    def set_adb_controller(self, adb_controller):
        self.adb = adb_controller

    def _find_window(self):
        if not HAS_WIN32:
            return

        def enum_windows_callback(hwnd, extra):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    import re
                    if re.search(self.title_pattern, title, re.IGNORECASE):
                        self.hwnd = hwnd
            except Exception:
                pass
            return True  # Must return True to prevent pywin32 from raising error 5

        try:
            win32gui.EnumWindows(enum_windows_callback, None)
            if not self.hwnd:
                for t in ["MEmu", "Clash of Clans", "LDPlayer", "BlueStacks"]:
                    h = win32gui.FindWindow(None, t)
                    if h:
                        self.hwnd = h
                        break
            if self.hwnd:
                rect = win32gui.GetWindowRect(self.hwnd)
                self.window_rect = {
                    "left": rect[0],
                    "top": rect[1],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1]
                }
                print(f"[ScreenCapture] Attached to emulator window (HWND: {self.hwnd}, Rect: {self.window_rect})")
        except Exception:
            pass

    def get_frame(self, target_size=(1280, 720), max_age=0.06):
        """
        Grabs frame from ADB device (pure 1280x720 Android frame) or desktop window.
        Thread-safe and cached for 60ms to eliminate redundant ADB queries and GDI handle exhaustion.
        """
        now = time.time()
        with self._lock:
            # 0. Fast-path: return cached frame if fresh enough (protects against concurrent thread spam)
            if self._last_frame is not None and (now - self._last_frame_time) < max_age:
                return self._last_frame

            # 1. Primary: Direct ADB internal framebuffer (100% clean, no desktop occlusion)
            if self.adb:
                try:
                    raw_bytes = self.adb.screencap() if hasattr(self.adb, "screencap") else (self.adb.device.screencap() if self.adb.device else None)
                    if raw_bytes and len(raw_bytes) > 1000:
                        img = cv2.imdecode(np.frombuffer(raw_bytes, np.uint8), cv2.IMREAD_COLOR)
                        if img is not None:
                            if target_size and (img.shape[1] != target_size[0] or img.shape[0] != target_size[1]):
                                img = cv2.resize(img, target_size, interpolation=cv2.INTER_LINEAR)
                            self._last_frame = img
                            self._last_frame_time = now
                            self._consecutive_adb_fails = 0
                            return img
                except Exception:
                    self._consecutive_adb_fails += 1
                    if self._last_frame is not None and (now - self._last_frame_time) < 2.0:
                        return self._last_frame

            # Prefer cached frame over Windows GDI grab if within 2 seconds
            if self._last_frame is not None and (now - self._last_frame_time) < 2.0:
                return self._last_frame

            # 2. Secondary: Direct window capture if HWND was identified
            if not self.hwnd and HAS_WIN32:
                self._find_window()

            if self.hwnd and HAS_WIN32:
                try:
                    # Capture exact Client rendering area (excludes Windows title bar and outer window borders)
                    client_rect = win32gui.GetClientRect(self.hwnd)
                    left_top = win32gui.ClientToScreen(self.hwnd, (0, 0))
                    w = client_rect[2] - client_rect[0]
                    h = client_rect[3] - client_rect[1]
                    if w > 100 and h > 100:
                        # Emulators (MEmu/LDPlayer) often have a right-docked utility toolbar (~40-45px wide)
                        # When maximized or resized, pure 16:9 game area has aspect ratio = 1.778.
                        # Trim any docked right-side toolbar to preserve exact 16:9 game coordinates:
                        aspect = w / float(h)
                        actual_w = w
                        if aspect > 1.80:
                            actual_w = int(h * 16.0 / 9.0)

                        monitor = {"top": left_top[1], "left": left_top[0], "width": actual_w, "height": h}
                        raw = np.array(self.sct.grab(monitor))
                        bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                        if target_size and (bgr.shape[1] != target_size[0] or bgr.shape[0] != target_size[1]):
                            bgr = cv2.resize(bgr, target_size, interpolation=cv2.INTER_LINEAR)
                        self._last_frame = bgr
                        self._last_frame_time = now
                        return bgr
                except Exception:
                    try:
                        self.sct.close()
                        self.sct = mss.mss()
                    except Exception:
                        pass

            # 3. Fallback: return last cached frame or primary monitor
            if self._last_frame is not None:
                return self._last_frame

            try:
                monitor = self.sct.monitors[1]
                raw = np.array(self.sct.grab(monitor))
                bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                if target_size:
                    bgr = cv2.resize(bgr, target_size, interpolation=cv2.INTER_LINEAR)
                self._last_frame = bgr
                self._last_frame_time = now
                return bgr
            except Exception:
                return None

    def save_debug_screenshot(self, filename="test_screen_capture.png"):
        frame = self.get_frame()
        cv2.imwrite(filename, frame)
        print(f"[ScreenCapture] Saved debug frame to {filename}")
        return filename
