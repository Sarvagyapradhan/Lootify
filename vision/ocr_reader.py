"""
High-Speed Pure OpenCV OCR & Digit Engine for Clash of Clans.
Uses pre-calibrated digit template matching (<5ms execution time, zero external heavy dependencies).
Accurately reads:
1. Village Storages (Gold, Elixir, Dark Elixir) in Home Base.
2. Available Raid Loot (Gold, Elixir, Dark Elixir) during Matchmaking Attacks.
"""

import os
import sys
import cv2
import numpy as np


def get_base_dir():
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(exe_dir, "assets")):
            return exe_dir
        return getattr(sys, "_MEIPASS", exe_dir)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LootOCRReader:
    def __init__(self, digits_dir="assets/digits"):
        self.digits_dir = digits_dir
        self.digits = {}
        self._load_digit_templates()

    def _load_digit_templates(self):
        """Loads Supercell font templates (0-9) from assets/digits/."""
        target_dir = os.path.join(get_base_dir(), self.digits_dir)
        if not os.path.exists(target_dir):
            target_dir = self.digits_dir
        if not os.path.exists(target_dir):
            return

        self.digits = {str(i): [] for i in range(10)}
        for fname in os.listdir(target_dir):
            if fname.lower().endswith(".png"):
                char = fname[0]
                if char.isdigit():
                    p = os.path.join(target_dir, fname)
                    tmpl = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
                    if tmpl is not None:
                        self.digits[char].append(tmpl)

    def parse_digits_from_crop(self, bgr_crop, is_raid=False):
        """
        Extracts integer value from a cropped resource bar using digit template matching.
        """
        if bgr_crop is None or bgr_crop.size == 0 or not self.digits:
            return 0

        if is_raid:
            # Raid loot digits are bright cream/white on grass background
            b, g, r = cv2.split(bgr_crop)
            mask = (r > 190) & (g > 180) & (b > 140)
            thresh = (mask * 255).astype(np.uint8)
        else:
            # Exclude right-hand resource icon when checking text color
            d_area = bgr_crop[:, :-25] if bgr_crop.shape[1] > 35 else bgr_crop
            b_d, g_d, r_d = cv2.split(d_area)
            red_pts = np.sum((r_d > 185) & (g_d < 105) & (b_d < 105))

            if red_pts >= 40:
                # Text is RED (occurs when storages are full in Clash of Clans)
                b, g, r = cv2.split(bgr_crop)
                red_mask = (r > 175) & (g < 115) & (b < 115)
                thresh = (red_mask * 255).astype(np.uint8)
            else:
                # White text mask: Clash of Clans storage numbers are crisp white (R,G,B > 185)
                # This cleanly separates the white numbers from yellow gold (B<100) and purple elixir (G<120) fill bars!
                b, g, r = cv2.split(bgr_crop)
                white_mask = (r > 185) & (g > 185) & (b > 165)
                thresh = (white_mask * 255).astype(np.uint8)
                if np.sum(thresh) < 50:
                    gray = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in contours]

        # Ignore icon at far right edge of the bar
        max_x = bgr_crop.shape[1] - (8 if not is_raid else 12)
        valid_boxes = sorted([b for b in boxes if 9 <= b[3] <= 24 and 3 <= b[2] <= 22 and b[0] < max_x], key=lambda b: b[0])

        if not valid_boxes and not is_raid:
            gray = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 195, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            boxes = [cv2.boundingRect(c) for c in contours]
            valid_boxes = sorted([b for b in boxes if 9 <= b[3] <= 24 and 3 <= b[2] <= 22 and b[0] < max_x], key=lambda b: b[0])

        # Vertical alignment filter: reject stray glints that don't align with the digit baseline
        if len(valid_boxes) >= 2:
            med_y = np.median([b[1] + b[3] / 2.0 for b in valid_boxes])
            valid_boxes = [b for b in valid_boxes if abs((b[1] + b[3] / 2.0) - med_y) <= 6.0]

        # Horizontal spacing filter: discard isolated artifact noise far to the left of the main number cluster
        while len(valid_boxes) >= 2:
            gap = valid_boxes[1][0] - (valid_boxes[0][0] + valid_boxes[0][2])
            if gap > 22:
                valid_boxes.pop(0)
            else:
                break

        recognized = []
        for (x, y, w, h) in valid_boxes:
            char_crop = thresh[y:y+h, x:x+w]
            best_digit, best_score = None, -1
            for d_char, tmpls in self.digits.items():
                if d_char == "1" and w >= 9:
                    continue
                if d_char in ["0", "4", "8", "9"] and w <= 7:
                    continue
                for d_tmpl in tmpls:
                    th, tw = d_tmpl.shape
                    rz = cv2.resize(d_tmpl, (max(1, int(tw * h / th)), h))
                    ch = cv2.resize(char_crop, (rz.shape[1], h)) if char_crop.shape[1] < rz.shape[1] else char_crop
                    res = cv2.matchTemplate(ch, rz, cv2.TM_CCOEFF_NORMED)
                    score = cv2.minMaxLoc(res)[1]
                    if score > best_score:
                        best_score, best_digit = score, d_char
            if best_digit and best_score >= 0.45:
                recognized.append(best_digit)

        return int("".join(recognized)) if recognized else 0

    def parse_wall_cost_from_crop(self, bgr_crop):
        """
        Specialized OCR for wall upgrade costs in the Builder Recommendations drawer.
        Accounts for:
        1. Wide digit spread with spaces (e.g., '1 000 000', '500 000').
        2. Connected / touching zeros (splitting boxes with w >= 16).
        3. Strict mapping to standard Clash of Clans wall upgrade tiers.
        """
        if bgr_crop is None or bgr_crop.size == 0 or not self.digits:
            return 0

        b, g, r = cv2.split(bgr_crop)
        white_mask = (r > 185) & (g > 185) & (b > 165)
        thresh = (white_mask * 255).astype(np.uint8)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in contours]
        raw_boxes = [b for b in boxes if 8 <= b[3] <= 26 and 3 <= b[2] <= 32]

        split_boxes = []
        for (x, y, w, h) in raw_boxes:
            if w >= 16:
                w1 = w // 2
                split_boxes.append((x, y, w1, h))
                split_boxes.append((x + w1, y, w - w1, h))
            else:
                split_boxes.append((x, y, w, h))

        split_boxes = sorted(split_boxes, key=lambda b: b[0])
        recognized = []
        for (x, y, w, h) in split_boxes:
            char_crop = thresh[y:y+h, x:x+w]
            best_digit, best_score = None, -1
            for d_char, tmpls in self.digits.items():
                for d_tmpl in tmpls:
                    th, tw = d_tmpl.shape
                    rz = cv2.resize(d_tmpl, (max(1, int(tw * h / th)), h))
                    ch = cv2.resize(char_crop, (rz.shape[1], h)) if char_crop.shape[1] < rz.shape[1] else char_crop
                    res = cv2.matchTemplate(ch, rz, cv2.TM_CCOEFF_NORMED)
                    score = cv2.minMaxLoc(res)[1]
                    if score > best_score:
                        best_score, best_digit = score, d_char
            if best_digit and best_score >= 0.45:
                recognized.append(best_digit)

        if not recognized:
            return 0

        digits_str = "".join(recognized)
        n_digits = len(digits_str)
        first_char = digits_str[0]

        try:
            val = int(digits_str)
        except Exception:
            val = 0

        valid_tiers = [
            200, 1000, 5000, 10000, 20000, 50000, 75000,
            100000, 200000, 300000, 500000, 800000,
            1000000, 2000000, 3000000, 4000000, 5000000, 7000000, 9000000
        ]
        for tier in valid_tiers:
            if abs(val - tier) <= max(200, tier * 0.15):
                return tier

        # Disambiguation by digit count & leading digit
        tier_maps = {
            7: {'1': 1000000, '2': 2000000, '3': 3000000, '4': 4000000, '5': 5000000, '7': 7000000, '9': 9000000},
            6: {'5': 500000, '3': 300000, '2': 200000, '1': 100000, '8': 800000},
            5: {'5': 50000, '2': 20000, '1': 10000, '7': 75000},
            4: {'5': 5000, '1': 1000},
        }
        if n_digits >= 7:
            return tier_maps[7].get(first_char, 1000000)
        elif n_digits == 6:
            return tier_maps[6].get(first_char, 500000)
        elif n_digits == 5:
            return tier_maps[5].get(first_char, 10000)
        elif n_digits == 4:
            return tier_maps[4].get(first_char, 5000)
        elif n_digits <= 3:
            return 200

        return val

    def parse_card_count(self, top_badge_crop):
        """
        Parses small troop count badge from top of a unit tray card (e.g. 'x15' -> 15).
        """
        if top_badge_crop is None or top_badge_crop.size == 0 or not self.digits:
            return 0
        b, g, r = cv2.split(top_badge_crop)
        # White text mask on dark badge background
        mask = (r > 165) & (g > 165) & (b > 130)
        thresh = (mask * 255).astype(np.uint8)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in contours]
        # In Clash of Clans, the count badge (e.g. 'x10') is located on the right side of the card header (x >= 35)
        # Digit boxes are small: height 9 to 20, width 4 to 18
        valid = sorted([bx for bx in boxes if 9 <= bx[3] <= 20 and 4 <= bx[2] <= 18 and bx[0] >= 35], key=lambda b: b[0])

        recognized = []
        for (x, y, w, h) in valid:
            char_crop = thresh[y:y+h, x:x+w]
            best_digit, best_score = None, -1
            for d_char, tmpls in self.digits.items():
                if d_char == "1" and (w >= 7 or (w / float(h)) > 0.55):
                    continue
                if d_char in ["0", "4", "8", "9"] and w <= 5:
                    continue
                for d_tmpl in tmpls:
                    th, tw = d_tmpl.shape
                    rz = cv2.resize(d_tmpl, (max(1, int(tw * h / th)), h))
                    ch = cv2.resize(char_crop, (rz.shape[1], h)) if char_crop.shape[1] < rz.shape[1] else char_crop
                    res = cv2.matchTemplate(ch, rz, cv2.TM_CCOEFF_NORMED)
                    score = cv2.minMaxLoc(res)[1]
                    if score > best_score:
                        best_score, best_digit = score, d_char
            th_score = 0.39 if best_digit == "1" else 0.44
            if best_digit and best_score >= th_score:
                recognized.append(best_digit)
        if recognized:
            try:
                return int("".join(recognized))
            except Exception:
                pass
        return 0

    def detect_screen(self, frame_1280x720):
        """
        Comprehensive global screen classifier.
        Accurately identifies:
        - HOME_VILLAGE (Base with Attack button)
        - ATTACK_MENU (Multiplayer match selection with Find a Match button)
        - MY_ARMY_WINDOW (Army overview with green Attack! button)
        - MODAL_POPUP (Add Reinforcements, Builders busy, or any dialog with Cancel/X)
        - MATCHMAKING (In-battle raid with Next or Surrender button)
        - BATTLE_RESULTS (Victory/Defeat screen with Return Home button)
        - DISCONNECTED (Reload game modal)
        - UNKNOWN (Fallback for non-standard transitions)
        """
        if frame_1280x720 is None:
            return "UNKNOWN"

        def _check_tmpl(name, thresh=0.70):
            p = os.path.join(get_base_dir(), f"assets/templates/{name}.png")
            if not os.path.exists(p):
                p = f"assets/templates/{name}.png"
            if os.path.exists(p):
                tmpl = cv2.imread(p)
                if tmpl is not None:
                    res = cv2.matchTemplate(frame_1280x720, tmpl, cv2.TM_CCOEFF_NORMED)
                    return cv2.minMaxLoc(res)[1] >= thresh
            return False

        # 1. Check for reload game / disconnect dialog
        if _check_tmpl("reload_game", 0.72):
            return "DISCONNECTED"

        # 2. Check for Home Village HUD buttons (Build hammer or Attack sword button)
        has_home_hud = (
            _check_tmpl("build_button", 0.60)
            or _check_tmpl("attack_button", 0.50)
            or _check_tmpl("battle_button", 0.50)
            or _check_tmpl("shop_button", 0.65)
        )
        if has_home_hud:
            return "HOME_VILLAGE"

        # 3. Check for My Army Confirmation screen (green Attack! button)
        if _check_tmpl("army_attack_button", 0.72):
            return "MY_ARMY_WINDOW"

        # 4. Check for Find Match Attack selection menu
        if _check_tmpl("find_match_button", 0.70):
            return "ATTACK_MENU"

        # 5. Check for Battle Matchmaking (Next button visible)
        if _check_tmpl("next_button", 0.65):
            return "MATCHMAKING"

        # 6. Check for Battle Raid Combat (End Battle / Surrender button visible)
        if _check_tmpl("end_battle_button", 0.65) or _check_tmpl("surrender_button", 0.65):
            return "ATTACKING"
        end_crop = frame_1280x720[550:625, 15:150]
        if end_crop.size > 0:
            b, g, r = cv2.split(end_crop)
            red_end = np.sum((r > 160) & (g < 75) & (b < 75))
            white_end = np.sum((r > 185) & (g > 185) & (b > 180))
            if red_end > 300 and white_end >= 25:
                return "ATTACKING"

        # 7. Check for Modal Popups (e.g. Add Reinforcements modal or Builders busy)
        if _check_tmpl("modal_cancel_btn", 0.72) or _check_tmpl("all_builders_busy", 0.82):
            return "MODAL_POPUP"

        # 8. Check for Battle Results / Return Home (ONLY after all active gameplay screens are ruled out!)
        top_left_brightness = np.mean(frame_1280x720[15:65, 15:65])
        if top_left_brightness < 75:  # Battle Results screen is darkened by vignette overlay
            crop_rh = frame_1280x720[575:640, 540:740]
            if crop_rh.size > 0:
                b, g, r = cv2.split(crop_rh)
                green_pts = np.sum((g > 135) & (g > r * 1.30) & (g > b * 1.40) & (r < 115) & (b < 95))
                white_pts = np.sum((r > 195) & (g > 195) & (b > 180))
                if (green_pts >= 250 and white_pts >= 35) or _check_tmpl("return_home_button", 0.70):
                    return "BATTLE_RESULTS"

        # 9. Fallback for Home Village via storages
        try:
            st = self.read_village_storages(frame_1280x720)
            if st.get("gold", 0) > 0 or st.get("elixir", 0) > 0:
                return "HOME_VILLAGE"
        except Exception:
            pass

        return "UNKNOWN"

    def is_crop_red(self, bgr_crop):
        """Checks if text inside a cropped resource bar is rendered in RED (100% full storage in COC)."""
        if bgr_crop is None or bgr_crop.size == 0:
            return False
        d_area = bgr_crop[:, :-25] if bgr_crop.shape[1] > 35 else bgr_crop
        b_d, g_d, r_d = cv2.split(d_area)
        return int(np.sum((r_d > 185) & (g_d < 105) & (b_d < 105))) >= 40

    def read_village_storages(self, frame_1280x720):
        """
        Reads current village storage amounts from the top right.
        Accurately supports:
        1. Standard neutral Home Village layout (tight crop right before resource icon at x: 1215)
        2. Shifted layout when the Build / Buildings & Heroes drawer is open (x: 755..875)
        3. Vertical alignment & spacing filtering to reject liquid fill meter glints (e.g. false '72' digits)
        4. Clamping against live village max capacity (caps from village_profile)
        5. RED text detection when storages are 100% FULL (sets gold_full / elixir_full flags)
        """
        if frame_1280x720 is None or frame_1280x720.size == 0:
            return {"gold": 0, "elixir": 0, "dark_elixir": 0, "gold_full": False, "elixir_full": False}

        # Check if Buildings & Heroes drawer is open on the right (red close X at (1240, 35))
        close_x = frame_1280x720[15:55, 1220:1265]
        is_drawer_open = (close_x.size > 0 and np.sum((close_x[:, :, 2] > 165) & (close_x[:, :, 1] < 75) & (close_x[:, :, 0] < 75)) >= 20)

        if is_drawer_open:
            g_crop = frame_1280x720[20:52, 735:875]
            e_crop = frame_1280x720[68:100, 735:875]
            de_crop = frame_1280x720[116:148, 755:875]
        else:
            # Storage text is right-aligned ending at x: 1218 (right before the resource icon).
            # A 7 or 8-digit storage amount (e.g. 3,128,800 or 12,500,000) spans 130-170px.
            # Starting at x=1035 guarantees all leading digits are included with zero truncation!
            g_crop = frame_1280x720[20:52, 1035:1218]
            e_crop = frame_1280x720[68:100, 1035:1218]
            de_crop = frame_1280x720[116:148, 1075:1218]

        gold = self.parse_digits_from_crop(g_crop, is_raid=False)
        elixir = self.parse_digits_from_crop(e_crop, is_raid=False)
        de = self.parse_digits_from_crop(de_crop, is_raid=False)

        gold_full = self.is_crop_red(g_crop)
        elixir_full = self.is_crop_red(e_crop)

        # Sanity Clamp against village max storage capacity
        try:
            from core.village_parser import village_profile
            caps = village_profile.get_max_storage_capacities()
            max_g = caps.get("gold", 5504500)
            max_e = caps.get("elixir", 5503000)
            max_de = caps.get("dark_elixir", 100000)

            def _clamp_val(val, max_cap, name):
                if val <= 0:
                    return 0
                if val > int(max_cap * 1.12):
                    # Check if extra digits (e.g. '72' or '7') were prepended to actual number
                    s = str(val)
                    for cut in [1, 2, 3]:
                        if len(s) > cut:
                            sub = int(s[cut:])
                            if 0 < sub <= max_cap:
                                print(f"[LootOCRReader] Corrected outlier {name} reading {val:,} -> {sub:,} (Max: {max_cap:,})")
                                return sub
                    print(f"[LootOCRReader] Clamped outlier {name} reading {val:,} to max capacity {max_cap:,}")
                    return max_cap
                return val

            gold = _clamp_val(gold, max_g, "Gold")
            elixir = _clamp_val(elixir, max_e, "Elixir")
            de = _clamp_val(de, max_de, "Dark Elixir")
        except Exception:
            pass

        return {
            "gold": gold,
            "elixir": elixir,
            "dark_elixir": de,
            "gold_full": gold_full,
            "elixir_full": elixir_full,
        }

    def read_search_loot(self, frame_1280x720):
        """Reads available raid loot during an attack from top left."""
        gold = self.parse_digits_from_crop(frame_1280x720[95:125, 60:240], is_raid=True)
        elixir = self.parse_digits_from_crop(frame_1280x720[133:163, 60:240], is_raid=True)
        de = self.parse_digits_from_crop(frame_1280x720[170:202, 60:240], is_raid=True)
        return {"gold": gold, "elixir": elixir, "dark_elixir": de}

    def read_loot(self, frame_1280x720):
        """Unified method: detects screen and reads appropriate loot."""
        screen = self.detect_screen(frame_1280x720)
        if screen == "HOME_VILLAGE":
            return self.read_village_storages(frame_1280x720)
        else:
            return self.read_search_loot(frame_1280x720)
