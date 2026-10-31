"""
ADB Controller with Biometric Anti-Detection Simulation.
Uses Ex-Gaussian latency distributions, bivariate Gaussian spatial dispersion,
and micro-drag touch durations to mirror genuine physical touchscreen interaction.
"""

import os
import time
import random
import subprocess
import threading
from ppadb.client import Client as AdbClient
from core.humanizer import Humanizer


class ADBController:
    def __init__(self, host="127.0.0.1", port=5555, custom_adb_path=None, jitter_radius=5):
        self.host = host
        self.port = port
        self.custom_adb_path = custom_adb_path
        self.jitter_radius = jitter_radius
        self.device = None
        self.client = None
        self._adb_lock = threading.RLock()
        self._tap_history = []
        self._tap_history_lock = threading.Lock()
        self.humanizer = Humanizer()
        self.is_bot_tapping = False
        self.device_width = 1280
        self.device_height = 720
        self.scale_x = 1.0
        self.scale_y = 1.0
        self._initialize_connection()

    def record_tap_event(self, x, y, label=""):
        """Records a tap event for live HUD overlay visualization."""
        now = time.time()
        with self._tap_history_lock:
            self._tap_history.append({
                "type": "tap",
                "x": int(round(x)),
                "y": int(round(y)),
                "time": now,
                "label": label or f"({int(round(x))}, {int(round(y))})"
            })
            cutoff = now - 4.0
            self._tap_history = [t for t in self._tap_history if t["time"] >= cutoff]

    def record_swipe_event(self, x1, y1, x2, y2, label=""):
        """Records a swipe event for live HUD overlay visualization."""
        now = time.time()
        with self._tap_history_lock:
            self._tap_history.append({
                "type": "swipe",
                "x1": int(round(x1)),
                "y1": int(round(y1)),
                "x2": int(round(x2)),
                "y2": int(round(y2)),
                "time": now,
                "label": label or f"Swipe ({int(round(x1))},{int(round(y1))})->({int(round(x2))},{int(round(y2))})"
            })
            cutoff = now - 4.0
            self._tap_history = [t for t in self._tap_history if t["time"] >= cutoff]

    def get_recent_touch_events(self):
        """Returns a snapshot of recent taps/swipes within the last 3.5 seconds."""
        now = time.time()
        with self._tap_history_lock:
            cutoff = now - 3.5
            return [dict(t) for t in self._tap_history if t["time"] >= cutoff]

    def enable_touch_visualizer(self, enable=True):
        """
        Enables Android system touch indicators so every tap renders a visual circle
        on the emulator screen natively, in addition to our GUI viewfinder overlay.
        """
        with self._adb_lock:
            if self.device:
                try:
                    val = "1" if enable else "0"
                    self.device.shell(f"settings put system show_touches {val}")
                except Exception:
                    pass

    def screencap(self):
        """
        Thread-safe screencap executed strictly under ADB controller lock,
        preventing concurrent socket corruption between taps and framebuffer reads.
        """
        with self._adb_lock:
            if not self.device:
                self.ensure_connected()
            if self.device:
                try:
                    return self.device.screencap()
                except Exception:
                    self.device = None
                    self.ensure_connected()
                    if self.device:
                        return self.device.screencap()
        return None

    def _detect_screen_resolution(self):
        """Auto-detects the connected device's physical resolution and sets dynamic scaling."""
        if not self.device:
            return
        try:
            out = self.device.shell("wm size")
            import re
            m = re.findall(r"(\d+)x(\d+)", out)
            if m:
                w, h = int(m[-1][0]), int(m[-1][1])
                if h > w:
                    w, h = h, w
                self.device_width = w
                self.device_height = h
                self.scale_x = w / 1280.0
                self.scale_y = h / 720.0
                if abs(self.scale_x - 1.0) > 0.01 or abs(self.scale_y - 1.0) > 0.01:
                    print(f"[ADB] Universal Device Scaling Active: Native {w}x{h} (Scale X={self.scale_x:.3f}, Y={self.scale_y:.3f})")
        except Exception:
            self.device_width, self.device_height = 1280, 720
            self.scale_x, self.scale_y = 1.0, 1.0

    def to_device_coords(self, x, y):
        """Converts normalized 1280x720 coordinates to the device's physical touchscreen resolution."""
        sx = getattr(self, "scale_x", 1.0)
        sy = getattr(self, "scale_y", 1.0)
        if abs(sx - 1.0) < 0.001 and abs(sy - 1.0) < 0.001:
            return int(round(x)), int(round(y))
        return int(round(x * sx)), int(round(y * sy))

    def ensure_connected(self):
        """Attempts to reconnect to ADB if connection is lost or device is not attached."""
        with self._adb_lock:
            if self.device:
                try:
                    self.device.shell("echo 1")
                    return True
                except Exception:
                    self.device = None

            try:
                if self.custom_adb_path and os.path.exists(self.custom_adb_path):
                    subprocess.run([self.custom_adb_path, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run([self.custom_adb_path, "connect", f"{self.host}:{self.port}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                self.client = AdbClient(host=self.host, port=5037)
                devices = self.client.devices()

                if not devices:
                    candidate_ports = [self.port, 21503, 5555, 21513, 5554, 16384]
                    seen = set()
                    for p in candidate_ports:
                        endpoint = f"{self.host}:{p}"
                        if endpoint in seen:
                            continue
                        seen.add(endpoint)
                        try:
                            self.client.remote_connect(self.host, p)
                        except Exception:
                            pass
                    devices = self.client.devices()

                if devices:
                    self.device = devices[0]
                    print(f"[ADB] Connected to device: {self.device.serial}")
                    self._detect_screen_resolution()
                    self.enable_touch_visualizer(True)
                    return True
            except Exception:
                pass
            return False

    def _initialize_connection(self):
        """Connects to ADB server and finds the emulator device."""
        if not self.ensure_connected():
            print(f"[ADB] Warning: No active ADB devices detected on {self.host}:{self.port}.")

    def tap(self, x, y, custom_delay=None, min_delay=None, max_delay=None):
        """
        Executes a biometrically natural tap:
        - Dynamic scaling from 1280x720 baseline to native device resolution
        - Bivariate Gaussian coordinate dispersion (thumb contact simulation)
        - Realistic touch-down duration (50ms - 90ms with micro-drift)
        - Ex-Gaussian reaction delay or bounded custom/min-max delay
        """
        self.is_bot_tapping = True
        try:
            with self._adb_lock:
                if not self.device:
                    self.ensure_connected()

                dev_x, dev_y = self.to_device_coords(x, y)
                target_x, target_y = self.humanizer.get_dispersed_coordinate(dev_x, dev_y, radius_x=self.jitter_radius, radius_y=self.jitter_radius)
                touch_duration = self.humanizer.get_touch_down_duration_ms()

                # Slight 1-pixel micro-drift simulating skin squish/drag during tap
                end_x = target_x + random.choice([-1, 0, 1])
                end_y = target_y + random.choice([-1, 0, 1])

                cmd = f"input swipe {target_x} {target_y} {end_x} {end_y} {touch_duration}"

                if self.device:
                    try:
                        self.device.shell(cmd)
                        self.record_tap_event(x, y)
                    except Exception:
                        self.device = None
                        self.ensure_connected()
                        if self.device:
                            self.device.shell(cmd)
                            self.record_tap_event(x, y)
                elif self.custom_adb_path and os.path.exists(self.custom_adb_path):
                    subprocess.run([self.custom_adb_path, "shell"] + cmd.split(),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.record_tap_event(x, y)
        finally:
            self.is_bot_tapping = False

        # Apply delay logic
        if min_delay is not None and max_delay is not None:
            delay = random.uniform(min_delay, max_delay)
        elif custom_delay is not None:
            delay = custom_delay
        else:
            delay = self.humanizer.get_reaction_delay()
        time.sleep(delay)
        return (target_x, target_y)

    def tap_empty_grass(self, frame=None):
        """
        Taps safely on neutral empty grass/forest to deselect any open building menus.
        Applies natural humanized spatial dispersion around the outer perimeter forest
        at (90 ± 18, 260 ± 18) well outside the village grid.
        """
        target_x = 90 + random.randint(-18, 18)
        target_y = 260 + random.randint(-18, 18)
        return self.tap(target_x, target_y, min_delay=0.06, max_delay=0.12)

    def swipe(self, x1, y1, x2, y2, duration_ms=None):
        """Performs a curved swipe gesture simulating natural human finger dragging."""
        self.is_bot_tapping = True
        try:
            if not self.device:
                self.ensure_connected()

            if duration_ms is None:
                duration_ms = random.randint(310, 490)

            dev_x1, dev_y1 = self.to_device_coords(x1, y1)
            dev_x2, dev_y2 = self.to_device_coords(x2, y2)
            t_x1, t_y1 = self.humanizer.get_dispersed_coordinate(dev_x1, dev_y1, radius_x=self.jitter_radius)
            t_x2, t_y2 = self.humanizer.get_dispersed_coordinate(dev_x2, dev_y2, radius_x=self.jitter_radius)

            cmd = f"input swipe {t_x1} {t_y1} {t_x2} {t_y2} {duration_ms}"
            if self.device:
                try:
                    self.device.shell(cmd)
                    self.record_swipe_event(x1, y1, x2, y2)
                except Exception:
                    self.device = None
                    self.ensure_connected()
                    if self.device:
                        self.device.shell(cmd)
                        self.record_swipe_event(x1, y1, x2, y2)
            elif self.custom_adb_path and os.path.exists(self.custom_adb_path):
                subprocess.run([self.custom_adb_path, "shell"] + cmd.split(),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.record_swipe_event(x1, y1, x2, y2)
        finally:
            self.is_bot_tapping = False

        time.sleep(duration_ms / 1000.0 + self.humanizer.get_reaction_delay())

    def multi_tap(self, points, delay_after=0.04):
        """
        Executes fast multi-finger deployment taps at multiple coordinates (2-4 fingers)
        dispatched simultaneously via background subshell processes.
        """
        if not points:
            return
        self.is_bot_tapping = True
        try:
            with self._adb_lock:
                if not self.device:
                    self.ensure_connected()

                cmds = []
                for pt in points:
                    dev_x, dev_y = self.to_device_coords(pt[0], pt[1])
                    tx, ty = self.humanizer.get_dispersed_coordinate(dev_x, dev_y, radius_x=self.jitter_radius, radius_y=self.jitter_radius)
                    cmds.append(f"input tap {tx} {ty}")

                full_cmd = " & ".join(cmds)
                if self.device:
                    try:
                        self.device.shell(full_cmd)
                        for pt in points:
                            self.record_tap_event(pt[0], pt[1])
                    except Exception:
                        self.device = None
                        self.ensure_connected()
                        if self.device:
                            self.device.shell(full_cmd)
                            for pt in points:
                                self.record_tap_event(pt[0], pt[1])
                elif self.custom_adb_path and os.path.exists(self.custom_adb_path):
                    subprocess.run([self.custom_adb_path, "shell", full_cmd],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    for pt in points:
                        self.record_tap_event(pt[0], pt[1])
        finally:
            self.is_bot_tapping = False

        if delay_after > 0:
            time.sleep(delay_after)

    def swipe_deploy(self, start_pt, end_pt, duration_ms=250):
        """
        Deploys a continuous line of troops along the perimeter boundary
        via a smooth, fast touch swipe.
        """
        if not self.device:
            self.ensure_connected()
        sx, sy = self.to_device_coords(start_pt[0], start_pt[1])
        ex, ey = self.to_device_coords(end_pt[0], end_pt[1])
        cmd = f"input swipe {sx} {sy} {ex} {ey} {duration_ms}"
        if self.device:
            try:
                self.device.shell(cmd)
            except Exception:
                pass
        time.sleep(duration_ms / 1000.0 + 0.05)

    def launch_game(self, package_name="com.supercell.clashofclans"):
        """Launches Clash of Clans directly."""
        if not self.device:
            self.ensure_connected()

        cmd = f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        if self.device:
            self.device.shell(cmd)
            print(f"[ADB] Sent launch command for {package_name}")
        elif self.custom_adb_path and os.path.exists(self.custom_adb_path):
            subprocess.run([self.custom_adb_path, "shell"] + cmd.split(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[ADB] Sent launch command for {package_name} via adb CLI")

    def send_keyevent(self, keycode):
        """Sends an Android keyevent (e.g. keycode 4 for Back/Escape)."""
        if not self.device:
            self.ensure_connected()

        cmd = f"input keyevent {keycode}"
        if self.device:
            try:
                self.device.shell(cmd)
            except Exception:
                self.device = None
                self.ensure_connected()
                if self.device:
                    self.device.shell(cmd)
        elif self.custom_adb_path and os.path.exists(self.custom_adb_path):
            subprocess.run([self.custom_adb_path, "shell"] + cmd.split(),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.3)

    def pinch_zoom_out(self, times=2):
        """
        Executes camera zoom-out using MEmu's native 'memuc zoomout' command,
        providing smooth, instantaneous full-perimeter battlefield view with zero screen dragging.
        """
        # 1. Attempt native MEmu zoomout via memuc.exe
        memuc_path = None
        if self.custom_adb_path and os.path.exists(self.custom_adb_path):
            candidate = os.path.join(os.path.dirname(self.custom_adb_path), "memuc.exe")
            if os.path.exists(candidate):
                memuc_path = candidate
        if not memuc_path:
            standard_memu = r"D:\Program Files\Microvirt\MEmu\memuc.exe"
            if os.path.exists(standard_memu):
                memuc_path = standard_memu

        if memuc_path:
            # Map port 21503 -> VM index 0, 21513 -> VM index 1, etc.
            vm_index = max(0, (self.port - 21503) // 10) if self.port >= 21503 else 0
            memuc_success = False
            for i in range(times):
                try:
                    res = subprocess.run([memuc_path, "zoomout", "-i", str(vm_index)],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6.0)
                    if res.returncode == 0:
                        memuc_success = True
                    time.sleep(0.18)
                except Exception as e:
                    print(f"[ADB] memuc zoomout notice: {e}")
            if memuc_success:
                print(f"[ADB] Battle camera zoom-out executed via MEmu native command (VM index {vm_index}, {times}x).")
                return

        # 2. Fallback: Multi-touch zoom out via Android keyevents (Ctrl + Minus / Keycode 169)
        print("[ADB] Executing multi-touch zoom out fallback...")
        if self.device:
            try:
                # Keycode 169 is KEYCODE_ZOOM_OUT, Keycode 69 is KEYCODE_MINUS with Ctrl (meta 113)
                self.device.shell("input keyevent 169")
                time.sleep(0.1)
                self.device.shell("input keyevent --meta 113 69")
            except Exception:
                pass
        time.sleep(0.3)
