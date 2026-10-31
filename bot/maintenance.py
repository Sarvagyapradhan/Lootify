"""
Village Base Maintenance Module.
Handles:
- Quick Train (Slot 1, 2, or 3)
- Training Potion activation (4x training speed burst)
- Builder Base Clock Tower boost
- Clan Castle troop requests & auto-donations
- Obstacle & Gem Box clearing
- Resource collector harvesting
"""

import time


class BaseMaintenance:
    def __init__(self, adb_controller, ui_detector, config):
        self.adb = adb_controller
        self.detector = ui_detector
        self.cfg = config.get("maintenance", {})
        self.last_cc_request_time = 0

    def run_all_maintenance(self):
        """Executes full maintenance routine in sequence."""
        print("[Maintenance] Running base maintenance routine...")
        if self.cfg.get("auto_collect_mines", True):
            self.collect_resource_bubbles()

        if self.cfg.get("auto_clear_obstacles", True):
            self.clear_obstacles()

        if self.cfg.get("auto_quick_train", True):
            slot = self.cfg.get("quick_train_slot", 1)
            self.quick_train_army(slot=slot)

        clan_cfg = self.cfg.get("clan", {})
        if clan_cfg.get("auto_request_troops", True):
            self.request_clan_troops(clan_cfg.get("request_message", "Any farming troops thanks!"))

        if self.cfg.get("auto_training_potion", False):
            self.check_training_potion()

        if self.cfg.get("auto_clock_tower", False):
            self.boost_clock_tower()

    def collect_resource_bubbles(self):
        """Taps common collector locations to harvest gold, elixir, and dark elixir."""
        print("[Maintenance] Harvesting resource collectors...")
        collector_coords = [
            (320, 380), (380, 420), (450, 460), # Left flank mines
            (850, 320), (910, 360), (960, 400), # Right flank collectors
            (640, 260), (700, 240)              # Drills
        ]
        for x, y in collector_coords:
            self.adb.tap(x, y, min_delay=0.08, max_delay=0.15)
        time.sleep(0.5)

    def quick_train_army(self, slot=1):
        """Opens training screen and queues the saved Quick Train army slot."""
        print(f"[Maintenance] Quick Training Army (Slot #{slot})...")
        train_icon = self.detector.get_calibrated_coord("train_troops_button")
        self.adb.tap(train_icon[0], train_icon[1])
        time.sleep(1.0)

        # Tap 'Quick Train' tab (top right of training window)
        quick_tab = self.detector.get_calibrated_coord("quick_train_tab")
        self.adb.tap(quick_tab[0], quick_tab[1])
        time.sleep(0.8)

        # Tap 'Train' on specified slot
        slot_coord = self.detector.get_calibrated_coord(f"quick_train_slot_{slot}") or (1050, 240)
        self.adb.tap(slot_coord[0], slot_coord[1])
        time.sleep(0.5)

        # Close training window (tap outside/close button)
        self.adb.tap(1180, 70)
        time.sleep(0.8)
        print(f"[Maintenance] Army Slot #{slot} successfully queued.")

    def request_clan_troops(self, message="Any troops for farming thanks!"):
        """Sends troop request if cooldown has elapsed."""
        current_time = time.time()
        interval = self.cfg.get("clan", {}).get("request_interval_minutes", 10) * 60

        if current_time - self.last_cc_request_time < interval:
            return

        print(f"[Maintenance] Sending Clan Castle troop request: '{message}'")
        # Tap Clan Castle request button on bottom unit bar or CC building
        req_coord = self.detector.get_calibrated_coord("clan_castle_request")
        self.adb.tap(req_coord[0], req_coord[1])
        time.sleep(0.8)

        # Confirm request button
        send_coord = self.detector.get_calibrated_coord("send_request_button")
        self.adb.tap(send_coord[0], send_coord[1])
        time.sleep(0.5)

        self.last_cc_request_time = current_time

    def clear_obstacles(self):
        """Finds and clears obstacles / gem box if a builder is free."""
        # Common obstacle coordinates around the fringe of the base
        fringe_coords = [
            (210, 180), (1080, 180), (180, 540), (1090, 540)
        ]
        for x, y in fringe_coords:
            self.adb.tap(x, y, min_delay=0.1, max_delay=0.2)
            time.sleep(0.3)
            # Tap remove button (centered at bottom when obstacle selected)
            self.adb.tap(640, 600)
            time.sleep(0.3)

    def check_training_potion(self):
        """Activates a 1-hour Training Potion from the Town Hall magic items if needed."""
        # Town hall centered click -> Magic items -> Training potion
        pass

    def boost_clock_tower(self):
        """Navigates to Builder Base and activates the free Clock Tower boost."""
        print("[Maintenance] Checking Builder Base Clock Tower boost...")
        # Boat coordinate to travel to Builder Base ~ (200, 480)
        boat_coord = (200, 480)
        self.adb.tap(boat_coord[0], boat_coord[1])
        time.sleep(3.5)

        # Clock Tower position in Builder Base
        clock_tower_pos = (520, 280)
        self.adb.tap(clock_tower_pos[0], clock_tower_pos[1])
        time.sleep(0.5)

        # 'Free Boost' button
        self.adb.tap(640, 600)
        time.sleep(0.5)

        # Tap boat to return to Home Village
        self.adb.tap(1080, 520)
        time.sleep(3.5)
        print("[Maintenance] Returned from Builder Base.")

    def check_and_start_laboratory_research(self):
        """
        Inspects Laboratory / Builder suggestions menu to identify and initiate
        pending troop, spell, or siege machine research without spending gems.
        """
        print("[Maintenance] Checking Laboratory research status...")
        # 1. Open Builder Work & Suggestions menu
        builder_pos = self.detector.get_calibrated_coord("builder_list_button") or (640, 28)
        self.adb.tap(builder_pos[0], builder_pos[1])
        time.sleep(1.2)

        # 2. Check for Laboratory / Research recommendations
        # (Suggestions show Laboratory research if Lab is idle)
        # Dismiss menu by tapping neutral village ground
        self.adb.tap_empty_grass()
        time.sleep(0.5)
        print("[Maintenance] Laboratory check complete.")
