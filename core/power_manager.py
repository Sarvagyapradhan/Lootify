"""
Power Management & Scheduled Session Auto-Stop.
Provides scheduled session auto-stop timers (hours and minutes)
with configurable post-stop actions:
- JUST_STOP: Cleanly stop bot automation and remain on dashboard
- CLOSE_BOT_AND_EMULATOR: Stop bot, kill emulator processes, and close ClashBot
- SHUTDOWN_PC: Stop bot, close emulator, and initiate clean PC shutdown (with 60s cancellation window)
- SLEEP_PC: Stop bot, close emulator, and place PC into sleep/suspend state
"""

import os
import subprocess


class PowerManager:
    @staticmethod
    def kill_emulator_processes():
        """Terminates common emulator processes cleanly."""
        print("[PowerManager] Terminating emulator processes...")
        targets = [
            "MEmu.exe", "MEmuConsole.exe", "MEmuHeadless.exe",
            "HD-Player.exe", "dnplayer.exe", "Nox.exe"
        ]
        cmd = ["taskkill", "/f"]
        for t in targets:
            cmd.extend(["/im", t])
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[PowerManager] Emulator processes terminated.")
        except Exception as e:
            print(f"[PowerManager] Notice terminating emulator: {e}")

    @staticmethod
    def shutdown_pc(warning_seconds=60):
        """Initiates a clean Windows shutdown with warning message and cancel option."""
        print(f"[PowerManager] [SHUTDOWN] Initiating Windows system shutdown in {warning_seconds}s...")
        msg = f"ClashBot scheduled farming completed. Shutting down PC in {warning_seconds} seconds. Run 'shutdown /a' in CMD to cancel."
        cmd = f'shutdown /s /t {warning_seconds} /c "{msg}"'
        try:
            os.system(cmd)
            print("[PowerManager] Windows shutdown command scheduled.")
        except Exception as e:
            print(f"[PowerManager] Shutdown error: {e}")

    @staticmethod
    def sleep_pc():
        """Puts Windows PC into Sleep / Suspend mode."""
        print("[PowerManager] [SLEEP] Putting Windows PC into sleep mode...")
        try:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        except Exception as e:
            print(f"[PowerManager] Sleep error: {e}")
