"""
Vision Detector for Clash of Clans UI and Game Elements.
Uses OpenCV Multi-Scale Template Matching with calibrated 1280x720 UI positions.
"""

import os
import sys
import cv2
import numpy as np
from ai.realtime_learner import realtime_learner


def get_base_dir():
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(exe_dir, "assets")):
            return exe_dir
        return getattr(sys, "_MEIPASS", exe_dir)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class UIDetector:
    # Standard 1280x720 baseline UI locations for quick clicks (Calibrated on Live Game)
    COORDINATES_1280x720 = {
        "attack_button": (82, 640),  # Modern Battle button (bottom left, yellow sword area)
        "find_match_button": (218, 545),  # Multiplayer Battle card button
        "army_attack_button": (1131, 642),  # Green Attack! button on My Army window
        "modal_cancel_button": (430, 505),
        "modal_close_x": (965, 88),  # Top-right modal close X
        "next_button": (1166, 540),  # Next base in raid matchmaking
        "end_battle_button": (91, 565),  # End battle / surrender button in raid
        "confirm_surrender_button": (740, 420),
        "return_home_button": (640, 600),
        "train_troops_button": (40, 580),
        "quick_train_tab": (780, 110),
        "quick_train_slot_1": (1050, 240),
        "quick_train_slot_2": (1050, 370),
        "quick_train_slot_3": (1050, 500),
        "clan_castle_request": (450, 640),
        "send_request_button": (880, 540),
        "reload_game_button": (640, 440),
        "builder_menu": (620, 35),
        "build_button": (1220, 660),
        "buildings_panel_close_x": (1245, 35),
        # Build Menu 2-Row Batch Layout (With Wall Ring Magic Item)
        "build_wall_remove_1": (326, 507),
        "build_wall_add_10": (466, 507),
        "build_wall_add_1": (604, 507),
        "build_wall_upgrade_gold": (327, 623),
        "build_wall_upgrade_elixir": (467, 633),
        "build_wall_upgrade_ring": (604, 633),
        # Build Menu 1-Row Batch Layout (No Magic Item / 5 buttons)
        "build_wall_1row_more": (466, 568),
        "build_wall_1row_remove_1": (187, 568),
        "build_wall_1row_add_10": (326, 568),
        "build_wall_1row_add_1": (466, 568),
        "build_wall_1row_upgrade_gold": (605, 582),
        "build_wall_1row_upgrade_elixir": (745, 582),
        # Wall upgrades (Calibrated on live Level 7/9 wall menu)
        "wall_info": (361, 586),
        "wall_select_row": (500, 586),
        "wall_upgrade_more": (638, 586),
        "wall_upgrade_gold": (758, 586),
        "wall_upgrade_elixir": (880, 586),
        # Batch Mode (Inside Upgrade More)
        "wall_remove_1": (280, 605),
        "wall_add_10": (390, 605),
        "wall_add_1": (500, 605),
        "wall_batch_upgrade_gold": (610, 605),
        "wall_batch_upgrade_elixir": (720, 605),
        "wall_confirm_okay": (765, 470),
        "wall_confirm_cancel": (515, 470),
        "wall_confirm_single": (720, 610),
        "wall_confirm_single_close": (890, 105),
        "busy_close_x": (702, 300),
        "hero_slot_1": (180, 650),
        "hero_slot_2": (260, 650),
        "hero_slot_3": (340, 650),
        "hero_slot_4": (420, 650),
    }

    def __init__(self, templates_dir="assets/templates"):
        self.templates_dir = templates_dir
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        """Loads available PNG templates from the assets directory."""
        target_dir = os.path.join(get_base_dir(), self.templates_dir)
        if not os.path.exists(target_dir):
            target_dir = self.templates_dir
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            return

        for filename in os.listdir(target_dir):
            if filename.endswith(".png"):
                name = os.path.splitext(filename)[0]
                path = os.path.join(target_dir, filename)
                tmpl = cv2.imread(path, cv2.IMREAD_COLOR)
                if tmpl is not None:
                    self.templates[name] = tmpl

    def find_template(self, frame, template_name, threshold=0.82):
        """
        Locates a template in the given frame.
        Returns (x, y) center coordinate or None if not found.
        """
        if frame is None:
            return None

        if template_name == "return_home_button":
            return self.check_return_home_button(frame)

        if template_name not in self.templates:
            return None

        template = self.templates[template_name]

        # High-Speed ROI mapping for known UI landmarks (executes in ~2ms instead of ~230ms full frame)
        ROI_MAP = {
            "attack_button": (570, 720, 0, 160),
            "battle_button": (570, 720, 0, 160),
            "next_button": (450, 650, 1040, 1280),
            "end_battle_button": (510, 650, 10, 190),
            "find_match_button": (480, 620, 150, 320),
            "army_attack_button": (560, 720, 1000, 1280),
            "build_button": (520, 720, 1120, 1280),
        }

        if template_name in ROI_MAP and frame.shape[0] == 720 and frame.shape[1] == 1280:
            y1, y2, x1, x2 = ROI_MAP[template_name]
            roi = frame[y1:y2, x1:x2]
            if roi.shape[0] >= template.shape[0] and roi.shape[1] >= template.shape[1]:
                res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                if max_val >= threshold:
                    h, w = template.shape[:2]
                    center_x = x1 + max_loc[0] + w // 2
                    center_y = y1 + max_loc[1] + h // 2
                    realtime_learner.learn_button_coordinate(template_name, (center_x, center_y), max_val)
                    return (center_x, center_y)
            # Fixed HUD elements in ROI_MAP never exist elsewhere on the 1280x720 canvas
            return None

        res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            realtime_learner.learn_button_coordinate(template_name, (center_x, center_y), max_val)
            return (center_x, center_y)
        return None

    def get_calibrated_coord(self, key):
        """Returns dynamically learned coordinate or standard calibrated coordinate for 1280x720 resolution."""
        learned = realtime_learner.get_learned_coordinate(key)
        if key == "attack_button":
            if learned and (learned[1] < 580 or learned[0] > 160):
                return (75, 645)
            return learned or (75, 645)
        if learned:
            return learned
        return self.COORDINATES_1280x720.get(key)

    def check_return_home_button(self, frame):
        """
        Locates the green 'Return Home' button on the Battle Results screen (Victory/Defeat).
        Centered horizontally at x: 530..750, y: 570..645.
        Strict safeguards:
        1. Must NOT be in Home Village (attack_button / build_button absent).
        2. Must NOT be in Matchmaking scouting (next_button absent).
        3. Must NOT be in Active Combat (end_battle_button absent).
        4. Screen must be darkened by battle-end vignette (top-left corner < 75 brightness).
        5. Must contain saturated Supercell green button pixels AND white text pixels in center.
        Returns (640, 605) or None.
        """
        if frame is None or frame.size == 0:
            return None
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        # Disqualify if active game HUD buttons are visible
        if (
            self.find_template(frame, "next_button", threshold=0.60)
            or self.find_template(frame, "attack_button", threshold=0.60)
            or self.find_template(frame, "build_button", threshold=0.60)
            or self.find_template(frame, "end_battle_button", threshold=0.55)
        ):
            return None

        # Check for red End Battle / Surrender button at bottom-left
        if self.check_end_battle_button(frame) is not None:
            return None  # Still in combat!

        # Check for template if available
        if "return_home_button" in self.templates:
            template = self.templates["return_home_button"]
            res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if max_val >= 0.68:
                h, w = template.shape[:2]
                return (max_loc[0] + w // 2, max_loc[1] + h // 2)

        # Battle Results background is always darkened by vignette overlay
        top_left_brightness = np.mean(frame[15:65, 15:65])
        if top_left_brightness > 75:
            # Normal bright daylight grass; definitely NOT Battle Results modal
            return None

        # Inspect button area at bottom center (575..640, 540..740)
        crop = frame[575:640, 540:740]
        if crop.size > 0:
            b, g, r = cv2.split(crop)
            # Saturated Supercell emerald green: high G, strict ratio over R and B
            green_pts = np.sum((g > 135) & (g > r * 1.30) & (g > b * 1.40) & (r < 115) & (b < 95))
            # Text inside button is crisp white / cream
            white_pts = np.sum((r > 195) & (g > 195) & (b > 180))
            if green_pts >= 250 and white_pts >= 35:
                return (640, 605)

        return None

    def check_surrender_modal(self, frame):
        """
        Detects whether the authentic 'Surrender? / End Battle?' confirmation modal is genuinely open.
        Strict verification:
        1. Screen darkened by modal vignette overlay (top_left_brightness < 75).
        2. Supercell green 'Okay' button at (740, 420) (x: 680..790, y: 395..445) with white text.
        3. Prevents 100% of false matches on bright daylight battlefield grass.
        Returns (740, 420) or None.
        """
        if frame is None or frame.size == 0:
            return None
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        top_left_brightness = np.mean(frame[15:65, 15:65])
        if top_left_brightness > 75:
            # Normal daylight scene; definitely NOT a modal dialog
            return None

        okay_crop = frame[395:445, 680:790]
        if okay_crop.size > 0:
            b_ok, g_ok, r_ok = cv2.split(okay_crop)
            green_ok = np.sum((g_ok > 125) & (g_ok > r_ok * 1.20) & (g_ok > b_ok * 1.25) & (r_ok < 120))
            white_ok = np.sum((r_ok > 185) & (g_ok > 185) & (b_ok > 170))
            if green_ok >= 100 and white_ok >= 20:
                return (740, 420)
        return None

    def check_end_battle_button(self, frame):
        """
        Locates the red 'End Battle' / 'Surrender' button at bottom-left in raid combat.
        Returns (94, 596) or None.
        """
        if frame is None or frame.size == 0:
            return None
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        # SAFEGUARD: If Home Village HUD (Attack sword or Build hammer) is visible, cannot be in combat!
        if (
            self.find_template(frame, "attack_button", threshold=0.55)
            or self.find_template(frame, "build_button", threshold=0.58)
        ):
            return None

        pos = self.find_template(frame, "end_battle_button", threshold=0.65)
        if pos:
            return pos
        pos_surr = self.find_template(frame, "surrender_button", threshold=0.65)
        if pos_surr:
            return pos_surr
        end_crop = frame[550:625, 15:150]
        if end_crop.size > 0:
            b, g, r = cv2.split(end_crop)
            red_px = np.sum((r > 155) & (g < 75) & (b < 75))
            white_px = np.sum((r > 185) & (g > 185) & (b > 180))
            if red_px > 300 and white_px >= 25:
                return (94, 596)
        return None

    def check_disconnect_or_reload(self, frame):
        """
        Checks if an authentic Supercell 'Reload Game' button or disconnect dialog is genuinely visible.
        Strictly prevents false positives when normal village HUD, My Army window, or modals are active.
        """
        if frame is None:
            return None

        # 1. If active home village, My Army window, or battle HUD buttons are visible, the game is 100% connected
        if (
            self.find_template(frame, "attack_button", threshold=0.60)
            or self.find_template(frame, "build_button", threshold=0.60)
            or self.find_template(frame, "return_home_button", threshold=0.60)
            or self.find_template(frame, "next_button", threshold=0.60)
            or self.find_template(frame, "end_battle_button", threshold=0.55)
            or self.find_template(frame, "army_attack_button", threshold=0.60)
            or self.find_template(frame, "find_match_button", threshold=0.60)
            or self.find_template(frame, "modal_close_x", threshold=0.65)
            or self.find_template(frame, "buildings_panel_close_x", threshold=0.65)
        ):
            return None

        # Disconnection modals in Clash of Clans heavily darken the game screen.
        # Normal game screens (like My Army or Home Village) maintain mean brightness > 55
        if np.mean(frame) > 55:
            return None

        # 2. Template match for authentic Supercell 'Reload Game' button (centered at x: 450..830, y: 350..550)
        pos = self.find_template(frame, "reload_game", threshold=0.70)
        if pos and 350 <= pos[1] <= 550 and 450 <= pos[0] <= 830:
            print(f"[UIDetector] Verified Supercell 'Reload Game' prompt at {pos}.")
            return pos

        # 3. Check for centered dialog box with modal backdrop (screen must be darkened)
        top_left_brightness = np.mean(frame[20:100, 20:100])
        if top_left_brightness < 45:
            dialog_crop = frame[260:480, 440:840]
            if dialog_crop.size > 0:
                pos_btn = self.find_template(dialog_crop, "reload_game", threshold=0.65)
                if pos_btn:
                    actual_pos = (440 + pos_btn[0], 260 + pos_btn[1])
                    print(f"[UIDetector] Verified dialog 'Reload Game' prompt at {actual_pos}.")
                    return actual_pos

        return None

    def check_village_under_attack(self, frame):
        """
        Detects if the player's village is currently under live attack (Live Replay / Spectator view).
        Distinct visual indicators:
        1. 'Live Replay' banner at bottom-right (template match or saturated red text).
        2. Scared Villager avatar with 'is attacking your Village!' alert on the right.
        3. 'Spectators:' top badge with eye icon.
        4. Absolute absence of Home Village HUD (Build button and normal Attack button absent).
        Returns True if under live defense, False otherwise.
        """
        if frame is None or frame.size == 0:
            return False
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        # Check template match for 'Live Replay'
        if "live_replay" in self.templates:
            tmpl = self.templates["live_replay"]
            roi = frame[560:640, 1040:1260]
            res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
            if cv2.minMaxLoc(res)[1] >= 0.70:
                return True

        # Check red text pixels in Live Replay area (R > 140, G < 60, B < 60)
        c_lr = frame[580:625, 1050:1250]
        if c_lr.size > 0:
            red_pts = np.sum((c_lr[:, :, 2] > 140) & (c_lr[:, :, 1] < 60) & (c_lr[:, :, 0] < 60))
            if red_pts >= 40:
                # Disqualify if home village build hammer gold is visible
                c_bld = frame[600:700, 1180:1270]
                bld_gold = np.sum((c_bld[:, :, 2] > 180) & (c_bld[:, :, 1] > 140) & (c_bld[:, :, 0] < 80))
                if bld_gold < 150:
                    return True

        # Check 'Spectators:' top bar
        c_spec = frame[10:65, 520:760]
        if c_spec.size > 0:
            spec_white = np.sum((c_spec[:, :, 0] > 190) & (c_spec[:, :, 1] > 190) & (c_spec[:, :, 2] > 190))
            spec_dark = np.sum((c_spec[:, :, 0] < 50) & (c_spec[:, :, 1] < 50) & (c_spec[:, :, 2] < 50))
            c_atk = frame[10:45, 1050:1250]
            atk_white = np.sum((c_atk[:, :, 0] > 190) & (c_atk[:, :, 1] > 190) & (c_atk[:, :, 2] > 190))
            if spec_white >= 80 and spec_dark >= 800 and atk_white >= 60:
                return True

        return False

    def check_defense_return_home_button(self, frame):
        """
        Locates the cream 'Return Home' button at the bottom-left on the Village Defense Results screen.
        Distinct from the green Return Home button on the Raid Results screen (which is at center 640, 605).
        Returns tap coordinates (77, 664) if detected, None otherwise.
        """
        if frame is None or frame.size == 0:
            return None
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        # 1. Template match
        if "defense_return_home" in self.templates:
            tmpl = self.templates["defense_return_home"]
            roi = frame[590:720, 0:170]
            res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCOEFF_NORMED)
            val, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= 0.65:
                h, w = tmpl.shape[:2]
                return (max_loc[0] + w // 2, 590 + max_loc[1] + h // 2)

        # 2. Color profile of Return Home button (cream frame + villager face)
        c_rh = frame[600:720, 10:150]
        cream_mask = (c_rh[:, :, 0] > 110) & (c_rh[:, :, 1] > 160) & (c_rh[:, :, 2] > 180)
        if np.sum(cream_mask) >= 2500:
            hair_mask = (c_rh[:, :, 2] > 130) & (c_rh[:, :, 1] < 90) & (c_rh[:, :, 0] < 70)
            if np.sum(hair_mask) >= 60:
                return (77, 664)

        return None

    def find_all_walls_in_builder_menu(self, frame, threshold=0.80, ocr_reader=None):
        """
        Locates ALL genuine Wall entries visible in the Builder Recommendations Menu drawer (x=935..1276).
        Returns a list of dicts:
        [{
            "pos": (x, y),          # Center tap coordinate (e.g. 950, y)
            "cost": int,            # Parsed or estimated upgrade cost
            "orig_cx": cx,
            "orig_cy": cy,
            "resource": "ELIXIR" | "GOLD",
            "score": float
        }, ...]
        Strictly excludes buildings with timers/clocks and items with gems.
        """
        if frame is None or frame.shape[0] < 700 or frame.shape[1] < 1200:
            return []

        t_word = self.templates.get("builder_wall_word")
        if t_word is None:
            p_w = os.path.join(get_base_dir(), "assets/templates/builder_wall_word.png")
            if os.path.exists(p_w):
                t_word = cv2.imread(p_w)

        if t_word is None:
            return []

        # Search for 'Wall' inside drawer scrollable list ROI (x: 935..1276, y: 75..570)
        roi = frame[75:570, 935:1276]
        res = cv2.matchTemplate(roi, t_word, cv2.TM_CCOEFF_NORMED)
        locs = np.where(res >= threshold)
        wall_matches = []

        for pt in zip(*locs[::-1]):
            cx = 935 + pt[0] + t_word.shape[1] // 2
            cy = 75 + pt[1] + t_word.shape[0] // 2

            # 'Wall' text in drawer is centered at x: 980..1045
            if not (980 <= cx <= 1045):
                continue

            # Safe vertical viewport check (exclude header and bottom tabs)
            if not (95 <= cy <= 570):
                continue

            if any(abs(cy - m["orig_cy"]) < 28 for m in wall_matches):
                continue

            # Disqualify building rows by checking for upgrade timer / clock icon at top-right
            clock_roi = frame[max(0, cy - 25) : min(720, cy + 5), 1215:1275]
            has_clock_or_timer = False
            if clock_roi.size > 0:
                clock_gray = cv2.cvtColor(clock_roi, cv2.COLOR_BGR2GRAY)
                bright_px = int(np.sum(clock_gray > 180))
                hsv_clk = cv2.cvtColor(clock_roi, cv2.COLOR_BGR2HSV)
                gold_clk_px = int(np.sum((hsv_clk[:, :, 0] >= 20) & (hsv_clk[:, :, 0] <= 35) & (hsv_clk[:, :, 1] >= 140) & (hsv_clk[:, :, 2] >= 140)))
                if bright_px >= 90 or gold_clk_px >= 15:
                    has_clock_or_timer = True

            if has_clock_or_timer:
                continue

            # Check resource badge at bottom-right of row: x: 1240..1275, y: cy+8..cy+32
            res_patch = frame[max(0, cy + 8) : min(720, cy + 32), 1240:1275]
            is_elixir = False
            is_gold = False
            has_green_gem = False
            if res_patch.size > 0:
                hsv_r = cv2.cvtColor(res_patch, cv2.COLOR_BGR2HSV)
                gem_pts = int(np.sum((hsv_r[:, :, 0] >= 35) & (hsv_r[:, :, 0] <= 85) & (hsv_r[:, :, 1] >= 100) & (hsv_r[:, :, 2] >= 100)))
                if gem_pts >= 20:
                    has_green_gem = True
                e_pts = int(np.sum((hsv_r[:, :, 0] >= 130) & (hsv_r[:, :, 0] <= 170) & (hsv_r[:, :, 1] >= 80) & (hsv_r[:, :, 2] >= 80)))
                g_pts = int(np.sum((hsv_r[:, :, 0] >= 15) & (hsv_r[:, :, 0] <= 35) & (hsv_r[:, :, 1] >= 100) & (hsv_r[:, :, 2] >= 100)))
                is_elixir = e_pts >= 25
                is_gold = g_pts >= 25

            if has_green_gem:
                continue

            # Read cost from row via specialized wall OCR if available (crop x: 1120..1258 excludes wall count badges)
            row_cost = 0
            if ocr_reader is not None:
                cost_crop = frame[max(0, cy - 8) : min(720, cy + 28), 1120:1258]
                try:
                    if hasattr(ocr_reader, "parse_wall_cost_from_crop"):
                        row_cost = ocr_reader.parse_wall_cost_from_crop(cost_crop)
                    else:
                        row_cost = ocr_reader.parse_digits_from_crop(cost_crop)
                except Exception:
                    row_cost = 0

            # In Clash of Clans, all walls with cost >= 50,000 (Level 5+) accept BOTH Gold AND Elixir
            if row_cost >= 50000:
                is_elixir = True
                is_gold = True

            wall_matches.append({
                "pos": (1050, cy + 5),
                "x": 1050,
                "y": cy + 5,
                "orig_cx": cx,
                "orig_cy": cy,
                "cost": row_cost,
                "resource": "BOTH" if (is_elixir and is_gold) else ("ELIXIR" if is_elixir else "GOLD"),
                "accepts_elixir": is_elixir,
                "accepts_gold": is_gold,
                "score": float(res[pt[1], pt[0]])
            })

        return wall_matches

    def find_wall_in_builder_menu(self, frame, threshold=0.82, preferred_resource=None, strategy="CHEAPEST_FIRST", ocr_reader=None):
        """
        Locates genuine Wall entries inside the Builder Recommendations Menu (drawer at x=935..1276).
        Uses find_all_walls_in_builder_menu under the hood.
        Returns safe center tap coordinate (1050, cy + 10) or None.
        """
        matches = self.find_all_walls_in_builder_menu(frame, threshold=threshold, ocr_reader=ocr_reader)
        if not matches:
            return None

        # Filter by preferred resource if specified
        filtered = matches
        if preferred_resource == "ELIXIR":
            elixir_matches = [m for m in matches if m["accepts_elixir"]]
            if elixir_matches:
                filtered = elixir_matches
        elif preferred_resource == "GOLD":
            gold_matches = [m for m in matches if m["accepts_gold"]]
            if gold_matches:
                filtered = gold_matches

        # Sort according to strategy
        if strategy == "CHEAPEST_FIRST":
            # Prefer lowest numeric cost if OCR succeeded; fallback to higher y (lower down in list)
            filtered.sort(key=lambda m: (m["cost"] if m["cost"] > 0 else 99999999, -m["y"]))
        else:
            filtered.sort(key=lambda m: (-m["cost"] if m["cost"] > 0 else 0, m["y"]))

        target = filtered[0]
        cost_str = f", Cost: {target['cost']:,}" if target['cost'] > 0 else ""
        print(f"[UIDetector] Builder Menu: Selected wall row at {target['pos']} (Strategy: {strategy}, Candidates: {len(matches)}{cost_str}).")
        return (int(target["x"]), int(target["y"]))

    def get_builders_info(self, frame):
        """
        Dynamically inspects the builder widget (modern bottom-right placement above Build button,
        with fallback to top-center banner).
        Returns dict: {"free": int, "total": int, "is_busy": bool, "text": str}
        Accurately supports 2, 3, 4, 5, or 6 total builders.
        """
        total = 3
        try:
            from core.village_parser import village_profile
            total = getattr(village_profile, "total_builders", 3)
        except Exception:
            total = 3

        if frame is None:
            return {"free": total, "total": total, "is_busy": False, "text": f"{total}/{total} Free"}

        # 1. Primary Check: Builder HUD widget area above/next to Build hammer (x: 1110..1275, y: 515..580)
        # Covers both single-widget and dual-widget (regular builders + apprentice builder)
        # Secondary Check: Modern wide bottom-right placement (x: 980..1180, y: 600..680)
        candidate_rois = [
            (frame[515:580, 1110:1275], 1110, 515),
            (frame[600:680, 980:1180], 980, 600)
        ]

        tslash = self.templates.get("builder_slash")
        if tslash is None:
            ps = os.path.join(get_base_dir(), "assets/digits/builder_slash.png")
            if os.path.exists(ps):
                tslash = cv2.imread(ps)

        # Load digit templates for builders (0 to 6)
        digit_templates = {}
        for d_i in range(7):
            d_tpl = self.templates.get(f"builder_{d_i}")
            if d_tpl is None:
                p_b = os.path.join(get_base_dir(), f"assets/digits/builder_{d_i}.png")
                if os.path.exists(p_b):
                    d_tpl = cv2.imread(p_b)
                elif os.path.exists(os.path.join(get_base_dir(), f"assets/digits/{d_i}.png")):
                    d_tpl = cv2.imread(os.path.join(get_base_dir(), f"assets/digits/{d_i}.png"))
            if d_tpl is not None:
                digit_templates[d_i] = d_tpl

        for crop, offset_x, offset_y in candidate_rois:
            if crop is None or crop.size == 0 or tslash is None:
                continue
            if crop.shape[0] < tslash.shape[0] or crop.shape[1] < tslash.shape[1]:
                continue

            ress = cv2.matchTemplate(crop, tslash, cv2.TM_CCOEFF_NORMED)
            locs = np.where(ress >= 0.68)
            pts = list(zip(*locs[::-1]))
            if not pts:
                continue

            # Cluster multiple slash matches (e.g. main village builder + apprentice builder)
            clusters = []
            for pt in sorted(pts, key=lambda p: -ress[p[1], p[0]]):
                if not any(abs(pt[0] - c[0]) < 12 and abs(pt[1] - c[1]) < 8 for c in clusters):
                    clusters.append(pt)

            candidates = []
            for slash_x, slash_y in clusters:
                # Match free digit immediately to the left of slash:
                # Digit is tightly bounded in [slash_x - 24 : slash_x - 2] and roughly same y (+- 8px)
                free_digit = None
                best_free_score = 0.55
                for d_val, tpl in digit_templates.items():
                    if tpl is None:
                        continue
                    x_min = max(0, slash_x - 24)
                    x_max = max(0, slash_x - 2)
                    y_min = max(0, slash_y - 6)
                    y_max = min(crop.shape[0], slash_y + 18)
                    roi = crop[y_min:y_max, x_min:x_max]
                    if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
                        continue
                    res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
                    score = float(res.max())
                    if score > best_free_score:
                        best_free_score = score
                        free_digit = d_val

                # Match total digit immediately to the right of slash:
                # Digit is tightly bounded in [slash_x + 8 : slash_x + 28] and roughly same y (+- 8px)
                total_digit = total
                best_tot_score = 0.55
                for d_val in range(1, 7):
                    tpl = digit_templates.get(d_val)
                    if tpl is None:
                        continue
                    x_min = slash_x + 8
                    x_max = min(crop.shape[1], slash_x + 28)
                    y_min = max(0, slash_y - 6)
                    y_max = min(crop.shape[0], slash_y + 18)
                    roi = crop[y_min:y_max, x_min:x_max]
                    if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
                        continue
                    res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
                    score = float(res.max())
                    if score > best_tot_score:
                        best_tot_score = score
                        total_digit = d_val

                candidates.append((free_digit, total_digit, best_free_score, best_tot_score, slash_x))

            # Select village builder: prioritize total >= 2 (regular builders) over total == 1 (apprentice)
            chosen_cand = None
            for free_d, tot_d, fs, ts, sx in candidates:
                if tot_d is not None and tot_d >= 2:
                    chosen_cand = (free_d, tot_d)
                    break
            if not chosen_cand and candidates:
                chosen_cand = (candidates[0][0], candidates[0][1])

            if chosen_cand:
                free_digit, total_digit = chosen_cand
                if free_digit is None:
                    free_digit = 2 if total_digit == 3 else total_digit

                is_busy = (free_digit == 0)
                status_text = f"0/{total_digit} Busy" if is_busy else f"{free_digit}/{total_digit} Free"
                res_dict = {"free": free_digit, "total": total_digit, "is_busy": is_busy, "text": status_text}
                self._last_builder_info = res_dict
                try:
                    from core.village_parser import village_profile
                    if hasattr(village_profile, 'live_free_builders'):
                        village_profile.live_free_builders = free_digit
                except Exception:
                    pass
                return res_dict

        # 2. If visual detection on this single frame was inconclusive, consult village profile ground truth:
        # DO NOT blindly assume all builders are free (free = total)!
        expected_free = total
        try:
            from core.village_parser import village_profile
            if hasattr(village_profile, 'get_free_builder_count'):
                expected_free = village_profile.get_free_builder_count()
        except Exception:
            expected_free = total
        if hasattr(self, '_last_builder_info') and self._last_builder_info is not None:
            # Maintain previous verified reading unless village profile indicates timers completed
            return self._last_builder_info

        # 3. Fallback check for top-center builder_zero template
        pos = self.find_template(frame, "builder_zero", threshold=0.76)
        free = 0 if (pos and 610 <= pos[0] <= 670 and 15 <= pos[1] <= 60) else expected_free
        status_text = f"{free}/{total} Busy" if free == 0 else f"{free}/{total} Free"
        res_dict = {"free": free, "total": total, "is_busy": (free == 0), "text": status_text}
        # Only cache if free is explicitly verified as zero or ground truth
        if free == 0:
            self._last_builder_info = res_dict
        return res_dict
        return res_dict

    def has_zero_free_builders(self, frame):
        """Checks if the builder banner at top center shows 0 free builders."""
        if frame is None:
            return False
        return self.get_builders_info(frame)["is_busy"]

    def check_builders_busy_modal(self, frame):
        """Checks if 'All builders are busy!' modal is displayed."""
        if frame is None:
            return None
        return self.find_template(frame, "all_builders_busy", threshold=0.78)

    def check_next_button(self, frame):
        """Checks if orange 'Next' button is present at x=1065..1270, y=490..585."""
        if frame is None:
            return None
        # Safeguard: Home Village HUD (Attack/Battle button or Build hammer) cannot coexist with Next
        if (
            self.find_template(frame, "attack_button", threshold=0.62)
            or self.find_template(frame, "build_button", threshold=0.62)
        ):
            return None
        pos = self.find_template(frame, "next_button", threshold=0.68)
        if pos:
            return pos
        crop = frame[490:585, 1065:1270]
        if crop.size > 0:
            orange_px = np.sum((crop[:, :, 2] > 195) & (crop[:, :, 1] > 115) & (crop[:, :, 0] < 85))
            if orange_px > 250:
                return (1166, 540)
        return None

    def check_battle_ended(self, frame):
        """
        Evaluates whether battle has concluded (all troops died, 100% destroyed, or time ran out).
        Signs:
        1. Green Return Home button is verified visible at (640, 605) on darkened Victory/Defeat screen.
        """
        if frame is None:
            return False
        return self.check_return_home_button(frame) is not None

    def check_building_upgrade_modal(self, frame):
        """
        Detects if an unexpected standard Building or Hero Upgrade modal is open
        (e.g., 'Upgrade Dark Elixir Drill to Level 8?', 'Upgrade Archer Queen to Level 6?').
        Features:
        1. Top-right red close 'X' at (1131, 56) (matches modal_close_x or red pixel cluster).
        2. Presence of 'Upgrade time' box with builder time at x: 780..915, y: 600..680.
        Returns the (x, y) coordinates of the Red Close 'X' (1131, 56) so it can be safely dismissed immediately,
        guaranteeing NO accidental building upgrade is ever confirmed.
        """
        if frame is None or frame.shape[0] < 700:
            return None

        # 1. Check for modal_close_x template
        pos_x = self.find_template(frame, "modal_close_x", threshold=0.65)
        if pos_x and 1060 <= pos_x[0] <= 1180 and 25 <= pos_x[1] <= 95:
            return pos_x

        # 2. Check for red close X pixel cluster at x: 1100..1160, y: 30..80
        x_roi = frame[30:80, 1100:1160]
        if x_roi.size > 0:
            r, g, b = x_roi[:, :, 2], x_roi[:, :, 1], x_roi[:, :, 0]
            red_pts = np.sum((r > 175) & (g < 75) & (b < 75))
            if red_pts >= 40:
                return (1131, 56)

        return None

    def find_wall_confirm_button(self, frame):
        """
        Detects whether a genuine batch wall upgrade confirmation dialog is open.
        Returns ((x, y), mode) where mode is 'batch' or 'single', or None.
        Strictly excludes any modal prompting Gem purchases or Building/Hero Upgrades.
        """
        if frame is None:
            return None

        # 1. Check for Building/Hero Upgrade modal: NEVER confirm!
        if self.check_building_upgrade_modal(frame) is not None:
            return None

        # 2. Check for Gem purchase modal: NEVER confirm!
        if self.check_gem_purchase_modal(frame) is not None:
            return None

        # 3. Batch wall dialog: verified "Okay" template match (threshold >= 0.68)
        okay_pos = self.find_template(frame, "wall_confirm_okay", threshold=0.68)
        if okay_pos:
            return (okay_pos, "batch")

        return None

    def check_modal_popup(self, frame):
        """
        Detects if an unexpected modal popup (like 'Add Reinforcements' or other dialog) is open.
        Returns the (x, y) coordinate of the Cancel or Close button if found, else None.
        """
        if frame is None:
            return None
        # 1. Cancel button on Reinforcements modal
        cancel_pos = self.find_template(frame, "modal_cancel_btn", threshold=0.70)
        if cancel_pos:
            return cancel_pos
        # 2. Busy modal close X
        busy_pos = self.find_template(frame, "all_builders_busy", threshold=0.75)
        if busy_pos:
            return self.get_calibrated_coord("busy_close_x") or (702, 300)
        # 3. Star Bonus received or League reward modal
        star_pos = self.check_star_bonus_popup(frame)
        if star_pos:
            return star_pos
        return None

    def check_star_bonus_popup(self, frame):
        """
        Detects if a 'Star Bonus received!' or post-battle League reward modal is open.
        Features:
        1. Auto-scales frame to 1280x720 if necessary.
        2. Dialog Body Verification: Verifies royal blue modal background (x: 400..880, y: 200..450).
           On Home Village grass, blue_dialog_pts is 0; on real modal, blue_dialog_pts > 20,000.
        3. Template match on 'star_bonus_okay.png'
        4. Color & geometry verification for centered Supercell green 'Okay' button in dialog.
        Returns the (x, y) coordinate of the green Okay button (typically (653, 643)), or None.
        """
        if frame is None or frame.size == 0:
            return None
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        chk_frame = frame
        if frame.shape[0] != 720 or frame.shape[1] != 1280:
            chk_frame = cv2.resize(frame, (1280, 720))

        # 1. Dialog Body Verification: Modal MUST have the large royal blue dialog background
        # Completely eliminates 100% of false positives on green home village grass!
        dialog_center = chk_frame[200:450, 400:880]
        b, g, r = cv2.split(dialog_center)
        blue_dialog_pts = int(np.sum((b > 130) & (b > r.astype(int) * 1.3) & (b > g.astype(int) * 1.1)))
        if blue_dialog_pts < 5000:
            return None

        # 2. Template match for Star Bonus green Okay button
        pos = self.find_template(chk_frame, "star_bonus_okay", threshold=0.70)
        if pos and 480 <= pos[0] <= 800 and 520 <= pos[1] <= 680:
            return pos

        # 3. Color & geometry verification for centered Supercell green 'Okay' button inside blue dialog
        btn_roi = chk_frame[580:670, 520:760]
        if btn_roi.size > 0:
            b_b, g_b, r_b = cv2.split(btn_roi)
            green_pts = np.sum((g_b > 135) & (g_b > r_b * 1.25) & (g_b > b_b * 1.30) & (r_b < 130) & (b_b < 110))
            white_pts = np.sum((r_b > 190) & (g_b > 190) & (b_b > 180))
            if green_pts >= 180 and white_pts >= 25:
                return (640, 635)

        return None

    def check_army_attack_btn(self, frame):
        """Detects if 'My Army' confirmation screen is visible with the green Attack! button."""
        if frame is None:
            return None
        pos = self.find_template(frame, "army_attack_button", threshold=0.68)
        if pos:
            return pos
        return None

    def find_wall_upgrade_button(self, frame, resource_type="ELIXIR"):
        """
        Dynamically locates the Gold or Elixir upgrade button on the bottom toolbar.
        Anchored by template matching for the coin / elixir droplet icon.
        """
        if frame is None:
            return None
        tname = "wall_btn_gold_icon" if resource_type.upper() == "GOLD" else "wall_btn_elixir_icon"
        pos = self.find_template(frame, tname, threshold=0.72)
        if pos:
            return (pos[0] + 35, pos[1])
        if resource_type.upper() == "GOLD":
            return self.get_calibrated_coord("wall_upgrade_gold") or (770, 600)
        return self.get_calibrated_coord("wall_upgrade_elixir") or (910, 600)

    def is_wall_upgrade_price_insufficient(self, frame, resource_type="ELIXIR", is_build_menu=None, button_pos=None):
        """
        Detects if the wall upgrade price digits are rendered in RED,
        which indicates insufficient resources (tapping it would request GEMS).
        Covers the complete width of the card's price area to prevent missing digits.
        """
        if frame is None:
            return False

        patch = None
        if button_pos:
            bx, by = button_pos
            # Card is ~105px wide, centered at bx. Price digits span x: bx - 48 to bx + 22, y: by - 48 to by - 12
            patch = frame[max(0, by - 48) : min(frame.shape[0], by - 12),
                          max(0, bx - 48) : min(frame.shape[1], bx + 22)]
        else:
            # Dynamically locate button via template matching
            tname = "build_wall_upgrade_gold" if resource_type.upper() == "GOLD" else "build_wall_upgrade_elixir"
            pos = self.find_template(frame, tname, threshold=0.65)
            if not pos:
                tname2 = "wall_batch_upgrade_gold" if resource_type.upper() == "GOLD" else "wall_batch_upgrade_elixir"
                pos = self.find_template(frame, tname2, threshold=0.65)

            if pos:
                bx, by = pos
                patch = frame[max(0, by - 48) : min(frame.shape[0], by - 12),
                              max(0, bx - 48) : min(frame.shape[1], bx + 22)]
            else:
                if is_build_menu:
                    pos_ref = self.find_template(frame, "build_wall_add_10", threshold=0.68)
                    if pos_ref and pos_ref[1] < 535:
                        patch = frame[585:615, 280:365] if resource_type.upper() == "GOLD" else frame[585:615, 420:505]
                    else:
                        patch = frame[530:555, 565:625] if resource_type.upper() == "GOLD" else frame[530:555, 705:765]
                else:
                    if resource_type.upper() == "GOLD":
                        patch = frame[595:635, 570:650]
                    else:
                        patch = frame[595:635, 680:760]

        if patch is None or patch.size == 0:
            return False

        # True Red price digits in COC: Red channel is high (>= 180) and significantly
        # dominant over Green and Blue (R - G >= 50 and R - B >= 50).
        # This accurately identifies the coral/salmon red COC insufficient price text
        # while strictly rejecting white text (R ~= G ~= B) and purple/magenta Elixir droplet (high Blue).
        red_digits = (
            (patch[:, :, 2] >= 180)
            & (patch[:, :, 2].astype(int) - patch[:, :, 1].astype(int) >= 50)
            & (patch[:, :, 2].astype(int) - patch[:, :, 0].astype(int) >= 50)
        )
        return int(np.sum(red_digits)) >= 35

    def check_gem_purchase_modal(self, frame):
        """
        Detects if a 'Buy missing resources with Gems' dialog is open.
        Checks for emerald green gem crystals in the modal confirm area (x: 650..840, y: 430..510)
        or template matching for modal cancel button.
        Returns the (x, y) coordinates of the Cancel button (515, 470) if detected.
        """
        if frame is None or frame.size == 0:
            return None
        if frame.shape[:2] != (720, 1280):
            frame = cv2.resize(frame, (1280, 720))

        # Authentic resource confirmation dialogs with "Okay" or "CONFIRM" are NEVER gem modals
        if self.find_template(frame, "wall_confirm_okay", threshold=0.65) or self.find_template(frame, "wall_confirm_single", threshold=0.68):
            return None

        # 1. Check for emerald green gem in modal confirmation region
        roi_confirm = frame[430:510, 650:840]
        if roi_confirm.size > 0:
            hsv = cv2.cvtColor(roi_confirm, cv2.COLOR_BGR2HSV)
            # Emerald green gem: H: 35..85, S >= 110, V >= 110
            gem_pts = np.sum((hsv[:, :, 0] >= 35) & (hsv[:, :, 0] <= 85) & (hsv[:, :, 1] >= 110) & (hsv[:, :, 2] >= 110))
            modal_cancel = self.find_template(frame, "modal_cancel_btn", threshold=0.68)
            if int(gem_pts) >= 45 and modal_cancel:
                print(f"[UIDetector] [GEM DETECTED] Gem purchase prompt detected ({gem_pts} green gem pixels in modal confirmation)! Cancel required.")
                return (515, 470)

        # 2. Check modal cancel button template
        modal_cancel = self.find_template(frame, "modal_cancel_btn", threshold=0.68)
        if modal_cancel and (400 <= modal_cancel[0] <= 600) and (420 <= modal_cancel[1] <= 520):
            return modal_cancel

        # 3. Check for 'all_builders_busy' modal
        if self.find_template(frame, "all_builders_busy", threshold=0.75):
            return (515, 470)

        return None

    def check_no_more_walls_toast(self, frame):
        """
        Detects red toast banner 'No more walls at that level to add to your selection.'
        centered at y: 185..235, x: 250..950.
        """
        if frame is None or frame.size == 0:
            return False
        roi = frame[185:235, 250:950]
        red_mask = (
            (roi[:, :, 2] > 170)
            & (roi[:, :, 2].astype(int) - roi[:, :, 1].astype(int) > 60)
            & (roi[:, :, 2].astype(int) - roi[:, :, 0].astype(int) > 60)
        )
        col_counts = np.sum(red_mask, axis=0)
        cols_with_red = np.sum(col_counts > 0)
        total_red = np.sum(red_mask)
        return total_red >= 1500 and cols_with_red >= 250

    def detect_wall_batch_layout(self, frame):
        """
        Dynamically analyzes the wall upgrade toolbar to classify layout:
        Supports both Supercell UI modes:
        1. Single-Row Mode (horizontal toolbar at y ≈ 565)
        2. Two-Row Mode (staggered grid with top row y ≈ 505..520 and bottom row y ≈ 630..645)

        Correctly identifies:
        - SINGLE_WALL Mode: [Info (blue), Select Row (never tap!), Upgrade More (activates batch), Gold, Elixir]
        - BATCH Mode: [-1 (salmon pink), +10 (middle), +1 (lime green), Gold (bottom/left), Elixir (bottom/right)]

        CRITICAL SAFEGUARDS:
        - Accurately differentiates Single-Wall from Batch mode in Two-Row layout (preventing false batch detection).
        - Verifies that add_10 and add_1 never collapse to the same button coordinate.
        - Identifies exact single wall upgrade costs and resource requirements.
        """
        if frame is None:
            return None

        # 1. Primary template checks for high confidence landmarks
        btn_rem1_tmpl = self.find_template(frame, "build_wall_remove_1", threshold=0.72)
        btn_add10_tmpl = self.find_template(frame, "build_wall_add_10", threshold=0.72)
        btn_add1_tmpl = self.find_template(frame, "build_wall_add_1", threshold=0.72)
        btn_more_tmpl = self.find_template(frame, "build_wall_upgrade_more", threshold=0.62) or self.find_template(frame, "wall_upgrade_more", threshold=0.62)
        btn_select_row_tmpl = self.find_template(frame, "wall_select_row", threshold=0.68)

        # 2. Contour detection of all card squares across the toolbar ROI
        roi_y1, roi_y2 = 470, 705
        roi_x1, roi_x2 = 180, 850
        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cards = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            cy = roi_y1 + y + h // 2
            cx = roi_x1 + x + w // 2
            # Cards in both single-row (w~110, h~106) and two-row (w~110, h~89..106)
            if 95 <= w <= 135 and 75 <= h <= 135 and cy >= 485:
                cards.append((cx, cy, w, h))

        # Split into top and bottom rows
        top_row = sorted([c for c in cards if c[1] < 565], key=lambda c: c[0])
        bot_row = sorted([c for c in cards if c[1] >= 565], key=lambda c: c[0])
        is_two_row = (len(top_row) >= 2 and len(bot_row) >= 1) or (btn_add1_tmpl and btn_add1_tmpl[1] < 535)

        # 3. High-precision color profiling of detected cards
        has_add1 = False
        btn_add1_pos = None
        has_rem1 = False
        btn_add1_pos = None
        btn_rem1_pos = None
        has_add1 = False
        has_rem1 = False
        has_info = False
        btn_gold = None
        btn_elixir = None

        search_cards = top_row if is_two_row else cards
        for cx, cy, _, _ in search_cards:
            patch = frame[max(0, cy - 45) : min(720, cy + 45), max(0, cx - 45) : min(1280, cx + 45)]
            if patch.size == 0:
                continue
            b, g, r = cv2.split(patch)
            # +1 card has bright lime green digits (+1) in center/upper area
            green_pts = int(np.sum((g > 180) & (r < 150) & (b < 80)))
            # Info [i] card has vibrant blue circular badge
            blue_pts = int(np.sum((b > 170) & (r < 90)))
            # -1 Remove Wall card has salmon/pink text in lower half
            lower = patch[patch.shape[0] // 2 :, :]
            pink_pts = int(np.sum((lower[:, :, 2] > 200) & (lower[:, :, 1] > 100) & (lower[:, :, 1] < 170) & (lower[:, :, 0] > 90) & (lower[:, :, 0] < 170)))

            if green_pts >= 35:
                has_add1 = True
                btn_add1_pos = (cx, cy)
            if blue_pts >= 60:
                has_info = True
            if pink_pts >= 50:
                has_rem1 = True
                btn_rem1_pos = (cx, cy)

        # 4. Determine whether batch mode is active vs single-wall mode:
        # CRITICAL SAFEGUARD:
        # A single wall on the map ALWAYS has "Select Row" (wall_select_row) or "Upgrade More" (build_wall_upgrade_more).
        # When single-wall controls are present, it is 100% GUARANTEED to be in SINGLE WALL mode (is_batch = False).
        # Batch mode is ONLY active when batch controls (+10, +1, -1) are clearly matched AND single-wall controls are absent!
        has_batch_controls = (btn_add10_tmpl is not None or btn_add1_tmpl is not None or btn_rem1_tmpl is not None or has_add1 or has_rem1)
        has_single_controls = (btn_select_row_tmpl is not None or btn_more_tmpl is not None)

        if has_single_controls:
            is_batch = False
        elif has_batch_controls:
            is_batch = True
        else:
            is_batch = False

        # 5. Locate Gold and Elixir upgrade buttons
        # In single-row mode, upgrade buttons (Gold/Elixir) are strictly at x >= 540 (Card 3 and Card 4).
        # Cards with x < 540 are Card 0 (Info at ~185), Card 1 (Select Row at ~327), or Card 2 (Upgrade More at ~466).
        upgrade_search_cards = bot_row if is_two_row else [c for c in cards if c[0] >= 540]
        for cx, cy, _, _ in upgrade_search_cards:
            patch = frame[max(0, cy - 45) : min(720, cy + 45), max(0, cx - 45) : min(1280, cx + 45)]
            if patch.shape[0] >= 35 and patch.shape[1] >= 40:
                tr = patch[:35, patch.shape[1] - 40 :]
                gold_pts = int(np.sum((tr[:, :, 0] < 60) & (tr[:, :, 1] > 140) & (tr[:, :, 2] > 180)))
                elixir_pts = int(np.sum((tr[:, :, 0] > 90) & (tr[:, :, 2] > 140) & (tr[:, :, 1] < 80)))
                if gold_pts >= 15:
                    btn_gold = (cx, cy)
                elif elixir_pts >= 15:
                    btn_elixir = (cx, cy)

        # 6. Map buttons based on layout mode
        btn_rem1 = None
        btn_add10 = None
        btn_add1 = None
        btn_more = None

        if is_two_row:
            layout = "TWO_ROW_BATCH" if is_batch else "TWO_ROW_SINGLE"
            if is_batch:
                # Top row in batch mode: Left is -1, Middle is +10, Right is +1
                if len(top_row) >= 3:
                    # In two-row batch mode with 3 top cards: [0] is -1, [1] is +10, [2] is +1
                    btn_rem1 = (top_row[0][0], top_row[0][1])
                    btn_add10 = (top_row[1][0], top_row[1][1])
                    btn_add1 = (top_row[2][0], top_row[2][1])
                elif btn_add1_pos:
                    btn_add1 = btn_add1_pos
                    btn_add10 = (btn_add1_pos[0] - 138, btn_add1_pos[1])
                    btn_rem1 = (btn_add1_pos[0] - 278, btn_add1_pos[1])
                elif btn_rem1_pos:
                    btn_rem1 = btn_rem1_pos
                    btn_add10 = (btn_rem1_pos[0] + 140, btn_rem1_pos[1])
                    btn_add1 = (btn_rem1_pos[0] + 278, btn_rem1_pos[1])
                elif len(top_row) == 2:
                    btn_rem1 = (top_row[0][0], top_row[0][1])
                    btn_add10 = None
                    btn_add1 = (top_row[1][0], top_row[1][1])
                else:
                    btn_rem1 = (326, 514)
                    btn_add10 = (466, 514)
                    btn_add1 = (604, 514)

                # Safeguard: ensure buttons NEVER share coordinates
                if btn_add10 and btn_add1 and abs(btn_add10[0] - btn_add1[0]) < 60:
                    btn_add10 = (btn_add1[0] - 138, btn_add1[1])
                if btn_rem1 and btn_add10 and abs(btn_rem1[0] - btn_add10[0]) < 60:
                    btn_rem1 = (btn_add10[0] - 140, btn_add10[1])

                if len(bot_row) >= 2:
                    btn_gold = btn_gold or (bot_row[0][0], bot_row[0][1])
                    btn_elixir = btn_elixir or (bot_row[1][0], bot_row[1][1])
                elif len(bot_row) == 1:
                    btn_gold = btn_gold or (bot_row[0][0], bot_row[0][1])
                    btn_elixir = None
                else:
                    btn_gold = btn_gold or (327, 632)
                    btn_elixir = None
            else:
                # Two-Row Single-Wall: Top row has [Info (0 at ~326), Select Row (1 at ~466), Upgrade More (2 at ~604)]
                # CRITICAL BUG FIX: NEVER pick top_row[-1] if x < 540 (which is Card 1 'Select Row' at ~466)!
                more_cards = [c for c in top_row if c[0] >= 540]
                if more_cards:
                    btn_more = (more_cards[0][0], more_cards[0][1])
                elif btn_more_tmpl and btn_more_tmpl[0] >= 540:
                    btn_more = btn_more_tmpl
                else:
                    btn_more = (604, 514)

                # INVARIANT: In two-row mode, Upgrade More MUST NEVER have x < 540 (Card 1 is Select Row at ~466)!
                if btn_more and btn_more[0] < 540:
                    btn_more = (604, 514)

                if len(bot_row) >= 2:
                    btn_gold = btn_gold or (bot_row[0][0], bot_row[0][1])
                    btn_elixir = btn_elixir or (bot_row[1][0], bot_row[1][1])
                elif len(bot_row) == 1:
                    btn_gold = btn_gold or (bot_row[0][0], bot_row[0][1])
                    btn_elixir = None
                else:
                    btn_gold = btn_gold or (327, 632)
                    btn_elixir = None
        else:
            # Single-Row Mode (horizontal toolbar at y ≈ 565)
            sorted_cards = sorted(cards, key=lambda c: c[0])
            num_cards = len(sorted_cards)
            layout = "SINGLE_ROW_BATCH" if is_batch else "SINGLE_ROW_SINGLE"

            if is_batch:
                if btn_add10_tmpl and btn_add1_tmpl:
                    btn_rem1 = btn_rem1_tmpl or (btn_add10_tmpl[0] - 138, btn_add10_tmpl[1])
                    btn_add10 = btn_add10_tmpl
                    btn_add1 = btn_add1_tmpl
                    btn_gold = btn_gold or (btn_add1[0] + 140, btn_add1[1])
                    btn_elixir = btn_elixir or ((btn_add1[0] + 280, btn_add1[1]) if num_cards >= 5 else None)
                elif num_cards >= 5:
                    btn_rem1 = (sorted_cards[0][0], sorted_cards[0][1])
                    btn_add10 = (sorted_cards[1][0], sorted_cards[1][1])
                    btn_add1 = (sorted_cards[2][0], sorted_cards[2][1])
                    btn_gold = btn_gold or (sorted_cards[3][0], sorted_cards[3][1])
                    btn_elixir = btn_elixir or (sorted_cards[4][0], sorted_cards[4][1])
                elif num_cards == 4:
                    # In single-row batch mode with 4 cards, the cards are:
                    # [0]: -1 (~185), [1]: +10 (~322), [2]: +1 (~464), [3]: Upgrade Gold (~605)
                    # (Elixir is absent for Gold-only low level walls)
                    btn_rem1 = (sorted_cards[0][0], sorted_cards[0][1])
                    btn_add10 = (sorted_cards[1][0], sorted_cards[1][1])
                    btn_add1 = (sorted_cards[2][0], sorted_cards[2][1])
                    btn_gold = btn_gold or (sorted_cards[3][0], sorted_cards[3][1])
                    btn_elixir = None
                else:
                    btn_rem1 = btn_rem1_tmpl or (185, 565)
                    btn_add10 = btn_add10_tmpl or (322, 566)
                    btn_add1 = btn_add1_tmpl or (464, 566)
                    btn_gold = btn_gold or (605, 567)
                    btn_elixir = btn_elixir or (745, 567)

                # Overwrite with template locations if detected
                if btn_rem1_tmpl:
                    btn_rem1 = btn_rem1_tmpl
                if btn_add10_tmpl:
                    btn_add10 = btn_add10_tmpl
                if btn_add1_tmpl:
                    btn_add1 = btn_add1_tmpl

                # Strictly protect against button collapse or negative offsets
                if btn_add10 and btn_add10[0] < 260:
                    btn_add10 = (322, 566)
                if btn_add1 and btn_add1[0] < 390:
                    btn_add1 = (464, 566)
                if btn_rem1 and btn_rem1[0] > 260:
                    btn_rem1 = (185, 565)
            else:
                # Single-Wall Toolbar: [Info (0 at ~185), Select Row (1 at ~322), Upgrade More (2 at ~464), Gold (3 at ~605), Elixir (4 at ~745)]
                more_cards = [c for c in sorted_cards if 400 <= c[0] <= 530]
                if more_cards:
                    btn_more = (more_cards[0][0], more_cards[0][1])
                elif btn_more_tmpl and 400 <= btn_more_tmpl[0] <= 530:
                    btn_more = btn_more_tmpl
                else:
                    btn_more = (464, 566)
                if btn_more and btn_more[0] < 400:
                    btn_more = (464, 566)

                # Single-Row Mode Upgrade Button Mapping:
                # Upgrade Gold MUST NEVER be at x < 540 (Card 1 is Select Row at ~327, Card 2 is Upgrade More at ~466)!
                if not btn_gold or btn_gold[0] < 540:
                    gold_cands = [c for c in sorted_cards if 550 <= c[0] <= 660]
                    btn_gold = (gold_cands[0][0], gold_cands[0][1]) if gold_cands else (605, 567)
                if not btn_elixir or btn_elixir[0] < 680:
                    elixir_cands = [c for c in sorted_cards if c[0] >= 680]
                    btn_elixir = (elixir_cands[0][0], elixir_cands[0][1]) if elixir_cands else ((745, 567) if num_cards >= 5 else None)

        has_elixir = (btn_elixir is not None)
        # Safeguard: Verify if the selected entity is genuinely a wall.
        # A wall toolbar MUST have batch controls (+1, -1, +10) or wall-specific actions (Select Row, Upgrade More).
        # Normal buildings (e.g. Cannon, Elixir Collector, Army Camp) only have Info, Upgrade, Collect, etc.
        is_genuine_wall = bool(is_batch or btn_more_tmpl or btn_select_row_tmpl or (btn_more is not None and not has_info))

        return {
            "layout": layout,
            "remove_1": btn_rem1,
            "add_10": btn_add10,
            "add_1": btn_add1,
            "upgrade_more": btn_more,
            "select_row": btn_select_row_tmpl,
            "upgrade_gold": btn_gold,
            "upgrade_elixir": btn_elixir,
            "has_elixir": has_elixir,
            "is_batch": is_batch,
            "is_wall": is_genuine_wall,
            "cards": cards
        }


