"""
Wall Dumping & Resource Sink Module via Builder Work Menu.
Selects unupgraded walls dynamically from the Build / Builder Recommendations Menu,
activates batch mode (+10, +1, -1), dynamically budgets walls based on available Gold and Elixir,
and confirms upgrades with 100% affordability (0 GEMS SPENT).
"""

import time
import numpy as np
from core.screen_capture import ScreenCapture
from vision.ocr_reader import LootOCRReader


class WallUpgrader:
    def __init__(self, adb_controller, ui_detector, config, screen_capture=None, ocr_reader=None):
        self.adb = adb_controller
        self.detector = ui_detector
        self.capture = screen_capture or ScreenCapture(adb_controller=adb_controller)
        self.ocr = ocr_reader or LootOCRReader()
        self.global_config = config or {}
        self.cfg = config.get("wall_dump", {})
        self.enabled = self.cfg.get("enabled", True)
        self.trigger_percentage = self.cfg.get("storage_full_percentage", 85)
        # Enforce user requirement: At least 2,000 Gold MUST remain in storage after wall upgrade
        self.gold_reserve = max(2000, self.cfg.get("keep_gold_reserve", 2000))
        self.elixir_reserve = self.cfg.get("keep_elixir_reserve", 200000)
        self.max_walls_per_cycle = self.cfg.get("max_walls_per_cycle", 50)
        self.priority = self.cfg.get("upgrade_resource_priority", "BOTH").upper()
        self.strategy = config.get("village_profile", {}).get("wall_strategy") or self.cfg.get("wall_strategy", "CHEAPEST_FIRST")
        self.fsm = None
        self.abort_requested = False

    def check_should_abort(self):
        """Checks if stop or pause has been requested by the user."""
        if self.abort_requested:
            return True
        if hasattr(self, "fsm") and self.fsm:
            if not self.fsm.is_running:
                return True
            while self.fsm.is_paused and self.fsm.is_running:
                time.sleep(0.1)
            return not self.fsm.is_running
        return False

    def set_screen_capture(self, screen_capture):
        self.capture = screen_capture

    def check_and_dump_resources(self, storages_dict=None, current_storage_percent=None, force=False):
        """
        Main entrypoint: evaluates storages and executes wall dumping via Builder Menu.
        Only triggers when storages are full or close to full (>= storage_full_percentage),
        and respects min reserve and max spend configuration.
        """
        if not self.enabled:
            return False
        if hasattr(self, "fsm") and self.fsm and self.fsm.is_running and not self.fsm.is_paused:
            self.abort_requested = False
        if self.check_should_abort():
            return False

        should_dump = False
        avail_gold = 0
        avail_elixir = 0

        s_cfg = self.global_config.get("storages", {})
        max_g = s_cfg.get("max_gold_capacity", 5004500)
        max_e = s_cfg.get("max_elixir_capacity", 5004500)
        trigger_pct = self.cfg.get("storage_full_percentage", 85) / 100.0
        max_spend_pct = self.cfg.get("max_dump_spend_percent", 100) / 100.0

        if not storages_dict:
            frame_now = self.capture.get_frame(target_size=(1280, 720))
            if hasattr(self, "ocr") and self.ocr:
                storages_dict = self.ocr.read_village_storages(frame_now)

        if storages_dict:
            gold = storages_dict.get("gold", 0)
            elixir = storages_dict.get("elixir", 0)

            raw_avail_gold = max(0, gold - self.gold_reserve)
            raw_avail_elixir = max(0, elixir - self.elixir_reserve)
            avail_gold = int(raw_avail_gold * max_spend_pct)
            avail_elixir = int(raw_avail_elixir * max_spend_pct)

            if force:
                if avail_gold >= 30000 or avail_elixir >= 30000:
                    should_dump = True
                    print(f"[WallUpgrader] Continuous dump cycle active (Spendable: G={avail_gold:,}, E={avail_elixir:,}). Continuing...")
                else:
                    print(f"[WallUpgrader] Spendable resources depleted down to reserve (G={avail_gold:,}, E={avail_elixir:,}). Dump session completed.")
                    return False
            else:
                is_full = (
                    storages_dict.get("gold_full")
                    or storages_dict.get("elixir_full")
                    or (gold >= int(max_g * trigger_pct))
                    or (elixir >= int(max_e * trigger_pct))
                )

                if is_full:
                    if avail_gold >= 30000 or avail_elixir >= 30000:
                        should_dump = True
                        print(f"[WallUpgrader] Storage capacity full/near-full trigger reached (Gold: {gold:,}, Elixir: {elixir:,}, Spendable: G={avail_gold:,}, E={avail_elixir:,}). Dump triggered.")
                    else:
                        print("[WallUpgrader] Storages full but spendable resources after reserve are below 30,000. Skipping dump.")
                        return False
                else:
                    print(f"[WallUpgrader] Storages below full trigger threshold ({int(trigger_pct*100)}%) (Gold: {gold:,}/{max_g:,}, Elixir: {elixir:,}/{max_e:,}). Skipping dump.")
                    return False

        elif current_storage_percent is not None:
            if current_storage_percent >= self.trigger_percentage or force:
                should_dump = True
            else:
                print(f"[WallUpgrader] Storages at {current_storage_percent}% (< {self.trigger_percentage}%). Skipping dump.")
                return False
        else:
            should_dump = True

        if not should_dump or self.check_should_abort():
            return False

        print("\n[WallUpgrader] >>> INITIATING WALL DUMP ROUTINE VIA BUILD MENU <<<")

        # 0. Check whether any builder is free
        frame_home = self.capture.get_frame(target_size=(1280, 720))
        if self.detector.has_zero_free_builders(frame_home):
            if not force:
                print("[WallUpgrader] Notice: 0 free builders available (all builders busy).")
                print("[WallUpgrader] In Clash of Clans, walls require at least 1 free builder to upgrade. Skipping dump.")
                return False
            else:
                print("[WallUpgrader] Notice: All builders are busy. Proceeding in test mode...")

        if self.check_should_abort():
            return False

        # 1. Locate and select an unupgraded wall via Build Menu (User preferred method)
        selected = self._select_wall_from_builder_menu(avail_gold=avail_gold, avail_elixir=avail_elixir)
        if not selected or self.check_should_abort():
            print("[WallUpgrader] No unupgraded walls found in Build Menu or abort requested.")
            self._close_menus()
            return {"success": False, "walls_upgraded": 0, "spent_amount": 0, "reason": "no_wall_found"}

        # 2. Execute batch upgrade using Upgrade More / Build Menu 2-Row Layout
        row_cost = getattr(self, "_last_selected_wall_cost", 0)
        result = self._execute_upgrade_more_cycle(avail_gold=avail_gold, avail_elixir=avail_elixir, row_cost=row_cost)

        # 3. Clean up and restore neutral home screen
        self._close_menus()
        return result

    def _close_menus(self):
        """Safely dismisses any open menus, dialogs, or panels without clicking storage bars or pressing back."""
        self.adb.tap_empty_grass()
        time.sleep(0.3)
        frame = self.capture.get_frame(target_size=(1280, 720))
        if frame is not None:
            # Check for Star Bonus modal Okay button
            star_btn = self.detector.check_star_bonus_popup(frame)
            if star_btn:
                self.adb.tap(star_btn[0], star_btn[1])
                time.sleep(0.4)

            # Check for modal close X (e.g. Cardboard chest / event modal)
            modal_x = self.detector.check_modal_popup(frame)
            if modal_x:
                self.adb.tap(modal_x[0], modal_x[1])
                time.sleep(0.3)

            panel_x = self.detector.find_template(frame, "buildings_panel_close_x", threshold=0.75)
            if panel_x:
                self.adb.tap(panel_x[0], panel_x[1])
                time.sleep(0.3)
            else:
                close_x = frame[15:55, 1220:1265]
                if close_x.size > 0 and np.sum((close_x[:, :, 2] > 165) & (close_x[:, :, 1] < 75) & (close_x[:, :, 0] < 75)) >= 20:
                    self.adb.tap(1240, 35)
                    time.sleep(0.3)
                else:
                    self.adb.tap_empty_grass()
                    time.sleep(0.2)

    def _is_build_drawer_open(self, frame):
        """Verifies if the Build / Builder suggestions drawer is currently open on the right."""
        if frame is None or frame.size == 0:
            return False
        # Fast landmark: Red close button with white 'X' at top right of drawer (x: 1210..1265, y: 10..60)
        roi = frame[10:60, 1210:1265]
        red_pts = np.sum((roi[:, :, 2] > 175) & (roi[:, :, 1] < 70) & (roi[:, :, 0] < 70))
        white_pts = np.sum((roi[:, :, 2] > 190) & (roi[:, :, 1] > 190) & (roi[:, :, 0] > 190))
        if red_pts >= 40 and white_pts >= 10:
            return True
        if self.detector.find_template(frame, "buildings_panel_close_x", threshold=0.72):
            return True
        return False

    def _select_wall_from_builder_menu(self, avail_gold=0, avail_elixir=0):
        """
        Follows the user's exact fixed steps:
        1. Click the 'Build' button (bottom right hammer at (1220, 660)).
        2. In the right panel ('Buildings & Heroes' at x=740..1275), progressively scan for Wall entries.
        3. Intelligently selects Wall rows accepting Elixir or Gold based on availability.
        4. Tap the Wall row to auto-select the wall on the map and open batch upgrade mode.
        """
        # Determine preferred resource for filtering
        preferred_resource = None
        if self.priority == "ELIXIR":
            preferred_resource = "ELIXIR"
        elif self.priority == "GOLD":
            preferred_resource = "GOLD"
        elif avail_elixir >= 3500000 or (avail_elixir >= 500000 and avail_elixir > avail_gold):
            preferred_resource = "ELIXIR"
        elif avail_gold >= 3500000 or (avail_gold >= 500000 and avail_gold >= avail_elixir):
            preferred_resource = "GOLD"
        elif avail_elixir >= 200000 and avail_elixir > avail_gold:
            preferred_resource = "ELIXIR"
        else:
            preferred_resource = "GOLD"

        # Deselect any prior open building menu cleanly on empty grass
        self.adb.tap_empty_grass()
        time.sleep(0.5)

        # 1. Tap Build button (bottom right hammer at 1210, 650)
        frame = self.capture.get_frame(target_size=(1280, 720))
        drawer_open = self._is_build_drawer_open(frame)
        build_btn_pos = (1210, 650)
        tmpl_build = self.detector.find_template(frame, "build_button", threshold=0.6)
        if tmpl_build:
            build_btn_pos = tmpl_build

        if not drawer_open:
            # Check for any temporary cardboard box/chest modal or popup first
            modal_x = self.detector.check_modal_popup(frame)
            if modal_x:
                self.adb.tap(modal_x[0], modal_x[1])
                time.sleep(0.5)
                frame = self.capture.get_frame(target_size=(1280, 720))

            print(f"[WallUpgrader] Step 1: Clicking 'Build' button at {build_btn_pos}...")
            self.adb.tap(build_btn_pos[0], build_btn_pos[1])
            time.sleep(1.2)
            frame = self.capture.get_frame(target_size=(1280, 720))
            if not self._is_build_drawer_open(frame):
                print(f"[WallUpgrader] Drawer did not open on first click. Retrying at {build_btn_pos}...")
                self.adb.tap(build_btn_pos[0], build_btn_pos[1])
                time.sleep(1.0)
                frame = self.capture.get_frame(target_size=(1280, 720))

        # 2. Progressively scan the Build drawer for genuine Wall entries
        # Walls typically appear within 1 to 5 scrolls from top. Lower level walls appear further down.
        print(f"[WallUpgrader] Scanning Build panel for Wall entries (Preferred Resource: {preferred_resource}, Strategy: {self.strategy})...")
        
        # Comprehensive Drawer Wall Cataloger
        # If CHEAPEST_FIRST: We explore up to 6 scrolls downwards, recording all wall entries and costs.
        # An ultra-cheap wall (cost <= 10,000, e.g. 1k, 5k, 10k) is the lowest possible tier in COC.
        # If encountered, we can stop immediately and select it.
        # Otherwise, we find the lowest cost across the whole drawer.
        discovered_candidates = []  # List of {"pos": pos, "cost": cost, "scroll_index": i, "resource": res}
        current_scroll = 0
        max_scroll_attempts = 9

        for attempt in range(max_scroll_attempts):
            if self.check_should_abort():
                return False
            frame = self.capture.get_frame(target_size=(1280, 720))
            if not self._is_build_drawer_open(frame):
                print(f"[WallUpgrader] Drawer closed unexpectedly on scroll {attempt}. Reopening via Build button at {build_btn_pos}...")
                self.adb.tap(build_btn_pos[0], build_btn_pos[1])
                time.sleep(1.0)
                frame = self.capture.get_frame(target_size=(1280, 720))

            # Find all wall entries visible on the current screen slice
            visible_walls = self.detector.find_all_walls_in_builder_menu(frame, ocr_reader=self.ocr)
            
            if visible_walls:
                for w in visible_walls:
                    w_pos = w["pos"]
                    w_cost = w.get("cost", 0)
                    w_res = w.get("resource", "BOTH")
                    
                    # Avoid duplicate records at same vertical position in same scroll
                    if not any(c["scroll_index"] == attempt and abs(c["pos"][1] - w_pos[1]) < 25 for c in discovered_candidates):
                        cost_str = f" (Cost: {w_cost:,})" if w_cost > 0 else ""
                        print(f"[WallUpgrader] Discovered Wall at scroll {attempt}, pos={w_pos}{cost_str}, resource={w_res}.")
                        
                        discovered_candidates.append({
                            "pos": w_pos,
                            "cost": w_cost,
                            "scroll_index": attempt,
                            "resource": w_res,
                            "y": w_pos[1]
                        })

            current_scroll = attempt
            if attempt < max_scroll_attempts - 1:
                # If we've already discovered the lowest possible wall tier in CoC (cost <= 10,000), no need to scroll further
                cheapest_so_far = min([c["cost"] for c in discovered_candidates if c["cost"] > 0], default=99999999)
                if cheapest_so_far <= 10000:
                    print(f"[WallUpgrader] Lowest wall tier ({cheapest_so_far:,}) already discovered. Stopping downward exploration.")
                    break

                # Exploring further down Build drawer for lowest cost wall
                print(f"[WallUpgrader] Exploring further down Build drawer for lowest cost wall (scroll {attempt + 1}/{max_scroll_attempts})...")
                self.adb.swipe(1050, 480, 1050, 240, duration_ms=450)
                time.sleep(0.8)
                # Check if swipe actually moved the content (drawer bottom detection)
                frame_after = self.capture.get_frame(target_size=(1280, 720))
                if frame is not None and frame_after is not None:
                    drawer_diff = float(np.mean(np.abs(frame[150:550, 950:1260].astype(int) - frame_after[150:550, 950:1260].astype(int))))
                    if drawer_diff < 3.5:
                        print(f"[WallUpgrader] Drawer bottom reached at scroll {attempt + 1} (content unchanged). Halting downward exploration.")
                        break

        # After finishing the drawer exploration:
        if discovered_candidates:
            # Filter by preferred resource if applicable and available
            filtered = discovered_candidates
            if preferred_resource == "ELIXIR":
                elixir_cands = [c for c in discovered_candidates if c["resource"] in ["ELIXIR", "BOTH"]]
                if elixir_cands:
                    filtered = elixir_cands
            elif preferred_resource == "GOLD":
                gold_cands = [c for c in discovered_candidates if c["resource"] in ["GOLD", "BOTH"]]
                if gold_cands:
                    filtered = gold_cands

            # Sort according to strategy
            if self.strategy == "CHEAPEST_FIRST":
                # Prefer lowest positive cost; if costs equal or zero, prefer higher scroll_index (further down)
                filtered.sort(key=lambda c: (c["cost"] if c["cost"] > 0 else 99999999, -c["scroll_index"], -c["y"]))
            else:
                filtered.sort(key=lambda c: (-c["cost"] if c["cost"] > 0 else 0, c["scroll_index"], c["y"]))

            best_choice = filtered[0]
            print(f"[WallUpgrader] >>> Best wall candidate selected across whole drawer: Cost={best_choice['cost']:,}, Resource={best_choice['resource']}, Scroll Index={best_choice['scroll_index']}.")

            # If the best candidate was discovered at an earlier scroll index, scroll back up:
            scroll_diff = current_scroll - best_choice["scroll_index"]
            if scroll_diff > 0:
                print(f"[WallUpgrader] Scrolling back up {scroll_diff} step(s) to reach best wall (Cost: {best_choice['cost']:,})...")
                for s in range(scroll_diff):
                    self.adb.swipe(1050, 240, 1050, 480, duration_ms=450)
                    time.sleep(0.7)
                    f_mid = self.capture.get_frame(target_size=(1280, 720))
                    walls_mid = self.detector.find_all_walls_in_builder_menu(f_mid, ocr_reader=self.ocr)
                    if walls_mid:
                        target_cost = best_choice.get("cost", 0)
                        if target_cost > 0:
                            matches = [w for w in walls_mid if abs(w.get("cost", 0) - target_cost) <= 5000]
                            if matches:
                                print(f"[WallUpgrader] Target wall (Cost: {target_cost:,}) already in view after {s + 1} scroll-up step(s)!")
                                break

            # Re-read screen at this position and tap the target wall row
            frame_target = self.capture.get_frame(target_size=(1280, 720))
            best_pos = self.detector.find_wall_in_builder_menu(
                frame_target,
                preferred_resource=preferred_resource,
                strategy=self.strategy,
                ocr_reader=self.ocr
            )
            if not best_pos:
                # Fallback: search for any wall row on target frame without resource filter
                best_pos = self.detector.find_wall_in_builder_menu(
                    frame_target,
                    strategy=self.strategy,
                    ocr_reader=self.ocr
                )

            # Micro-nudge if rows are slightly offset
            if not best_pos:
                print("[WallUpgrader] Drawer rows slightly misaligned. Applying micro-nudge swipe...")
                self.adb.swipe(1050, 340, 1050, 420, duration_ms=300)
                time.sleep(0.5)
                frame_target = self.capture.get_frame(target_size=(1280, 720))
                best_pos = self.detector.find_wall_in_builder_menu(
                    frame_target,
                    strategy=self.strategy,
                    ocr_reader=self.ocr
                )

            # Strict building protection safeguard: NEVER blind-tap an old coordinate after swiping!
            if not best_pos:
                print("[WallUpgrader] 🛑 SAFEGUARD: No verified Wall row visible at this scroll position! Refusing blind tap to protect buildings.")
                self.adb.tap_empty_grass()
                time.sleep(0.4)
                return False

            print(f"[WallUpgrader] Step 2: Selecting target Wall entry at {best_pos}...")
            self.adb.tap(best_pos[0], best_pos[1])
            time.sleep(1.3)

            f_check = self.capture.get_frame(target_size=(1280, 720))
            layout = self.detector.detect_wall_batch_layout(f_check)
            if layout and layout.get("is_wall"):
                print(f"[WallUpgrader] Confirmed wall selected on map (Layout: {layout['layout']}).")
                self._last_selected_wall_cost = best_choice["cost"]
                return True
            else:
                print("[WallUpgrader] Tapped row did not open wall toolbar on map. Retrying...")
                self.adb.tap_empty_grass()
                time.sleep(0.4)

        # Close build panel safely if still open
        frame = self.capture.get_frame(target_size=(1280, 720))
        panel_x = self.detector.find_template(frame, "buildings_panel_close_x", threshold=0.75) if frame is not None else None
        if panel_x:
            self.adb.tap(panel_x[0], panel_x[1])
        else:
            self.adb.tap_empty_grass()
        time.sleep(0.5)

        print("[WallUpgrader] Notice: No verified Wall entry found in Build panel. Safely standing by (zero blind taps).")
        return False

    def _execute_upgrade_more_cycle(self, avail_gold=0, avail_elixir=0, row_cost=0):
        """
        Dynamically calculates and upgrades the exact maximum number of walls
        affordable with available Gold or Elixir (0 GEMS SPENT).
        - If available resources only afford 1 wall:
            Directly executes single-wall upgrade using Gold or Elixir (no batch mode needed, 0 popups).
        - If multiple walls are affordable:
            Taps 'Upgrade More' (Card 2 at (464, 566)) to open batch options.
            NEVER taps 'Select Row' (Card 1)!
            Inside options, uses '+10', '+1', and '-1' to dynamically scale wall count to budget.
            Interlocks strictly on RED price detection to ensure 0 gems are spent.
            Executes upgrade with chosen resource and confirms the green 'Okay' dialog.
        """
        frame = self.capture.get_frame(target_size=(1280, 720))

        layout_info = self.detector.detect_wall_batch_layout(frame)
        if not layout_info or not layout_info.get("is_wall", True):
            print("[WallUpgrader] 🛑 CRITICAL SAFEGUARD: Selected entity on map is NOT a wall! Aborting dump cycle to protect buildings.")
            self._close_menus()
            return {"success": False, "reason": "non_wall_safeguard"}

        has_elixir = layout_info.get("has_elixir", True)
        is_two_row = ("TWO_ROW" in layout_info.get("layout", ""))
        default_gold = (397, 632) if is_two_row else (605, 567)
        default_elixir = (535, 632) if is_two_row else (745, 567)
        btn_upgrade_gold = layout_info.get("upgrade_gold") or default_gold
        btn_upgrade_elixir = layout_info.get("upgrade_elixir") or default_elixir

        # STRICT INVARIANT: In single-row mode, upgrade buttons MUST NEVER be at x < 540!
        # Card 0 is Info (~185), Card 1 is 'Select Row' (~327), and Card 2 is 'Upgrade More' (~466)!
        if not is_two_row:
            if btn_upgrade_gold and btn_upgrade_gold[0] < 540:
                print(f"[WallUpgrader] Correcting gold upgrade button from false position {btn_upgrade_gold} (Select Row/More) -> {default_gold}")
                btn_upgrade_gold = default_gold
            if btn_upgrade_elixir and btn_upgrade_elixir[0] < 680:
                btn_upgrade_elixir = default_elixir

        # Single wall cost estimation
        # Prioritize exact cost read from drawer row (e.g. 5,000, 10,000, 500,000)
        single_cost = row_cost if row_cost > 0 else 500000

        # Only fallback to reading button crop if drawer row cost was unavailable
        if row_cost <= 0:
            ref_btn = btn_upgrade_elixir if has_elixir else btn_upgrade_gold
            bx, by = ref_btn
            patch = frame[max(0, by - 48) : min(720, by - 12), max(0, bx - 48) : min(1280, bx + 22)]
            raw_cost = self.ocr.parse_digits_from_crop(patch) if hasattr(self, "ocr") and self.ocr else 0
            valid_tiers = [
                200, 1000, 5000, 10000, 20000, 30000, 50000, 60000, 75000,
                100000, 200000, 300000, 500000, 800000, 1000000, 2000000, 3000000,
                4000000, 5000000, 7000000, 9000000
            ]
            if raw_cost > 0:
                for tier in valid_tiers:
                    if abs(raw_cost - tier) <= max(200, tier * 0.15):
                        single_cost = tier
                        break

        # Check affordability for 1 wall
        gold_red_1 = self.detector.is_wall_upgrade_price_insufficient(frame, "GOLD", button_pos=btn_upgrade_gold)
        elixir_red_1 = self.detector.is_wall_upgrade_price_insufficient(frame, "ELIXIR", button_pos=btn_upgrade_elixir) if has_elixir else True

        chosen_resource = None
        if not has_elixir:
            if not gold_red_1 and avail_gold >= single_cost:
                chosen_resource = "GOLD"
        else:
            if self.priority == "ELIXIR":
                if not elixir_red_1 and avail_elixir >= single_cost:
                    chosen_resource = "ELIXIR"
                elif not gold_red_1 and avail_gold >= single_cost:
                    print("[WallUpgrader] Elixir insufficient, falling back to Gold...")
                    chosen_resource = "GOLD"
            elif self.priority == "GOLD":
                if not gold_red_1 and avail_gold >= single_cost:
                    chosen_resource = "GOLD"
                elif not elixir_red_1 and avail_elixir >= single_cost:
                    print("[WallUpgrader] Gold insufficient, falling back to Elixir...")
                    chosen_resource = "ELIXIR"
            else:
                # BOTH: prioritize resource with highest excess above reserve
                if avail_elixir >= single_cost and not elixir_red_1 and (avail_elixir >= avail_gold or gold_red_1):
                    chosen_resource = "ELIXIR"
                elif not gold_red_1 and avail_gold >= single_cost:
                    chosen_resource = "GOLD"
                elif not elixir_red_1 and avail_elixir >= single_cost:
                    chosen_resource = "ELIXIR"

        if not chosen_resource:
            print(f"[WallUpgrader] 🛑 INSUFFICIENT RESOURCES: Neither Gold ({avail_gold:,}) nor Elixir ({avail_elixir:,}) can afford 1 wall ({single_cost:,}). Deselecting...")
            self._close_menus()
            return False

        if chosen_resource == "GOLD":
            # Strict user safeguard: Ensure at least 2,000 Gold remains in storage after Gold wall upgrades
            if avail_gold < single_cost:
                print("[WallUpgrader] 🛑 Gold wall upgrade skipped: less than 2,000 Gold would remain after upgrade. Preserving 2,000 Gold reserve for matchmaking fees.")
                if avail_elixir >= single_cost and not elixir_red_1:
                    print("[WallUpgrader] Switching to Elixir for wall upgrade instead!")
                    chosen_resource = "ELIXIR"
                else:
                    self._close_menus()
                    return False

        avail_budget = avail_elixir if chosen_resource == "ELIXIR" else avail_gold
        target_max_walls = max(1, self.max_walls_per_cycle)
        max_affordable = min(avail_budget // single_cost, target_max_walls)
        print(f"[WallUpgrader] Budget: Resource={chosen_resource}, Available={avail_budget:,}, Single Cost={single_cost:,} -> Affordable={max_affordable} walls.")

        target_btn = btn_upgrade_elixir if chosen_resource == "ELIXIR" else btn_upgrade_gold

        # Case 1: Only 1 wall affordable -> Single wall upgrade directly from toolbar
        if max_affordable <= 1:
            print(f"[WallUpgrader] Upgrading single wall directly with {chosen_resource} at {target_btn}...")
            self.adb.tap(target_btn[0], target_btn[1])
            time.sleep(1.0)
            f_single_dlg = self.capture.get_frame(target_size=(1280, 720))
            confirm_info = self.detector.find_wall_confirm_button(f_single_dlg)
            if confirm_info:
                self.adb.tap(confirm_info[0][0], confirm_info[0][1])
                time.sleep(0.5)
            print(f"[WallUpgrader] >>> SINGLE WALL UPGRADE COMPLETED ({single_cost:,} {chosen_resource} spent, 0 GEMS SPENT)! <<<")
            return {
                "success": True,
                "walls_upgraded": 1,
                "spent_amount": single_cost,
                "resource": chosen_resource,
                "single_cost": single_cost
            }

        # Case 2: Multiple walls affordable -> Activate batch options via 'Upgrade More' (Card 2)
        # Note: A newly selected wall from the build menu is NEVER in batch mode initially.
        batch_opened = False
        is_two_row = ("TWO_ROW" in layout_info.get("layout", ""))
        default_more = (604, 514) if is_two_row else (464, 566)
        more_pos = layout_info.get("upgrade_more") or default_more

        # Strict collision safeguards against Select Row
        select_row_pos = layout_info.get("select_row") or self.detector.find_template(frame, "wall_select_row", threshold=0.68)
        if select_row_pos and abs(more_pos[0] - select_row_pos[0]) < 70 and abs(more_pos[1] - select_row_pos[1]) < 60:
            print(f"[WallUpgrader] 🛑 SAFEGUARD: more_pos {more_pos} collided with Select Row {select_row_pos}! Shifting to Card 2...")
            more_pos = (select_row_pos[0] + 138, more_pos[1])

        if is_two_row and more_pos[0] < 540:
            more_pos = (604, 514)
        elif not is_two_row and more_pos[0] < 430:
            more_pos = (464, 566)

        for attempt in range(3):
            print(f"[WallUpgrader] Tapping 'Upgrade More' (Card 2) at {more_pos} to activate batch options (NEVER 'Select Row') (attempt {attempt + 1}/3)...")
            self.adb.tap(more_pos[0], more_pos[1])
            time.sleep(1.0)
            frame = self.capture.get_frame(target_size=(1280, 720))
            layout_info = self.detector.detect_wall_batch_layout(frame)
            if layout_info and layout_info.get("is_batch", False):
                batch_opened = True
                print("[WallUpgrader] Batch options successfully activated!")
                break

        if not batch_opened:
            print("[WallUpgrader] Notice: Batch options could not be activated safely. Falling back to single wall upgrade (NEVER tapping Select Row)!")
            print(f"[WallUpgrader] Upgrading single wall directly with {chosen_resource} at {target_btn}...")
            self.adb.tap(target_btn[0], target_btn[1])
            time.sleep(1.0)
            f_dlg = self.capture.get_frame(target_size=(1280, 720))
            confirm_info = self.detector.find_wall_confirm_button(f_dlg)
            if confirm_info:
                self.adb.tap(confirm_info[0][0], confirm_info[0][1])
                time.sleep(0.5)
            return {
                "success": True,
                "walls_upgraded": 1,
                "spent_amount": single_cost,
                "resource": chosen_resource,
                "single_cost": single_cost
            }

        # Verify that Select Row is definitely absent before performing any batch taps
        f_batch_check = self.capture.get_frame(target_size=(1280, 720))
        live_select_row = self.detector.find_template(f_batch_check, "wall_select_row", threshold=0.68)
        if live_select_row:
            print(f"[WallUpgrader] 🛑 CRITICAL SAFEGUARD: 'Select Row' is still visible on screen at {live_select_row}! Refusing batch taps.")
            self._close_menus()
            return False

        # Batch mode is verified active: clear pre-batch select_row coordinate
        select_row_pos = None

        is_two_row = ("TWO_ROW" in layout_info.get("layout", ""))
        if is_two_row:
            btn_remove_1 = layout_info.get("remove_1") or (324, 505)
            btn_add_10 = layout_info.get("add_10") or (462, 505)
            btn_add_1 = layout_info.get("add_1") or (602, 505)
            target_btn = layout_info.get("upgrade_elixir") if chosen_resource == "ELIXIR" else layout_info.get("upgrade_gold")
            target_btn = target_btn or ((535, 632) if chosen_resource == "ELIXIR" else (397, 632))
        else:
            btn_remove_1 = layout_info.get("remove_1") or (185, 565)
            btn_add_10 = layout_info.get("add_10") or (322, 566)
            btn_add_1 = layout_info.get("add_1") or (464, 566)
            target_btn = layout_info.get("upgrade_elixir") if chosen_resource == "ELIXIR" else layout_info.get("upgrade_gold")
            target_btn = target_btn or ((745, 567) if chosen_resource == "ELIXIR" else (605, 567))

        # Absolute safeguard against duplicate / collapsed button coordinates
        if btn_add_10 and btn_add_1 and abs(btn_add_10[0] - btn_add_1[0]) < 60:
            step = 138 if is_two_row else 140
            btn_add_10 = (btn_add_1[0] - step, btn_add_1[1])
            btn_remove_1 = (btn_add_10[0] - step, btn_add_10[1])

        # Enforce that btn_add_10 is strictly Card 1 and never Card 0 (which is -1 at x~185)
        if not is_two_row:
            if btn_add_10 and btn_add_10[0] < 260:
                btn_add_10 = (322, 566)
            if btn_add_1 and btn_add_1[0] < 390:
                btn_add_1 = (464, 566)
            if btn_remove_1 and btn_remove_1[0] > 260:
                btn_remove_1 = (185, 565)
        else:
            if btn_add_10 and btn_add_10[0] < 400:
                btn_add_10 = (462, 505)
            if btn_add_1 and btn_add_1[0] < 540:
                btn_add_1 = (602, 505)
            if btn_remove_1 and btn_remove_1[0] > 400:
                btn_remove_1 = (324, 505)

        print(f"[WallUpgrader] Verified batch buttons: -1 at {btn_remove_1}, +10 at {btn_add_10}, +1 at {btn_add_1}")

        # Collision interlock against Select Row coordinate (only if Select Row is genuinely on screen)
        live_select = self.detector.find_template(f_batch_check, "wall_select_row", threshold=0.68)
        if live_select and abs(btn_add_10[0] - live_select[0]) < 65 and abs(btn_add_10[1] - live_select[1]) < 65:
            print(f"[WallUpgrader] 🛑 ABORT: btn_add_10 {btn_add_10} overlaps with Select Row {live_select}! Refusing tap.")
            self._close_menus()
            return False

        current_count = 1
        print(f"[WallUpgrader] Inside batch options (initially 1 wall selected). Max affordable: {max_affordable} walls (Budget: {avail_budget:,} {chosen_resource}).")

        # STRICT RESOURCE & CAPACITY CHECK:
        # Calculate exactly how many +10 and +1 additions can be safely performed without exceeding budget
        # 1. Tap '+10' as many times as can be safely afforded without exceeding max_affordable or avail_budget
        while (current_count + 10) <= max_affordable and ((current_count + 10) * single_cost) <= avail_budget:
            if not btn_add_10:
                break
            print(f"[WallUpgrader] Safely adding 10 walls via '+10' at {btn_add_10} (count: {current_count + 10}/{max_affordable})...")
            self.adb.tap(btn_add_10[0], btn_add_10[1], custom_delay=0.12)
            current_count += 10
            time.sleep(0.2)

        # 2. Tap '+1' for remaining affordable walls
        needed_singles = max_affordable - current_count
        if needed_singles > 0 and btn_add_1:
            print(f"[WallUpgrader] Safely adding {needed_singles} wall(s) via '+1' at {btn_add_1} (budget remaining: {avail_budget - current_count * single_cost:,})...")
            for _ in range(needed_singles):
                if (current_count + 1) * single_cost > avail_budget:
                    print(f"[WallUpgrader] Addition wall check: Next wall would exceed budget ({avail_budget:,}). Stopping additions at {current_count} walls.")
                    break
                self.adb.tap(btn_add_1[0], btn_add_1[1], custom_delay=0.10)
                current_count += 1
                time.sleep(0.12)

        time.sleep(0.3)
        print(f"[WallUpgrader] Wall additions finalized: {current_count} walls selected. Total cost: {current_count * single_cost:,} {chosen_resource} (Budget: {avail_budget:,}).")

        # Back off using -1 if price unexpectedly turned RED (e.g. slight OCR discrepancy)
        frame_chk = self.capture.get_frame(target_size=(1280, 720))
        if self.detector.is_wall_upgrade_price_insufficient(frame_chk, chosen_resource, button_pos=target_btn):
            print(f"[WallUpgrader] Price for {chosen_resource} is RED ({current_count} walls). Backing off with -1...")
            while current_count > 1:
                self.adb.tap(btn_remove_1[0], btn_remove_1[1], custom_delay=0.12)
                current_count -= 1
                time.sleep(0.2)
                frame_chk = self.capture.get_frame(target_size=(1280, 720))
                if not self.detector.is_wall_upgrade_price_insufficient(frame_chk, chosen_resource, button_pos=target_btn):
                    print(f"[WallUpgrader] Price turned affordable (WHITE) at {current_count} walls.")
                    break

        # Final Zero-Gems Safeguard Interlock
        frame_final = self.capture.get_frame(target_size=(1280, 720))
        if self.detector.is_wall_upgrade_price_insufficient(frame_final, chosen_resource, button_pos=target_btn):
            print(f"[WallUpgrader] 🛑 ZERO-GEMS SAFETY ABORT: Price remains RED for {chosen_resource}! Aborting to ensure 0 gems spent.")
            self._close_menus()
            return {"success": False, "walls_upgraded": 0, "spent_amount": 0, "resource": chosen_resource}

        # Execute Upgrade
        print(f"[WallUpgrader] Tapping Upgrade button ({chosen_resource}) at {target_btn}...")
        self.adb.tap(target_btn[0], target_btn[1])
        time.sleep(1.2)

        # Handle Confirmation Dialog
        frame_dlg = self.capture.get_frame(target_size=(1280, 720))

        # 1. Building Modal Safeguard
        building_close_x = self.detector.check_building_upgrade_modal(frame_dlg)
        if building_close_x:
            print(f"[WallUpgrader] 🛑 CRITICAL SAFEGUARD: Building upgrade modal detected at {building_close_x}! Dismissing modal immediately.")
            self.adb.tap(building_close_x[0], building_close_x[1])
            time.sleep(0.5)
            self._close_menus()
            return {"success": False, "walls_upgraded": 0, "spent_amount": 0, "reason": "building_safeguard_triggered"}

        # 2. Gem Purchase Modal Safeguard
        if self.detector.check_builders_busy_modal(frame_dlg) or self.detector.check_gem_purchase_modal(frame_dlg):
            print("[WallUpgrader] 🛑 Gem purchase / Builders busy modal detected! Cancelling immediately...")
            cancel_pos = self.detector.get_calibrated_coord("wall_confirm_cancel") or (467, 456)
            self.adb.tap(cancel_pos[0], cancel_pos[1])
            time.sleep(0.5)
            self._close_menus()
            return {"success": False, "walls_upgraded": 0, "spent_amount": 0, "resource": chosen_resource}

        # 3. Verified Batch Confirmation via 'wall_confirm_okay' template
        confirm_info = self.detector.find_wall_confirm_button(frame_dlg)
        if confirm_info:
            confirm_pos, mode = confirm_info
            print(f"[WallUpgrader] Confirming {mode} upgrade dialog at {confirm_pos}...")
            self.adb.tap(confirm_pos[0], confirm_pos[1])
            time.sleep(1.2)
        else:
            print("[WallUpgrader] No modal dialog detected (upgrade applied directly by game).")

        time.sleep(1.2)
        spent_total = current_count * single_cost
        print(f"[WallUpgrader] >>> WALL UPGRADE BATCH COMPLETED ({current_count} walls upgraded, {spent_total:,} {chosen_resource} spent, 0 GEMS SPENT)! <<<")
        return {
            "success": True,
            "walls_upgraded": current_count,
            "spent_amount": spent_total,
            "resource": chosen_resource,
            "single_cost": single_cost
        }
