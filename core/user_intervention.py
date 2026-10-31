"""
User Manual Intervention Monitor.
Detects when the user manually clicks or touches the emulator window during bot automation.
Automatically pauses bot execution to let the user play freely without input conflicts,
and safely resumes automation after the user stops, dynamically identifying the current
screen and returning to the appropriate state.
"""

import os
import time
import threading
import ctypes


class UserInterventionMonitor:
    def __init__(self, adb_controller=None, screen_capture=None, idle_resume_seconds=0.8, enabled=False):
        self.adb = adb_controller
        self.capture = screen_capture
        self.idle_resume_seconds = idle_resume_seconds
        self.enabled = enabled
        self.is_human_active = False
        self.last_touch_time = 0.0
        self.on_intervention_start = None
        self.on_intervention_end = None
        self._running = False
        self._monitor_thread = None
        self._user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

    def start(self):
        if not self.enabled or self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop(self):
        self._running = False

    def report_human_touch(self):
        """Called whenever a physical user touch or click is observed on the emulator canvas."""
        now = time.time()
        self.last_touch_time = now
        if not self.is_human_active:
            self.is_human_active = True
            print("[UserIntervention] Manual user interaction detected on emulator! Pausing bot automation...")
            if self.on_intervention_start:
                try:
                    self.on_intervention_start()
                except Exception:
                    pass

    def check_is_idle(self):
        """Returns True if user was active and has now been idle for idle_resume_seconds (2.0s)."""
        if not self.is_human_active:
            return False
        if time.time() - self.last_touch_time >= self.idle_resume_seconds:
            return True
        return False

    def clear_intervention(self):
        self.is_human_active = False

    def _monitor_loop(self):
        """Monitors physical clicks strictly targeted at the emulator window."""
        my_pid = os.getpid()
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        while self._running:
            try:
                time.sleep(0.06)
                if not self.enabled:
                    continue

                # If bot is currently executing an automated tap, ignore
                if self.adb and getattr(self.adb, "is_bot_tapping", False):
                    continue

                if self._user32:
                    l_down = bool(self._user32.GetAsyncKeyState(0x01) & 0x8000)
                    r_down = bool(self._user32.GetAsyncKeyState(0x02) & 0x8000)
                    if l_down or r_down:
                        pt = POINT()
                        self._user32.GetCursorPos(ctypes.byref(pt))

                        # Topmost window under mouse cursor
                        wnd_at_pt = self._user32.WindowFromPoint(pt)
                        if not wnd_at_pt:
                            continue

                        # Check window process ID: NEVER trigger on ClashBot's own GUI
                        pt_pid = ctypes.c_ulong()
                        self._user32.GetWindowThreadProcessId(wnd_at_pt, ctypes.byref(pt_pid))
                        if pt_pid.value == my_pid:
                            continue

                        root_wnd = self._user32.GetAncestor(wnd_at_pt, 2) if hasattr(self._user32, "GetAncestor") else wnd_at_pt

                        is_emulator_click = False

                        # 1. Verification via attached emulator window handle
                        if self.capture and self.capture.hwnd:
                            emu_pid = ctypes.c_ulong()
                            self._user32.GetWindowThreadProcessId(self.capture.hwnd, ctypes.byref(emu_pid))
                            
                            # If cursor is over a completely different process (Chrome, Explorer, Taskbar, etc.), ignore
                            if emu_pid.value > 0 and pt_pid.value != emu_pid.value:
                                continue

                            # Verify cursor position is strictly inside emulator window boundaries
                            rect = RECT()
                            self._user32.GetWindowRect(self.capture.hwnd, ctypes.byref(rect))
                            if not (rect.left <= pt.x <= rect.right and rect.top <= pt.y <= rect.bottom):
                                continue

                            if wnd_at_pt == self.capture.hwnd or root_wnd == self.capture.hwnd or pt_pid.value == emu_pid.value:
                                is_emulator_click = True

                        # 2. Window title check if HWND was not already matched
                        if not is_emulator_click:
                            for w in [wnd_at_pt, root_wnd]:
                                if w:
                                    length = self._user32.GetWindowTextLengthW(w)
                                    if length > 0:
                                        buff = ctypes.create_unicode_buffer(length + 1)
                                        self._user32.GetWindowTextW(w, buff, length + 1)
                                        title = buff.value.lower()
                                        # Strict exclusion: NEVER match ClashBot GUI, browsers, code editors, or taskbar
                                        if any(bad in title for bad in ["clashbot", "suite", "python", "code", "ide", "terminal", "powershell", "chrome", "edge", "firefox", "discord", "spotify", "explorer"]):
                                            continue
                                        if any(k in title for k in ["memu", "clash of clans", "android", "ldplayer", "nox", "bluestacks"]):
                                            is_emulator_click = True
                                            if self.capture and not self.capture.hwnd:
                                                self.capture.hwnd = w
                                            break

                        if is_emulator_click:
                            self.report_human_touch()
                            continue

            except Exception:
                pass
