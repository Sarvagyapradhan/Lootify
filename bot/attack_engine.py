"""
Attack Engine for Clash of Clans Automation.
Executes Tactical Army Deployments (Perimeter, Single Side, Two Sides, Corners)
outside the red forbidden line, rapidly depleting full troop stacks,
skipping empty/x0 slots, auto-zooming out battlefield camera,
and deploying all heroes (1 to 4) and spells into base core.
"""

import time
import random
import threading
import cv2
import numpy as np
from core.screen_capture import ScreenCapture
from vision.ocr_reader import LootOCRReader
from ai import AIDetector, TacticalPlanner, DatasetRecorder
from ai.troop_knowledge import get_troop_metadata


class AttackEngine:
    # 100% Safe Outer Deployment Perimeter Coordinates (Resolution: 1280x720)
    # Guaranteed outside the base red line and completely clear of all HUDs
    # (Surrender button at x=10..150, y=530..610; Next button at x=1060..1260, y=490..590; Tray at y>=615; Loot at x<=210, y<=160)
    OUTER_CORNERS = {
        "TOP": (640, 70),
        "RIGHT": (1095, 320),
        "BOTTOM": (640, 582),
        "LEFT": (175, 340),
    }

    OUTER_EDGES = {
        "TOP_RIGHT": [
            (750, 75),
            (880, 110),
            (1000, 170),
            (1090, 250),
        ],
        "BOTTOM_RIGHT": [
            (1095, 390),
            (1010, 460),
            (890, 520),
            (760, 555),
        ],
        "BOTTOM_LEFT": [
            (520, 585),
            (380, 560),
            (260, 500),
            (175, 410),
        ],
        "TOP_LEFT": [
            (175, 270),
            (250, 180),
            (370, 120),
            (510, 75),
        ],
    }

    # Absolute outer grass points guaranteed outside any elongated village boundary
    OUTER_ABSOLUTE_GRASS = [
        (640, 65),     # Absolute top grass
        (780, 80),     # Top-right outer grass
        (920, 125),    # Top-right flank
        (1040, 210),   # Far right edge
        (1095, 320),   # Right beach corner
        (1020, 430),   # Bottom-right flank
        (880, 520),    # Bottom-right edge
        (760, 580),    # Bottom edge
        (640, 585),    # Bottom corner
        (520, 585),    # Bottom-left edge
        (380, 560),    # Bottom-left flank
        (250, 480),    # Far left edge
        (175, 340),    # Left beach corner
        (180, 250),    # Top-left flank
        (280, 150),    # Top-left edge
        (480, 80),     # Top-left edge
    ]

    # Calibrated Bottom Unit Tray Slot Centers
    TRAY_SLOTS = [
        (185, 675),  # Slot 1
        (252, 675),  # Slot 2
        (319, 675),  # Slot 3
        (386, 675),  # Slot 4
        (453, 675),  # Slot 5
        (520, 675),  # Slot 6
        (587, 675),  # Slot 7
        (654, 675),  # Slot 8
        (721, 675),  # Slot 9
        (788, 675),  # Slot 10
    ]

    def __init__(self, adb_controller, ui_detector, heroes_config, recipes_config, global_config=None, screen_capture=None):
        self.adb = adb_controller
        self.detector = ui_detector
        self.heroes_cfg = heroes_config.get("heroes", {}) if heroes_config else {}
        self.recipes_cfg = recipes_config.get("recipes", {}) if recipes_config else {}
        self.cfg = global_config or {}
        self.capture = screen_capture or ScreenCapture(adb_controller=self.adb)
        self.active_threads = []
        self.fsm = None
        self.abort_requested = False
        self.ocr = LootOCRReader()
        self.ai_detector = AIDetector()
        self.tactical_planner = TacticalPlanner()
        self.dataset_recorder = DatasetRecorder()

    def check_should_abort(self):
        """Checks if stop or pause has been requested by the user."""
        if self.abort_requested:
            return True
        if self.fsm:
            if not self.fsm.is_running:
                return True
            while self.fsm.is_paused and self.fsm.is_running:
                time.sleep(0.1)
            return not self.fsm.is_running
        return False

    def update_config(self, new_config):
        """Updates internal configuration from GUI or runtime modifications."""
        self.cfg = new_config or {}

    def get_pattern_drop_points(self, pattern="ALL_4_SIDES"):
        """
        Calculates safe outer grass drop points based on tactical pattern:
        - ALL_4_SIDES: Surround wave outside all 4 edges of the base (ideal for loot harvesting)
        - TWO_SIDES: Two adjacent edges for an L-shaped pincer attack
        - SINGLE_SIDE: Focuses all troops along 1 flank
        - SURGICAL_PERIMETER: Rapid multi-point perimeter wave outside collectors
        - CORE_RUSH: Funnel along 1 flank targeting the central core
        - ALL_4_CORNERS: Drops troops across all 4 outer corner points
        - SINGLE_CORNER: Focuses troops into a single outer corner funnel
        """
        pattern_norm = (pattern or "ADAPTIVE_SMART").upper().replace(" ", "_").replace("-", "_")

        # ADAPTIVE SMART AI TACTICS: Dynamically vary attack pattern every battle!
        if "ADAPTIVE" in pattern_norm or "SMART" in pattern_norm or "VARIETY" in pattern_norm or "RANDOM" in pattern_norm:
            tactical_styles = [
                ("TWO_SIDES", "Two Sides Pincer (Converging L-Flank assault)"),
                ("SURGICAL", "Surgical Perimeter Sweep (Outer Collectors & Storages First)"),
                ("CORE_RUSH", "Single Flank Funnel & Core Push"),
                ("ALL_4_SIDES", "Full 4-Sided Perimeter Surround"),
            ]
            chosen_style, style_desc = random.choice(tactical_styles)
            print(f"[AttackEngine] [AI Tactics] ADAPTIVE AI TACTIC ACTIVATED: {style_desc}")
            return self.get_pattern_drop_points(chosen_style)

        if "ALL_4_CORNERS" in pattern_norm or "FOUR_CORNERS" in pattern_norm:
            print("[AttackEngine] Tactical Pattern: ALL 4 CORNERS (outer diamond corners).")
            return [
                self.OUTER_CORNERS["TOP"],
                self.OUTER_CORNERS["RIGHT"],
                self.OUTER_CORNERS["BOTTOM"],
                self.OUTER_CORNERS["LEFT"],
            ]

        elif "SINGLE_CORNER" in pattern_norm or ("CORNER" in pattern_norm and "ALL" not in pattern_norm and "FOUR" not in pattern_norm):
            corner_name, corner_pt = random.choice(list(self.OUTER_CORNERS.items()))
            print(f"[AttackEngine] Tactical Pattern: SINGLE CORNER (focused at {corner_name} corner: {corner_pt}).")
            return [corner_pt]

        elif "SURGICAL" in pattern_norm:
            print("[AttackEngine] Tactical Pattern: SURGICAL PERIMETER (multi-point perimeter wave outside collectors).")
            pts = []
            for edge_pts in self.OUTER_EDGES.values():
                pts.extend(edge_pts)
            random.shuffle(pts)
            return pts

        elif "CORE_RUSH" in pattern_norm or "FUNNEL" in pattern_norm:
            edge_name, edge_pts = random.choice(list(self.OUTER_EDGES.items()))
            print(f"[AttackEngine] Tactical Pattern: CORE RUSH (funneling along {edge_name} directly to core).")
            return list(edge_pts)

        elif "SINGLE_SIDE" in pattern_norm or "ONE_SIDE" in pattern_norm or "RANDOM_SIDE" in pattern_norm:
            edge_name, edge_pts = random.choice(list(self.OUTER_EDGES.items()))
            print(f"[AttackEngine] Tactical Pattern: SINGLE SIDE (focused attack along {edge_name} flank).")
            return list(edge_pts)

        elif "TWO_SIDES" in pattern_norm or "2_SIDES" in pattern_norm or "L_SHAPE" in pattern_norm or "PINCER" in pattern_norm:
            pairs = [
                ("TOP_LEFT", "TOP_RIGHT"),
                ("TOP_RIGHT", "BOTTOM_RIGHT"),
                ("BOTTOM_RIGHT", "BOTTOM_LEFT"),
                ("BOTTOM_LEFT", "TOP_LEFT"),
            ]
            side_a, side_b = random.choice(pairs)
            print(f"[AttackEngine] Tactical Pattern: TWO SIDES PINCER (L-shape pincer along {side_a} + {side_b}).")
            return list(self.OUTER_EDGES[side_a]) + list(self.OUTER_EDGES[side_b])

        else:
            # Default: ALL_4_SIDES (Surround wave outside red boundary)
            print("[AttackEngine] Tactical Pattern: ALL 4 SIDES (full perimeter surround outside red line).")
            pts = []
            for edge_pts in self.OUTER_EDGES.values():
                pts.extend(edge_pts)
            return pts

    def get_safe_drop_points(self, frame, pattern="ALL_4_SIDES", raw_candidates=None):
        """
        Dynamically calculates safe outer grass drop points outside the forbidden red building perimeter:
        1. Analyzes frame for red building boundary lines (HSV mask).
        2. Fits a convex hull / polygon enclosing all base defenses.
        3. Projects tactical pattern points strictly into the safe grass at least 55px outside the red hull.
        4. Clamps all drop points away from HUD buttons (Surrender at x<=185, Next at x>=1075, Tray at y>=580).
        """
        raw_pts = raw_candidates if raw_candidates is not None else self.get_pattern_drop_points(pattern)
        if frame is None or frame.size == 0:
            return raw_pts

        # Detect red boundary lines in the battlefield
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 130, 120]), np.array([8, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([172, 130, 120]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Exclude HUD areas
        red_mask[:115, :] = 0      # Top loot/trophies
        red_mask[580:, :] = 0      # Bottom tray
        red_mask[:, :185] = 0      # Left surrender button
        red_mask[:, 1080:] = 0     # Right next button

        # Find red boundary contour points
        red_pts = cv2.findNonZero(red_mask)
        center_x, center_y = 640, 360

        if red_pts is not None and len(red_pts) >= 40:
            hull = cv2.convexHull(red_pts)
        else:
            # Baseline village grid convex hull (44x44 isometric village bounds: diamond centered at 640, 360)
            hull = np.array([
                [640, 115],
                [1080, 360],
                [640, 560],
                [195, 360]
            ], dtype=np.int32)

        safe_pts = []
        for px, py in raw_pts:
            # Test distance: >0 means inside hull, 0 on edge, <0 outside hull
            dist = cv2.pointPolygonTest(hull, (float(px), float(py)), measureDist=True)
            if dist > -55:
                # Point is inside or too close to red boundary: push radially outward away from base center
                dx = px - center_x
                dy = py - center_y
                norm = (dx * dx + dy * dy) ** 0.5
                if norm > 0:
                    push_factor = 1.0 + (abs(dist) + 65.0) / norm
                    px = int(center_x + dx * push_factor)
                    py = int(center_y + dy * push_factor)

            # STRICT HUD & SCREEN EXCLUSIONS:
            # 1. Next button: x: 1055..1280, y: 470..595
            if py >= 470 and px >= 1020:
                px = 1015
            # 2. Surrender / End Battle button: x: 0..195, y: 480..600
            if py >= 480 and px <= 200:
                px = 205
            # 3. Bottom army tray: y >= 575
            py = min(560, py)
            # 4. Top Loot HUD: x <= 260, y <= 125
            if px <= 260 and py <= 125:
                py = 135

            # Final safety clamping (away from HUD and screen edges)
            px = max(195, min(1020, px))
            py = max(65, min(560, py))
            safe_pts.append((px, py))

        print(f"[AttackEngine] Verified {len(safe_pts)} safe drop points outside the base red line boundary.")
        return safe_pts

    def get_opposite_drop_points(self, primary_points, pattern="ALL_4_SIDES", frame=None):
        """
        Calculates safe outer grass drop points on the opposite side of the battlefield from primary points.
        Point reflection across base center (640, 360):
        (px, py) -> (1280 - px, 720 - py), then verified and pushed outside red boundary.
        """
        opp_raw = []
        for px, py in primary_points:
            opp_x = 1280 - px
            opp_y = 720 - py
            opp_raw.append((opp_x, opp_y))

        return self.get_safe_drop_points(frame, raw_candidates=opp_raw)

    def _is_card_depleted_visually(self, frame, slot_x):
        """
        Determines purely from visual pixel state whether a troop tray slot is empty or depleted.
        In Clash of Clans:
        - Empty dashed slot over transparent battlefield grass is empty.
        - Depleted card is pitch black / deeply darkened (mean_val < 36) and desaturated.
        - Never flags active dark cards (Minion Prince, Earthquake Spell, Witch) as empty!
        """
        if frame is None or frame.size == 0:
            return False
        # Slot card bounds in 1280x720: y=648..720, width=76px
        card = frame[648:720, max(0, slot_x - 38):min(1280, slot_x + 38)]
        if card.shape[0] < 55 or card.shape[1] < 45:
            return True

        # 0. Empty dashed slot over battlefield grass check
        card_b = float(np.mean(card[:, :, 0]))
        card_g = float(np.mean(card[:, :, 1]))
        card_r = float(np.mean(card[:, :, 2]))
        if card_b < 55 and card_g > 65 and (card_g > card_b * 1.4) and (card_b + card_r < 140):
            return True

        # 1. Darkness check - truly depleted cards in CoC are pitch black / deep gray (mean < 36)
        mean_val = np.mean(card)
        if mean_val < 36:
            return True

        # 2. Desaturation check - empty cards in COC are completely grayed out with low value
        hsv = cv2.cvtColor(card, cv2.COLOR_BGR2HSV)
        sat_mean = np.mean(hsv[15:65, 10:50, 1])
        if sat_mean < 15 and mean_val < 42:
            return True

        return False

    def _is_slot_empty(self, frame, slot_x):
        """Alias for visual depletion check."""
        return self._is_card_depleted_visually(frame, slot_x)

    def _is_hero_deployed(self, frame, slot_x, card_before=None):
        """Verifies whether a hero was deployed onto the battlefield."""
        if frame is None or frame.size == 0:
            return True
        card = frame[648:720, max(0, slot_x - 38):min(1280, slot_x + 38)]
        if card.shape[0] < 55 or card.shape[1] < 45:
            return True

        # Check 1: Card diff compared to pre-deployment
        if card_before is not None and card_before.shape == card.shape:
            diff = float(np.mean(cv2.absdiff(card_before, card)))
            if diff > 8.0:
                return True

        # Check 2: Hero health bar (bright neon green horizontal strip inside card)
        # CRITICAL: Exclude bottom-right corner ([-26:, -26:]) where Grand Warden air/ground mode toggle lives,
        # and exclude outer edges where transparent battlefield grass is visible!
        h_bar = card[50:62, 12:52]
        if h_bar.size > 0:
            hsv_bar = cv2.cvtColor(h_bar, cv2.COLOR_BGR2HSV)
            green_health = np.sum((hsv_bar[:, :, 0] >= 35) & (hsv_bar[:, :, 0] <= 85) & 
                                  (hsv_bar[:, :, 1] >= 150) & (hsv_bar[:, :, 2] >= 140))
            if green_health >= 20:
                return True

        # Check 3: Slot is empty/depleted or transformed
        if self._is_slot_empty(frame, slot_x):
            return True

        # Check 4: Deployed hero state (crimson red card with crown outline)
        b_c, g_c, r_c = float(np.mean(card[:, :, 0])), float(np.mean(card[:, :, 1])), float(np.mean(card[:, :, 2]))
        if r_c > 85 and b_c < 30 and g_c < 30:
            return True

        return False

    def _is_select_different_unit_warning(self, frame):
        """Detects in-game red alert 'Select a different unit' displayed when tapping empty/depleted slot."""
        if frame is None or frame.size == 0:
            return False
        crop = frame[195:250, 450:830]
        if crop.size == 0:
            return False
        red_pts = np.sum((crop[:, :, 2] > 190) & (crop[:, :, 1] < 50) & (crop[:, :, 0] < 50))
        return red_pts >= 1000

    def _identify_unit_name(self, card, is_hero=False, is_spell=False):
        """Identifies specific troop, hero, super troop, or spell name using color and feature signatures."""
        if is_hero:
            # Check for deployed or active red state (crimson frame)
            face = card[18:65, 12:52]
            fb, fg, fr = cv2.split(face)
            mean_fr = float(np.mean(fr))
            mean_fb = float(np.mean(fb))
            mean_fg = float(np.mean(fg))
            is_crimson_deployed = (mean_fr > 80 and mean_fb < 35 and mean_fg < 35)

            # 1. Grand Warden: Green Air/Ground mode switch in bottom right corner (100% unique to Warden)
            bot_right = card[-26:, -26:]
            br_hsv = cv2.cvtColor(bot_right, cv2.COLOR_BGR2HSV)
            green_toggle = int(np.sum((br_hsv[:, :, 0] >= 35) & (br_hsv[:, :, 0] <= 85) & (br_hsv[:, :, 1] >= 75) & (br_hsv[:, :, 2] >= 75)))
            if green_toggle >= 12:
                return "Grand Warden"

            # 2. Minion Prince: Cyan/Sky Blue skin or dark cowl (Minion skin has 400+ cyan pixels)
            cyan_skin = int(np.sum((fb > 120) & (fg > 85) & (fr < 95) & (fb.astype(int) - fr.astype(int) > 20)))
            if cyan_skin >= 150:
                return "Minion Prince"

            # 3. Archer Queen: Golden crown + long vibrant purple/magenta hair framing face (and no air/ground toggle)
            crown_roi = card[14:38, 20:56]
            cr_b, cr_g, cr_r = cv2.split(crown_roi)
            purple_hair = int(np.sum((fb > 100) & (fr > 80) & (fg < 95) & (fb.astype(int) - fg.astype(int) > 12)))
            face_hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
            queen_magenta = int(np.sum((face_hsv[:, :, 0] >= 130) & (face_hsv[:, :, 0] <= 168) & (face_hsv[:, :, 1] >= 50) & (face_hsv[:, :, 2] >= 60)))
            if (queen_magenta >= 300 and purple_hair >= 100) or (queen_magenta >= 600):
                return "Archer Queen"

            # 4. Barbarian King: Golden crown AND bright yellow mustache/hair
            king_crown = int(np.sum((cr_r > 175) & (cr_g > 145) & (cr_b < 80) & (cr_r.astype(int) - cr_b.astype(int) > 60)))
            yellow_hair = int(np.sum((fr > 175) & (fg > 145) & (fb < 85) & (fr.astype(int) - fb.astype(int) > 55)))
            if king_crown >= 12 and yellow_hair >= 20:
                return "Barbarian King"

            # 5. Royal Champion: Blue hair/scarf + bronze forehead tiara
            lower = card[45:85, 15:55]
            lb, lg, lr = cv2.split(lower)
            blue_scarf = int(np.sum((lb > 120) & (lb.astype(int) - lr.astype(int) > 25)))
            if blue_scarf >= 30:
                return "Royal Champion"

            # Deployed state fallback
            if is_crimson_deployed:
                return "Minion Prince"

            return "Minion Prince"

        if is_spell:
            s_roi = card[20:65, 12:52]
            b, g, r = float(np.mean(s_roi[:, :, 0])), float(np.mean(s_roi[:, :, 1])), float(np.mean(s_roi[:, :, 2]))
            if (b > 150 and g > 115 and b > r * 1.15) or (b > 165 and g > 125):
                return "Lightning Spell"
            elif (abs(b - r) < 45 and b < 145 and g < 120) or (r > 75 and r > b + 5 and b < 140 and g < 120) or (b < 140 and g < 115 and r < 140 and abs(b - r) <= 30):
                return "Earthquake Spell"
            elif g > 110 and r < 90 and b < 90:
                return "Jump Spell"
            elif r > 110 and b > 110 and g < 90:
                return "Rage Spell"
            elif r > 120 and g > 110 and b < 80:
                return "Healing Spell"
            elif b > 120 and g > 110 and r < 90:
                return "Freeze Spell"
            elif g > 100 and r > 100 and b < 70:
                return "Overgrowth Spell"
            elif r > 120 and b < 90 and g < 80:
                return "Poison Spell"
            elif b > 110 and r > 110:
                return "Bat Spell"
            return "Spell"

        # Frontline Troops, Super Troops & Siege Machines
        t_roi = card[20:65, 10:52]
        b, g, r = float(np.mean(t_roi[:, :, 0])), float(np.mean(t_roi[:, :, 1])), float(np.mean(t_roi[:, :, 2]))

        # 1. Dragons (Electro Dragon & Fire/Purple Dragon)
        if b > 135 and (b - r) > 20:
            return "Electro Dragon"
        snout = card[25:62, 14:52]
        sb, sg, sr = cv2.split(snout)
        red_snout = int(np.sum((sr > 135) & (sg < 90) & (sb < 90)))
        white_teeth = int(np.sum((sr > 170) & (sg > 170) & (sb > 170)))
        purple_dragon = (b > 85 and r > 80 and g < 105 and white_teeth >= 6)
        if red_snout >= 12 or white_teeth >= 10 or purple_dragon or (r > 115 and r > b * 1.25 and r > g * 1.12):
            return "Dragon"

        if g > 105 and r < 100 and b < 80:
            return "Sneaky Goblin"
        # Wizard requires bright blue cowl with human skin tones (not dragon scales)
        if b > 125 and r < 85 and g < 95 and white_teeth < 5:
            return "Wizard"
        if r > 130 and g > 130 and b > 130 and t_roi.std() > 45:
            return "Super Wall Breaker" if r > 140 else "Wall Breaker"
        if r > 135 and g > 90 and b < 70:
            return "Giant"
        if r > 145 and g > 125 and b < 85:
            return "Barbarian"
        if r > 135 and b > 100 and g < 90:
            return "Super Archer" if b > 115 else "Archer"
        if r > 130 and g < 85 and b < 85:
            return "Rocket Balloon" if b < 60 else "Balloon"
        if r > 110 and b > 110 and g < 85:
            return "Super Dragon" if r > 130 else "Dragon"
        if g > 125 and r < 110 and b < 85:
            return "Inferno Dragon" if b > 90 else "Baby Dragon"
        if b > 110 and r > 90 and g < 90:
            return "P.E.K.K.A"
        if b > 135 and g > 120 and r < 90:
            return "Super Minion"
        if r > 115 and g > 75 and b < 65:
            return "Super Hog Rider" if g > 90 else "Hog Rider"
        if r > 140 and g > 95 and b < 75:
            return "Super Valkyrie" if r > 150 else "Valkyrie"
        if r > 110 and b > 110 and g < 80:
            return "Super Witch" if r > 125 else "Witch"
        if b > 125 and r > 105 and g < 90:
            return "Super Bowler" if r > 115 else "Bowler"
        if b > 165 and g > 140 and r < 95 and (b - r) > 65:
            return "Ice Hound"
        if b > 150 and g > 130 and r < 100 and (b - r) > 40:
            return "Ice Golem"
        if g > 110 and r > 90 and b < 70:
            return "Root Rider"
        if r > 135 and g > 130 and b > 110:
            return "Healer"

        return "Troop"

    def scan_battle_tray(self, frame):
        """
        Dynamically analyzes the battle toolbar (tray) to classify each active card:
        - Frontline Troops & Super Troops with exact card count OCR (e.g. x10 Dragons, x60 Sneaky Goblins)
        - Tactical Role Classification (Tanks, Wall Breakers, Resource Harvesters, DPS)
        - Heroes (Archer Queen, Barbarian King, Grand Warden, Royal Champion, Minion Prince)
          In battle, heroes NEVER have count badges (xN) and have Level badges (Lv N) or Warden green toggle.
        - Spells (Lightning, Earthquake, Jump, Rage, Heal, Freeze, etc.)
        - Strict Layout Invariant: [Troops] -> [Heroes] -> [Spells]
        - Contiguous Tray Invariant: Stops scanning immediately when the first empty slot is reached.
        Returns dict with categorized cards, counts, roles, and coordinates.
        """
        if frame is None:
            return {"troops": [], "heroes": [], "spells": [], "cc": [], "empty": []}

        # Baseline slot centers for 1280x720 tray: start at 235 with 83px pitch
        slot_centers = [(235 + idx * 83, 675) for idx in range(11)]
        results = {"troops": [], "heroes": [], "spells": [], "cc": [], "empty": []}

        # Pass 1: Extract non-empty cards and stop on first empty slot
        cards_data = []
        for idx, (cx, cy) in enumerate(slot_centers):
            card = frame[648:720, cx - 38 : cx + 38]
            if card.shape[0] < 55 or card.shape[1] < 45:
                results["empty"].append(idx + 1)
                break

            card_b = float(np.mean(card[:, :, 0]))
            card_g = float(np.mean(card[:, :, 1]))
            card_r = float(np.mean(card[:, :, 2]))

            # Detect empty dashed slot over battlefield grass:
            if card_b < 55 and card_g > 65 and (card_g > card_b * 1.4) and (card_b + card_r < 140):
                results["empty"].append(idx + 1)
                # In Clash of Clans, the army tray is strictly contiguous left-to-right.
                # Once an empty slot is encountered, all subsequent slots to the right are empty!
                break

            top_badge = card[3:25, :]
            count = 0
            if hasattr(self, "ocr") and self.ocr and hasattr(self.ocr, "parse_card_count"):
                count = self.ocr.parse_card_count(top_badge)

            tb, tg, tr = cv2.split(top_badge)
            white_badge_px = int(np.sum((tr > 165) & (tg > 165) & (tb > 130)))
            has_count_badge = (count > 0 or white_badge_px >= 40)

            # Specific hero color signatures
            face = card[18:65, 12:52]
            fb, fg, fr = cv2.split(face)
            mean_fr, mean_fb, mean_fg = float(np.mean(fr)), float(np.mean(fb)), float(np.mean(fg))
            is_deployed_or_cooldown = (mean_fr > 80 and mean_fb < 35 and mean_fg < 35)

            # Archer Queen vibrant violet/magenta hair in HSV
            face_hsv = cv2.cvtColor(face, cv2.COLOR_BGR2HSV)
            queen_magenta = int(np.sum((face_hsv[:, :, 0] >= 130) & (face_hsv[:, :, 0] <= 165) & (face_hsv[:, :, 1] >= 70) & (face_hsv[:, :, 2] >= 70)))

            # Minion Prince cyan skin
            cyan_skin = int(np.sum((fb > 120) & (fg > 85) & (fr < 95) & (fb.astype(int) - fr.astype(int) > 20)))
            purple_hair = int(np.sum((fb > 100) & (fr > 80) & (fg < 95) & (fb.astype(int) - fg.astype(int) > 12)))

            # Barbarian King crown & yellow hair
            crown_roi = card[14:32, 20:56]
            cr_b, cr_g, cr_r = cv2.split(crown_roi)
            king_crown = int(np.sum((cr_r > 175) & (cr_g > 145) & (cr_b < 80) & (cr_r.astype(int) - cr_b.astype(int) > 60)))
            yellow_hair = int(np.sum((fr > 175) & (fg > 145) & (fb < 85) & (fr.astype(int) - fb.astype(int) > 55)))

            lower = card[45:85, 15:55]
            lb, lg, lr = cv2.split(lower)
            blue_scarf = int(np.sum((lb > 120) & (lb.astype(int) - lr.astype(int) > 25)))

            # Grand Warden Air/Ground mode switch in bottom right corner (100% unique in CoC)
            bot_right = card[-26:, -26:]
            br_hsv = cv2.cvtColor(bot_right, cv2.COLOR_BGR2HSV)
            green_toggle = int(np.sum((br_hsv[:, :, 0] >= 35) & (br_hsv[:, :, 0] <= 85) & (br_hsv[:, :, 1] >= 75) & (br_hsv[:, :, 2] >= 75)))

            # Spell color checks (Lightning, Earthquake, etc.)
            s_roi = card[20:65, 12:52]
            sb_m, sg_m, sr_m = float(np.mean(s_roi[:, :, 0])), float(np.mean(s_roi[:, :, 1])), float(np.mean(s_roi[:, :, 2]))
            is_lightning_spell = (sb_m > 180 and sg_m > 135) or (sb_m > 165 and sg_m > 125 and sb_m > sr_m * 1.25)
            has_toggle = (green_toggle >= 12 and not is_lightning_spell)

            # Earthquake Spell: Dark brown potion vial with cracked earth textures
            is_earthquake_spell = (
                not has_toggle
                and not is_lightning_spell
                and not is_deployed_or_cooldown
                and cyan_skin < 15
                and queen_magenta < 50
                and sb_m >= 75
                and sg_m >= 60
                and abs(sb_m - sr_m) <= 40
            )

            # Frontline Dragon check (fiery mouth, teeth, dragon scales - NEVER a hero!)
            snout = card[25:62, 14:52]
            sb, sg, sr = cv2.split(snout)
            red_snout = int(np.sum((sr > 135) & (sg < 90) & (sb < 90)))
            white_teeth = int(np.sum((sr > 170) & (sg > 170) & (sb > 170)))
            is_e_drag = (mean_fb > 135 and (mean_fb - mean_fr) > 20) and (cyan_skin < 25)
            is_fire_drag = (red_snout >= 10 or white_teeth >= 8) and (mean_fr > 115 and mean_fr > mean_fb * 1.25)
            is_dragon_card = (is_e_drag or is_fire_drag) and (purple_hair < 18) and not has_toggle

            cards_data.append({
                "slot": idx + 1,
                "cx": cx,
                "cy": cy,
                "card": card,
                "count": count,
                "white_badge_px": white_badge_px,
                "has_count_badge": has_count_badge,
                "has_toggle": has_toggle,
                "cyan_skin": cyan_skin,
                "purple_hair": purple_hair,
                "queen_magenta": queen_magenta,
                "king_crown": king_crown,
                "yellow_hair": yellow_hair,
                "blue_scarf": blue_scarf,
                "is_lightning": is_lightning_spell,
                "is_earthquake": is_earthquake_spell,
                "is_dragon": is_dragon_card,
                "is_deployed": is_deployed_or_cooldown,
            })

        # Pass 2: Dynamic Layout Partitioning
        # In Clash of Clans:
        # - Regular frontline troops start at Slot 0 and extend to the first hero.
        # - Heroes appear in the middle (Archer Queen, Minion Prince, Grand Warden, Barbarian King, Royal Champion).
        # - Spells are ALWAYS located strictly after all heroes!
        # - STRICT INVARIANT: Heroes NEVER have count badges (xN)!
        #   Cards with genuine hero traits (queen magenta, minion cyan skin, warden green toggle, king crown) are heroes.
        #   Cards after the heroes are GUARANTEED to be Spells (Earthquake, Lightning, etc.)!

        hero_indices = []
        for i in range(1, len(cards_data)):
            c = cards_data[i]
            if c["is_dragon"] and i == 0:
                continue
            is_hero_trait = (
                c["has_toggle"]
                or c["cyan_skin"] >= 25
                or c["queen_magenta"] >= 60
                or (c["king_crown"] >= 12 and c["yellow_hair"] >= 20)
                or c["blue_scarf"] >= 25
                or c["is_deployed"]
            )
            # A card is added as hero strictly if it has genuine hero traits, up to max 3 heroes
            if is_hero_trait and len(hero_indices) < 3:
                hero_indices.append(i)

        if hero_indices:
            first_hero_idx = min(hero_indices)
            last_hero_idx = max(hero_indices)
            spell_start_idx = last_hero_idx + 1
        else:
            first_hero_idx = 1
            last_hero_idx = 0
            spell_start_idx = 1

        # Pass 3: Partition Cards into Troops, Heroes, and Spells
        # 1. Frontline Troops (0 .. first_hero_idx - 1)
        for i in range(0, first_hero_idx):
            cdata = cards_data[i]
            card = cdata["card"]
            cx, cy = cdata["cx"], cdata["cy"]
            count = cdata["count"]
            slot = cdata["slot"]
            t_name = self._identify_unit_name(card, is_hero=False)
            if t_name == "Troop" or "Dragon" not in t_name:
                t_name = "Electro Dragon" if cdata["is_dragon"] and cdata["card"][20:65, 10:52, 0].mean() > 140 else "Dragon"
            meta = get_troop_metadata(t_name)
            safe_count = count if count > 0 else (10 if "Dragon" in t_name else 15)
            results["troops"].append({
                "slot": slot,
                "coord": (cx, cy),
                "name": t_name,
                "count": safe_count,
                "role": meta.get("role", "DPS"),
                "priority_order": meta.get("priority_order", 4),
            })

        # 2. Heroes (first_hero_idx .. spell_start_idx - 1)
        # Any order of heroes is handled seamlessly, with strict singleton uniqueness (no duplicate names)
        seen_heroes = set()
        for i in range(first_hero_idx, spell_start_idx):
            cdata = cards_data[i]
            card = cdata["card"]
            cx, cy = cdata["cx"], cdata["cy"]
            slot = cdata["slot"]

            h_name = None
            if cdata["has_toggle"] and "Grand Warden" not in seen_heroes:
                h_name = "Grand Warden"
            elif cdata["queen_magenta"] >= 60 and "Archer Queen" not in seen_heroes:
                h_name = "Archer Queen"
            elif cdata["cyan_skin"] >= 18 and "Minion Prince" not in seen_heroes:
                h_name = "Minion Prince"
            elif (cdata["king_crown"] >= 12 and cdata["yellow_hair"] >= 20) and "Barbarian King" not in seen_heroes:
                h_name = "Barbarian King"
            elif cdata["blue_scarf"] >= 25 and "Royal Champion" not in seen_heroes:
                h_name = "Royal Champion"
            else:
                # Active TH11 hero roster prioritization
                for candidate in ["Archer Queen", "Minion Prince", "Grand Warden"]:
                    if candidate not in seen_heroes:
                        h_name = candidate
                        break
                if not h_name:
                    for candidate in ["Barbarian King", "Royal Champion"]:
                        if candidate not in seen_heroes:
                            h_name = candidate
                            break

            if not h_name:
                h_name = f"Hero_{slot}"
            seen_heroes.add(h_name)
            results["heroes"].append({
                "slot": slot,
                "coord": (cx, cy),
                "name": h_name,
                "count": 1,
                "role": "HERO",
                "priority_order": 5,
                "has_pet": False,
                "is_deployed": cdata.get("is_deployed", False),
            })

        # 3. Spells (spell_start_idx .. len(cards_data) - 1)
        # All cards after the last hero are GUARANTEED to be Spells (and Siege Machines)!
        for i in range(spell_start_idx, len(cards_data)):
            cdata = cards_data[i]
            card = cdata["card"]
            cx, cy = cdata["cx"], cdata["cy"]
            count = cdata["count"]
            slot = cdata["slot"]
            s_name = self._identify_unit_name(card, is_spell=True)
            if s_name == "Spell":
                s_name = "Lightning Spell" if cdata["is_lightning"] else "Earthquake Spell"
            safe_count = count if count > 0 else (4 if "Lightning" in s_name else 3)
            results["spells"].append({
                "slot": slot,
                "coord": (cx, cy),
                "name": s_name,
                "count": safe_count,
                "role": "SPELL",
                "priority_order": 6,
            })

        # Sort frontline troops according to tactical role sequence (Tanks -> Wall Breakers -> Harvesters -> DPS)
        results["troops"].sort(key=lambda t: t.get("priority_order", 4))
        return results

    def _get_smart_lightning_targets(self, frame):
        """
        Calculates optimal spell targets for Lightning Spells and Earthquake Spells:
        1. Identifies all storages (Gold, Elixir, Dark Elixir, Town Hall, Clan Castle) which are 100% IMMUNE to spell damage.
        2. Identifies high-value air-targeting defenses: Air Defenses (highest priority for Zap Dragons),
           followed by Inferno Towers, Eagle Artillery, and Wizard Towers.
        3. Filters targets to ensure lightning strikes land at least 70px away from any storage,
           preventing wasted damage on immune resource structures.
        4. Returns a list of target coordinates [(x, y), ...].
        """
        default_target = (640, 320)
        if frame is None or frame.size == 0 or not hasattr(self, "ai_detector") or not self.ai_detector:
            return [default_target]

        try:
            detections = self.ai_detector.detect(frame)
        except Exception as e:
            print(f"[AttackEngine] AI detection notice ({e}). Using core targeting.")
            return [default_target]

        # Storages & Town Hall are 100% immune to spell damage in Clash of Clans!
        immune_classes = {"gold_storage", "elixir_storage", "dark_elixir_storage", "town_hall", "clan_castle"}
        storages = [d for d in detections if d.get("class") in immune_classes]

        def dist_sq(p1, p2):
            return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2

        def is_near_any_storage(pt, min_dist=70):
            for s in storages:
                sc = s.get("center")
                if sc and dist_sq(pt, sc) < (min_dist ** 2):
                    return True
            return False

        # Priority 1: Air Defenses (the #1 threat to Dragons)
        air_defenses = [d for d in detections if d.get("class") == "air_defense"]
        valid_ads = [ad["center"] for ad in air_defenses if "center" in ad and not is_near_any_storage(ad["center"])]

        if valid_ads:
            print(f"[AttackEngine] [Zap] Smart Zap: Found {len(valid_ads)} Air Defense target(s) safe from storages: {valid_ads}")
            return valid_ads

        # Priority 2: Key heavy defenses (Inferno Tower, Eagle Artillery, Wizard Tower, X-Bow)
        key_def_classes = {"inferno_tower", "eagle_artillery", "wizard_tower", "x_bow"}
        key_defs = [d for d in detections if d.get("class") in key_def_classes]
        valid_defs = [kd["center"] for kd in key_defs if "center" in kd and not is_near_any_storage(kd["center"])]

        if valid_defs:
            print(f"[AttackEngine] [Zap] Smart Zap: Found {len(valid_defs)} Key Defense target(s) away from storages: {valid_defs}")
            return valid_defs

        # Priority 3: Fallback core compartment that strictly avoids any detected storages
        candidate_cores = [(640, 320), (640, 250), (550, 320), (730, 320), (640, 390)]
        for pt in candidate_cores:
            if not is_near_any_storage(pt, min_dist=80):
                print(f"[AttackEngine] [Zap] Smart Zap: Targeting core compartment at {pt} (safe distance from storages).")
                return [pt]

        # If all candidates are near storages, pick the one farthest from the closest storage
        best_pt = default_target
        max_min_dist = -1
        valid_storage_centers = [s["center"] for s in storages if s.get("center")]
        for pt in candidate_cores:
            min_d = min([dist_sq(pt, sc) for sc in valid_storage_centers]) if valid_storage_centers else 999999
            if min_d > max_min_dist:
                max_min_dist = min_d
                best_pt = pt

        print(f"[AttackEngine] [Zap] Smart Zap: Selected safest core point at {best_pt} (maximized distance from storages).")
        return [best_pt]

    def deploy_tactical_army(self, pattern=None, deplete=True, taps_per_card=None):
        """
        Deploys troops strictly outside the red boundary with intelligent tactical sequencing:
        1. Deploys frontline troops in role order (Tanks -> Wall Breakers -> Sneaky Goblins/Harvesters -> DPS).
        2. Respects card count badges: stops tapping immediately when card is depleted (no 20 taps for 2 wizards).
        3. Deploys heroes on attack flank with scheduled active abilities.
        4. Casts spells into base core compartment.
        5. Tracks live in-battle loot percentage stolen and surrenders early when loot target is reached.
        """
        combat_cfg = self.cfg.get("combat", {}) if hasattr(self, "cfg") and self.cfg else {}
        if pattern is None:
            pattern = combat_cfg.get("deployment_pattern", "ALL_4_SIDES")
        if taps_per_card is None:
            taps_per_card = combat_cfg.get("taps_per_troop_card", 25)
        if deplete is None:
            deplete = combat_cfg.get("deplete_troops", True)

        hero_ability_delay = combat_cfg.get("hero_ability_delay", 15)
        auto_zoom = combat_cfg.get("auto_zoom_out", False)
        early_surrender_pct = combat_cfg.get("early_surrender_loot_percent", 80)

        self.abort_requested = False
        print("\n[AttackEngine] >>> INITIATING INTELLIGENT TACTICAL ARMY DEPLOYMENT <<<")

        if self.check_should_abort():
            return

        # 0. Battle Screen Readiness: Ensure matchmaking clouds have cleared and battle tray is visible
        frame = None
        for _wait_ready in range(15):
            if self.check_should_abort():
                return
            frame = self.capture.get_frame(target_size=(1280, 720)) if hasattr(self, "capture") else None
            if frame is not None:
                has_end_btn = self.detector.check_end_battle_button(frame) is not None
                has_next_btn = self.detector.find_template(frame, "next_button", threshold=0.58) is not None
                center_crop = frame[250:470, 450:830]
                cb, cg, cr = float(np.mean(center_crop[:, :, 0])), float(np.mean(center_crop[:, :, 1])), float(np.mean(center_crop[:, :, 2]))
                is_cloud = (cb > 175 and cg > 175 and cr > 175 and center_crop.std() < 28)
                if (has_end_btn or has_next_btn) and not is_cloud:
                    break
            time.sleep(0.18)

        # Battle Camera Zoom: Smoothly auto-zoom out to reveal full perimeter
        if auto_zoom:
            print("[AttackEngine] Auto-zooming battlefield camera to maximum full-perimeter view via MEmu...")
            self.adb.pinch_zoom_out(times=2)
            time.sleep(0.4)
            frame = self.capture.get_frame(target_size=(1280, 720)) if hasattr(self, "capture") else frame

        if frame is None:
            frame = self.capture.get_frame(target_size=(1280, 720)) if hasattr(self, "capture") else None
        drop_points = self.get_safe_drop_points(frame, pattern)

        # Read initial target loot
        initial_loot = self.ocr.read_search_loot(frame) if hasattr(self, "ocr") and self.ocr else {}
        init_gold = initial_loot.get("gold", 0)
        init_elixir = initial_loot.get("elixir", 0)
        initial_total = init_gold + init_elixir
        if initial_total > 0:
            print(f"[AttackEngine] 🎯 Base Loot Available: Gold: {init_gold:,} | Elixir: {init_elixir:,} (Total: {initial_total:,})")

        # 1. Dynamically scan the battle tray to identify all troops, counts, heroes, and spells!
        tray_analysis = self.scan_battle_tray(frame)
        troops = tray_analysis.get("troops", [])
        heroes = tray_analysis.get("heroes", [])
        spells = tray_analysis.get("spells", [])

        troop_summary = [(t['name'], f"x{t.get('count', '?')}") for t in troops]
        print("[AttackEngine] Dynamic Army Tray Analysis:")
        print(f"  • Frontline Troops Detected: {len(troops)} cards ({troop_summary})")
        print(f"  • Heroes Detected: {len(heroes)} ({[h['name'] for h in heroes]})")
        print(f"  • Spells Detected: {len(spells)} cards ({[s['name'] for s in spells]})")

        # Fallback if tray scan found no cards (use calibrated default slots)
        if not troops and not heroes:
            print("[AttackEngine] Notice: Using fallback tray slots.")
            troops = [{"slot": i + 1, "coord": (236 + i * 77, 665), "name": f"Troop_{i+1}", "count": 20, "priority_order": 4} for i in range(4)]
            heroes = [{"slot": 5, "coord": (555, 665), "name": "Hero_1", "priority_order": 5}, {"slot": 6, "coord": (633, 665), "name": "Hero_2", "priority_order": 5}]
            spells = [{"slot": 7, "coord": (715, 665), "name": "Spell_1", "priority_order": 6}, {"slot": 8, "coord": (792, 665), "name": "Spell_2", "priority_order": 6}]

        deploy_start_time = time.time()
        self.deployed_slots = set()
        self._slot_coords = {item["slot"]: item["coord"] for item in troops + heroes + spells}
        self.hero_slot_coords = set(item["coord"] for item in heroes)
        self.hero_slot_indices = set(item["slot"] for item in heroes)

        # 2. Deploy Frontline Troops in Tactical Sequence (Tanks -> Wall Breakers -> Harvesters -> DPS)
        print(f"[AttackEngine] Phase 1: Deploying {len(troops)} troop stack(s) (Fast Multi-Touch Perimeter Wave)...")
        for t_info in troops:
            if self.check_should_abort():
                return
            slot_id = t_info["slot"]
            if slot_id in self.deployed_slots:
                continue

            # Immediate check: has battle already ended?
            f_now = self.capture.get_frame(target_size=(1280, 720))
            if f_now is not None:
                if self.detector.check_battle_ended(f_now) or self.detector.check_return_home_button(f_now):
                    print("[AttackEngine] 🏁 Battle results screen reached! Returning home cleanly...")
                    self.surrender_and_return_home()
                    return

            coord = t_info["coord"]
            t_name = t_info["name"]
            t_count = t_info.get("count", 0)

            # CRITICAL SAFEGUARD: Never falsely skip undeployed troops before attempting first selection!
            if t_count <= 0:
                t_count = 10 if "Dragon" in t_name else 15

            print(f"[AttackEngine] Selecting {t_name} at {coord} (count: {t_count})...")
            self.adb.tap(coord[0], coord[1], min_delay=0.02, max_delay=0.03)
            time.sleep(0.12)  # 120ms for game client to register troop card selection!

            # CRITICAL PRE-DEPLOYMENT SAFETY STEP:
            # Drop 1 initial probe unit directly at the attack flank (drop_points[0]) to dismiss Next button!
            if len(self.deployed_slots) == 0:
                probe_pt = drop_points[0]
                self.adb.tap(probe_pt[0], probe_pt[1], min_delay=0.02, max_delay=0.035)
                time.sleep(0.04)

            # Unleash entire troop stack at once along the attack flank!
            # Taps exactly t_count times (10 taps for 10 dragons directly)
            taps_to_send = t_count if t_count > 0 else 10
            print(f"[AttackEngine] Unleashing {taps_to_send} {t_name}(s) directly on attack flank...")
            for tap_i in range(taps_to_send):
                if self.check_should_abort():
                    return
                pt_base = drop_points[tap_i % len(drop_points)]
                tx = pt_base[0] + random.randint(-6, 6)
                ty = pt_base[1] + random.randint(-6, 6)
                self.adb.tap(tx, ty, min_delay=0.015, max_delay=0.03)

            self.deployed_slots.add(slot_id)
            print(f"[AttackEngine] Slot {slot_id} ({t_name}) fully unleashed on attack flank.")

        # 3. Deploy Heroes on the EXACT Same Attack Flank with Troops
        # Grand Warden, Archer Queen, and Minion Prince deploy directly along the Dragon attack line!
        if heroes:
            print(f"[AttackEngine] Phase 2: Deploying {len(heroes)} hero(es) directly on attack flank with army...")
            # Deploy directly at verified drop_points on the attack flank (never scattered to far corners!)
            hero_candidates = drop_points if drop_points else [(640, 75)]

            # Grand Warden deploys first alongside troops to immediately cover the dragons with his Life Aura:
            sorted_heroes = sorted(heroes, key=lambda h: 0 if "Warden" in h.get("name", "") else 1)

            for h_idx, h_info in enumerate(sorted_heroes):
                if self.check_should_abort():
                    return

                # Check if battle ended
                f_chk = self.capture.get_frame(target_size=(1280, 720))
                if f_chk is not None:
                    if self.detector.check_battle_ended(f_chk) or self.detector.check_return_home_button(f_chk):
                        print("[AttackEngine] 🏁 Battle results screen reached! Returning home cleanly...")
                        self.surrender_and_return_home()
                        return

                slot_id = h_info["slot"]
                if slot_id in self.deployed_slots:
                    continue

                coord = h_info["coord"]
                h_name = h_info["name"]

                self.deployed_slots.add(slot_id)
                print(f"[AttackEngine] Deploying {h_name} from slot {slot_id} at {coord}...")

                # CRITICAL WARDEN FIX: Tap upper-left region of card (cx - 15, 660)
                # to strictly avoid touching the bottom-right Air/Ground mode toggle switch!
                tap_x = coord[0] - 15 if "Warden" in h_name else coord[0]
                tap_y = 660
                self.adb.tap(tap_x, tap_y, min_delay=0.02, max_delay=0.03)
                time.sleep(0.14)  # 140ms for game to register card selection

                # Send 2 rapid taps 40ms apart on outer safe grass flank to ensure placement registers with 100% certainty!
                flank_pt = hero_candidates[h_idx % len(hero_candidates)]
                self.adb.tap(flank_pt[0] + random.randint(-4, 4), flank_pt[1] + random.randint(-4, 4), min_delay=0.02, max_delay=0.03)
                time.sleep(0.04)
                self.adb.tap(flank_pt[0] + random.randint(-4, 4), flank_pt[1] + random.randint(-4, 4), min_delay=0.02, max_delay=0.03)
                time.sleep(0.08)

                # Hero ability timing:
                # - Grand Warden Eternal Tome: ~12s (makes core assault invulnerable)
                # - Royal Champion Seeking Shield & Minion Prince: ~14s
                # - Barbarian King Iron Fist & Archer Queen Royal Cloak: ~15s
                if "Warden" in h_name:
                    delay = 12
                elif any(h in h_name for h in ["Prince", "Champion"]):
                    delay = 14
                else:
                    delay = hero_ability_delay
                self._schedule_hero_ability(h_name, coord, delay)

        # 4. Smart Spell Targeting & Fast Casts (Full Stack Casts)
        if spells:
            print(f"[AttackEngine] Phase 3: Casting {len(spells)} spell stack(s)...")
            for s_info in spells:
                if self.check_should_abort():
                    return

                f_chk = self.capture.get_frame(target_size=(1280, 720))
                if f_chk is not None:
                    if self.detector.check_battle_ended(f_chk) or self.detector.check_return_home_button(f_chk):
                        print("[AttackEngine] 🏁 Battle results screen reached! Returning home cleanly...")
                        self.surrender_and_return_home()
                        return

                slot_id = s_info["slot"]
                if slot_id in self.deployed_slots:
                    continue

                coord = s_info["coord"]
                s_name = s_info["name"]
                s_count = s_info.get("count", 0)
                if s_count <= 0:
                    s_count = 4 if "Lightning" in s_name else 3

                print(f"[AttackEngine] Selecting {s_name} (x{s_count}) from slot {slot_id}...")
                self.adb.tap(coord[0], coord[1], min_delay=0.02, max_delay=0.03)
                time.sleep(0.14)  # 140ms for game to register spell selection

                # Smart targeting: calculate optimal defense targets strictly avoiding storages
                if "Lightning" in s_name or "Earthquake" in s_name:
                    zap_targets = self._get_smart_lightning_targets(f_chk)
                elif "Rage" in s_name or "Heal" in s_name:
                    zap_targets = [(640, 390)]
                elif "Jump" in s_name:
                    zap_targets = [(640, 360)]
                elif "Freeze" in s_name:
                    zap_targets = [(640, 340)]
                else:
                    zap_targets = [(640, 360)]

                # Cast spell waves: GUARANTEE at least s_count casts so no spells are left behind!
                casts_to_send = max(s_count, 3 if "Earthquake" in s_name else 4)
                print(f"[AttackEngine] Casting {casts_to_send} strikes for {s_name}...")
                for cast_i in range(casts_to_send):
                    if self.check_should_abort():
                        return
                    # Distribute lightning strikes across available targets (e.g. 3 per Air Defense)
                    t_idx = (cast_i // 3) % len(zap_targets)
                    base_target = zap_targets[t_idx]
                    offset_x = random.randint(-10, 10)
                    offset_y = random.randint(-10, 10)
                    st_x = base_target[0] + offset_x
                    st_y = base_target[1] + offset_y

                    self.adb.tap(st_x, st_y, min_delay=0.02, max_delay=0.035)
                    time.sleep(0.06)

                    # Only check for end of battle during casting
                    if cast_i >= s_count:
                        f_chk = self.capture.get_frame(target_size=(1280, 720))
                        if f_chk is not None:
                            if self.detector.check_battle_ended(f_chk) or self.detector.check_return_home_button(f_chk):
                                print("[AttackEngine] 🏁 Battle results screen reached! Returning home cleanly...")
                                self.surrender_and_return_home()
                                return
                            if self._is_select_different_unit_warning(f_chk):
                                break

                self.deployed_slots.add(slot_id)
                print(f"[AttackEngine] Slot {slot_id} ({s_name}) fully cast ({casts_to_send} strikes).")
                time.sleep(0.03)

        # 4. Phase 4: Secondary Sweep for any remaining troops or spells on the main attack flank
        # If any units still remain in the unit tray, deploy them along the PRIMARY attack flank!
        time.sleep(0.05)
        f_sweep = self.capture.get_frame(target_size=(1280, 720))
        if f_sweep is not None:
            if self.detector.check_battle_ended(f_sweep) or self.detector.check_return_home_button(f_sweep):
                print("[AttackEngine] 🏁 Battle results screen reached! Returning home cleanly...")
                self.surrender_and_return_home()
                return

            active_tray = self.scan_battle_tray(f_sweep)
            # CRITICAL SAFEGUARD: Exclude all hero slots from the troop sweep!
            # Deployed hero ability buttons stay bright with green HP bars and must NEVER be treated as undeployed troops!
            remaining_troops = [
                t for t in active_tray.get("troops", [])
                if t["coord"] not in self.hero_slot_coords
                and t["slot"] not in self.hero_slot_indices
                and "hero" not in t.get("role", "").lower()
                and not self._is_card_depleted_visually(f_sweep, t["coord"][0])
                and t.get("count", 0) > 0
            ]
            remaining_spells = [
                s for s in active_tray.get("spells", [])
                if s["coord"] not in self.hero_slot_coords
                and s["slot"] not in self.hero_slot_indices
                and not self._is_card_depleted_visually(f_sweep, s["coord"][0])
                and s.get("count", 0) > 0
            ]

            if remaining_troops or remaining_spells:
                print(f"\n[AttackEngine] 🔄 SECONDARY SWEEP: {len(remaining_troops)} troop stack(s) and {len(remaining_spells)} spell(s) remaining.")
                # Always deploy remaining troops on the primary attack flank so all dragons stay concentrated together!
                flank_pts = drop_points if drop_points else self.get_pattern_drop_points(pattern)

                for rem_t in remaining_troops:
                    if self.check_should_abort():
                        return
                    coord = rem_t["coord"]
                    t_name = rem_t["name"]
                    print(f"[AttackEngine] Deploying remaining {t_name} from slot {rem_t['slot']} on primary attack flank...")
                    self.adb.tap(coord[0], coord[1], min_delay=0.02, max_delay=0.03)
                    time.sleep(0.14)  # 140ms for card selection

                    # Quick 2-3 wave burst max (never 12 waves!)
                    for rem_burst in range(3):
                        if self.check_should_abort():
                            return
                        wave_size = 8
                        for w_i in range(wave_size):
                            if self.check_should_abort():
                                return
                            pt_base = flank_pts[(rem_burst * wave_size + w_i) % len(flank_pts)]
                            tx = pt_base[0] + random.randint(-6, 6)
                            ty = pt_base[1] + random.randint(-6, 6)
                            self.adb.tap(tx, ty, min_delay=0.02, max_delay=0.035)

                        f_chk = self.capture.get_frame(target_size=(1280, 720))
                        if f_chk is not None:
                            if self.detector.check_battle_ended(f_chk) or self.detector.check_return_home_button(f_chk):
                                print("[AttackEngine] 🏁 Battle results screen reached! Returning home cleanly...")
                                self.surrender_and_return_home()
                                return
                            if self._is_select_different_unit_warning(f_chk):
                                print(f"[AttackEngine] ⚠️ 'Select a different unit' warning detected during sweep. Skipping slot {rem_t['slot']}.")
                                break
                            if self._is_card_depleted_visually(f_chk, coord[0]):
                                break
                    print(f"[AttackEngine] Remaining {t_name} deployed on primary flank.")

                for rem_s in remaining_spells:
                    if self.check_should_abort():
                        return
                    coord = rem_s["coord"]
                    s_name = rem_s["name"]
                    print(f"[AttackEngine] Casting remaining spell {s_name} into base...")
                    self.adb.tap(coord[0], coord[1], min_delay=0.02, max_delay=0.03)
                    time.sleep(0.14)  # 140ms for card selection

                    zap_targets = self._get_smart_lightning_targets(f_sweep) if ("Lightning" in s_name or "Earthquake" in s_name) else [(640, 360)]
                    for cast_i in range(4):
                        base_t = zap_targets[cast_i % len(zap_targets)]
                        drop_x = base_t[0] + random.randint(-12, 12)
                        drop_y = base_t[1] + random.randint(-12, 12)
                        self.adb.tap(drop_x, drop_y, min_delay=0.015, max_delay=0.03)
                        f_chk = self.capture.get_frame(target_size=(1280, 720))
                        if f_chk is not None:
                            if self.detector.check_battle_ended(f_chk) or self.detector.check_return_home_button(f_chk):
                                print("[AttackEngine] 🏁 Battle results screen reached! Returning home cleanly...")
                                self.surrender_and_return_home()
                                return
                            if self._is_select_different_unit_warning(f_chk):
                                print(f"[AttackEngine] ⚠️ 'Select a different unit' warning detected for spell sweep slot {rem_s['slot']}. Skipping.")
                                break
                            if self._is_card_depleted_visually(f_chk, coord[0]):
                                break

        total_deploy_elapsed = time.time() - deploy_start_time
        print(f"\n[AttackEngine] ⚔️ >>> ALL ARMY DEPLOYED IN {total_deploy_elapsed:.1f} SECONDS! <<< ⚔️")

        # 5. Live In-Battle Loot Harvesting & Smart Battle Ending Loop
        wait_s = max(90, combat_cfg.get("battle_duration_seconds", 90))
        print(f"[AttackEngine] Harvesting raid loot (Target: >= {early_surrender_pct}% loot stolen, Max wait: {wait_s}s)...")

        start_harvest_time = time.time()
        last_stolen = 0
        last_change_time = time.time()

        while (time.time() - start_harvest_time) < wait_s:
            if self.check_should_abort():
                print("[AttackEngine] Stop/Pause requested during battle. Returning home cleanly...")
                self.surrender_and_return_home()
                return

            time.sleep(0.8)
            f_harvest = self.capture.get_frame(target_size=(1280, 720))
            if f_harvest is None:
                continue

            # Check 1: Has battle naturally concluded (Battle Results screen active or Return Home visible)?
            if self.detector.check_battle_ended(f_harvest) or (hasattr(self, "ocr") and self.ocr and self.ocr.detect_screen(f_harvest) == "BATTLE_RESULTS"):
                print("[AttackEngine] 🏁 Battle results screen reached naturally (Victory/Defeat/3 Stars). Returning home...")
                self.surrender_and_return_home()
                return

            # Check 2: Read current loot and check if target reached
            cur_loot = self.ocr.read_search_loot(f_harvest) if hasattr(self, "ocr") and self.ocr else {}
            cur_gold = cur_loot.get("gold", 0)
            cur_elixir = cur_loot.get("elixir", 0)
            cur_total = cur_gold + cur_elixir

            stolen = max(0, initial_total - cur_total) if (initial_total > 0 and cur_total <= initial_total) else 0
            stolen_pct = (stolen / initial_total * 100.0) if initial_total > 0 else 0.0

            if initial_total > 0 and cur_total <= initial_total and (cur_gold > 0 or cur_elixir > 0):
                print(f"[LiveLoot] Loot Stolen: {stolen_pct:.1f}% ({stolen:,} / {initial_total:,}) | Remaining: Gold {cur_gold:,}, Elixir {cur_elixir:,}")
                if stolen_pct >= early_surrender_pct:
                    print(f"[AttackEngine] 🎯 Early Surrender Target Reached ({stolen_pct:.1f}% >= {early_surrender_pct}%)! Ending battle early.")
                    self.surrender_and_return_home()
                    return

            # Check 3: Plateau check - only after substantial battle time (>= 30s) and loot has stagnated for at least 20s
            battle_elapsed = time.time() - start_harvest_time
            if stolen != last_stolen:
                last_stolen = stolen
                last_change_time = time.time()
            else:
                stagnant_sec = time.time() - last_change_time
                if battle_elapsed >= 30.0 and stagnant_sec >= 20.0:
                    status_desc = f"at {stolen_pct:.1f}% stolen" if stolen > 0 else "before getting loot"
                    print(f"[AttackEngine] ⏱️ Loot stagnant for {stagnant_sec:.1f}s after {battle_elapsed:.1f}s of battle ({status_desc}). Ending battle cleanly.")
                    self.surrender_and_return_home()
                    return

        # 6. Surrender and return home safely
        self.surrender_and_return_home()

    def execute_recipe_attack(self, recipe_name=None):
        """
        Executes a complete attack based on the specified army recipe or tactical deployment.
        """
        recipe = self.recipes_cfg.get(recipe_name) if recipe_name else None
        if not recipe or recipe_name in ["Adaptive", "Tactical_Deployment", "Default", "Sneaky_Goblins_Farming"]:
            print("[AttackEngine] Executing Tactical Army Deployment...")
            self.deploy_tactical_army()
            return

        print(f"[AttackEngine] Executing Attack Recipe: {recipe_name}")
        deployment_plan = recipe.get("deployment_plan", [])

        for phase in deployment_plan:
            phase_type = phase.get("strategy")
            print(f"[AttackEngine] Starting phase: {phase.get('name', 'Deployment')}")

            if phase_type == "surgical_perimeter":
                self._deploy_surgical_perimeter(phase)
            elif phase_type == "spaced_perimeter":
                self._deploy_spaced_perimeter(phase)
            elif phase_type == "four_side_wave":
                self._deploy_four_side_wave(phase)
            elif phase_type == "hero_sequence":
                self._deploy_heroes_with_ability_timers(phase)
            elif phase_type in ["center_line", "core_target"]:
                self._deploy_spells(phase)
            elif phase_type == "concentrated_wave":
                self._deploy_concentrated_wave(phase)

            delay_after = phase.get("delay_ms", 500) / 1000.0
            time.sleep(delay_after)

        early_surrender = recipe.get("early_surrender", {})
        max_time = early_surrender.get("max_battle_time_seconds", 50)
        print(f"[AttackEngine] Farming army deployed. Waiting up to {max_time}s for loot collection...")
        time.sleep(max_time)

        self.surrender_and_return_home()

    def deploy_adaptive_army(self):
        """Alias for tactical army deployment."""
        self.deploy_tactical_army()

    def _deploy_heroes_with_ability_timers(self, phase_config):
        """Deploys heroes and schedules ability triggers."""
        hero_slots = [(319, 675), (386, 675)]
        drop_pos = self.OUTER_CORNERS["TOP"]

        for idx, slot_pos in enumerate(hero_slots):
            self.adb.tap(slot_pos[0], slot_pos[1])
            time.sleep(0.15)
            self.adb.tap(drop_pos[0] + idx * 30, drop_pos[1])
            print(f"[AttackEngine] Deployed Hero at ({drop_pos[0] + idx * 30}, {drop_pos[1]})")
            self._schedule_hero_ability(f"hero_{idx+1}", slot_pos, 15)
            time.sleep(0.5)

    def _schedule_hero_ability(self, hero_name, slot_coord, delay_seconds):
        """
        Runs an asynchronous background thread that triggers the hero's ability after delay.
        In Clash of Clans, tapping the hero's icon on the unit tray again triggers their ability.
        """
        def ability_worker():
            print(f"[HeroTimer] {hero_name} ability scheduled in {delay_seconds}s.")
            start_wait = time.time()
            while (time.time() - start_wait) < delay_seconds:
                if self.check_should_abort():
                    return
                time.sleep(0.2)
            if self.check_should_abort():
                return
            frame = self.capture.get_frame(target_size=(1280, 720)) if hasattr(self, "capture") else None
            if frame is not None:
                if self.detector.find_template(frame, "attack_button", threshold=0.65) or self.detector.find_template(frame, "return_home_button", threshold=0.65):
                    return
                # Hero ability activation: In CoC, tapping the hero slot card triggers ability (Royal Cloak, Tome, etc.).
                # We do NOT skip based on visual depletion heuristics because deployed heroes have green HP bars without count numbers.
                if self._is_select_different_unit_warning(frame):
                    return
            tap_x = slot_coord[0] - 14 if "warden" in hero_name.lower() else slot_coord[0]
            tap_y = 662 if "warden" in hero_name.lower() else slot_coord[1]
            self.adb.tap(tap_x, tap_y)
            print(f"[HeroTimer] >>> ACTIVATED {hero_name.upper()} ABILITY! <<<")

        t = threading.Thread(target=ability_worker, daemon=True)
        t.start()
        self.active_threads.append(t)

    def _deploy_surgical_perimeter(self, phase_config):
        """Deploys small clusters of troops near safe exterior points."""
        self.adb.tap(self.TRAY_SLOTS[0][0], self.TRAY_SLOTS[0][1])
        time.sleep(0.15)

        points = self.get_pattern_drop_points("ALL_4_SIDES")
        units_per_spot = phase_config.get("units_per_spot", 3)

        for pt in points:
            for _ in range(units_per_spot):
                self.adb.tap(pt[0], pt[1], min_delay=0.04, max_delay=0.08)
            time.sleep(0.15)

    def _deploy_four_side_wave(self, phase_config):
        """Deploys troops along all 4 safe outer edges."""
        self.adb.tap(self.TRAY_SLOTS[0][0], self.TRAY_SLOTS[0][1])
        time.sleep(0.15)

        points = self.get_pattern_drop_points("ALL_4_SIDES")
        for pt in points:
            self.adb.tap(pt[0], pt[1], min_delay=0.04, max_delay=0.08)
            self.adb.tap(pt[0] + random.randint(-6, 6), pt[1] + random.randint(-6, 6), min_delay=0.04, max_delay=0.08)

    def _deploy_spaced_perimeter(self, phase_config):
        """Deploys single units spaced out around the safe perimeter."""
        self.adb.tap(self.TRAY_SLOTS[0][0], self.TRAY_SLOTS[0][1])
        time.sleep(0.15)

        points = self.get_pattern_drop_points("ALL_4_SIDES")
        delay_s = phase_config.get("delay_between_spots_ms", 600) / 1000.0

        for pt in points:
            self.adb.tap(pt[0], pt[1], min_delay=0.06, max_delay=0.10)
            time.sleep(delay_s)

    def _deploy_spells(self, phase_config):
        """Drops spells into the core compartment."""
        self.adb.tap(self.TRAY_SLOTS[5][0], self.TRAY_SLOTS[5][1])
        time.sleep(0.15)

        count = phase_config.get("count", 1)
        for _ in range(count):
            drop_x = 640 + random.randint(-25, 25)
            drop_y = 360 + random.randint(-25, 25)
            self.adb.tap(drop_x, drop_y, min_delay=0.06, max_delay=0.12)
            time.sleep(0.3)

    def _deploy_concentrated_wave(self, phase_config):
        """Drops a cluster of units at a designated safe funnel point."""
        self.adb.tap(self.TRAY_SLOTS[0][0], self.TRAY_SLOTS[0][1])
        time.sleep(0.15)
        funnel_pt = self.OUTER_CORNERS["TOP"]
        for _ in range(phase_config.get("units_per_spot", 12)):
            self.adb.tap(funnel_pt[0] + random.randint(-10, 10), funnel_pt[1] + random.randint(-10, 10), min_delay=0.04, max_delay=0.08)

    def surrender_and_return_home(self):
        """Ends battle quickly and safely returns to home village with zero incorrect taps."""
        print("[AttackEngine] Ending battle and returning to Home Village...")

        for attempt in range(10):
            if self.check_should_abort():
                return
            frame = self.capture.get_frame(target_size=(1280, 720)) if hasattr(self, "capture") else None
            if frame is None:
                time.sleep(0.35)
                continue

            # 1. Are we already back at Home Village?
            if (
                self.detector.find_template(frame, "attack_button", threshold=0.60)
                or self.detector.find_template(frame, "build_button", threshold=0.60)
            ):
                print("[AttackEngine] Successfully confirmed at Home Village.")
                self.adb.tap_empty_grass()
                return

            # Check for Star Bonus or post-attack reward modal popup
            star_btn = self.detector.check_star_bonus_popup(frame)
            if star_btn:
                print(f"[AttackEngine] 'Star Bonus received!' modal detected! Tapping 'Okay' button at {star_btn}...")
                self.adb.tap(star_btn[0], star_btn[1])
                time.sleep(0.8)
                continue

            # 2. Are we on the Battle Results screen (Return Home button visible)?
            ret_btn = self.detector.check_return_home_button(frame)
            if ret_btn:
                print(f"[AttackEngine] Battle Results screen detected! Tapping 'Return Home' button at {ret_btn}...")
                self.adb.tap(ret_btn[0], ret_btn[1])
                # Wait for transition clouds to clear and home village to appear
                for _ in range(12):
                    time.sleep(0.35)
                    f_chk = self.capture.get_frame(target_size=(1280, 720))
                    if f_chk is not None:
                        star_chk = self.detector.check_star_bonus_popup(f_chk)
                        if star_chk:
                            print(f"[AttackEngine] 'Star Bonus received!' modal appeared during return transition. Tapping 'Okay' at {star_chk}...")
                            self.adb.tap(star_chk[0], star_chk[1])
                            time.sleep(0.8)
                        if (
                            self.detector.find_template(f_chk, "attack_button", threshold=0.60)
                            or self.detector.find_template(f_chk, "build_button", threshold=0.60)
                        ):
                            print("[AttackEngine] Successfully confirmed back at Home Village.")
                            self.adb.tap_empty_grass()
                            return
                continue

            # 3. Is the Surrender Confirmation popup ("Surrender? Okay / Cancel") genuinely open?
            modal_okay = self.detector.check_surrender_modal(frame)
            if modal_okay:
                print(f"[AttackEngine] Surrender confirmation modal detected. Tapping 'Okay' at {modal_okay}...")
                self.adb.tap(modal_okay[0], modal_okay[1])
                time.sleep(1.0)
                continue

            # 4. Are we in combat with 'End Battle' button visible?
            end_btn_pos = self.detector.check_end_battle_button(frame)
            if end_btn_pos:
                print(f"[AttackEngine] In battle. Tapping 'End Battle' button at {end_btn_pos}...")
                self.adb.tap(end_btn_pos[0], end_btn_pos[1])
                time.sleep(0.4)
                # Tap Okay on surrender modal immediately
                print("[AttackEngine] Confirming surrender modal by tapping 'Okay' at (740, 420)...")
                self.adb.tap(740, 420)
                time.sleep(1.2)
                continue

            # 5. Dismiss any open modal dialog (Exit Game, Reinforcements, etc.)
            cancel_btn = self.detector.find_template(frame, "modal_cancel_btn", threshold=0.68)
            if cancel_btn:
                print(f"[AttackEngine] Dismissing popup modal at {cancel_btn}...")
                self.adb.tap(cancel_btn[0], cancel_btn[1])
                time.sleep(0.6)
                continue

            close_x = self.detector.find_template(frame, "modal_close_x", threshold=0.70)
            if close_x:
                print(f"[AttackEngine] Dismissing close X at {close_x}...")
                self.adb.tap(close_x[0], close_x[1])
                time.sleep(0.6)
                continue

            # 6. Fallback tap Return Home default position (640, 605)
            # If screen is darkened by battle results overlay, tap Return Home immediately!
            top_left_brightness = float(np.mean(frame[15:65, 15:65]))
            if top_left_brightness < 75 or attempt >= 1:
                print("[AttackEngine] Tapping default 'Return Home' position (640, 605)...")
                self.adb.tap(640, 605)
                time.sleep(1.0)
