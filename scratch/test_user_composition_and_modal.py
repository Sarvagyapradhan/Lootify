import os
import sys
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.attack_engine import AttackEngine
from vision.detector import UIDetector
from vision.ocr_reader import LootOCRReader

detector = UIDetector()
ocr = LootOCRReader()

class DummyEngine(AttackEngine):
    def __init__(self):
        self.detector = detector
        self.ocr = ocr
        self.recipes_cfg = {}
        self.cfg = {}

engine = DummyEngine()

print("====================================================")
print("TEST 1: Star Bonus Modal Detection")
print("====================================================")
sb_img = cv2.imread("C:/Users/sarva/.gemini/antigravity/brain/3d0f3e62-0521-4442-babc-81868933e065/.user_uploaded/media_1793180623499_76f173a1.png")
sb_btn = detector.check_star_bonus_popup(sb_img)
print(f"Star Bonus Okay button detected at: {sb_btn}")
assert sb_btn is not None, "Failed to detect Star Bonus modal"
assert 550 <= sb_btn[0] <= 750 and 580 <= sb_btn[1] <= 670
print("  [PASS] Star Bonus popup Okay button detected.")

print("\n====================================================")
print("TEST 2: Real Combat Battle Tray Scan (User Screenshot)")
print("====================================================")
battle_img = cv2.imread("C:/Users/sarva/.gemini/antigravity/brain/3d0f3e62-0521-4442-babc-81868933e065/.user_uploaded/media_1793193652391_596e0dfa.png")
battle_img_720 = cv2.resize(battle_img, (1280, 720))

tray = engine.scan_battle_tray(battle_img_720)
print("Troops detected:", tray["troops"])
print("Heroes detected:", tray["heroes"])
print("Spells detected:", tray["spells"])
print("Empty slots:", tray["empty"])

assert len(tray["troops"]) == 1, f"Expected 1 troop stack, got {len(tray['troops'])}"
assert tray["troops"][0]["name"] == "Electro Dragon", f"Expected Electro Dragon, got {tray['troops'][0]['name']}"
assert tray["troops"][0]["count"] == 10, f"Expected count 10, got {tray['troops'][0]['count']}"
assert tray["troops"][0]["slot"] == 1

assert len(tray["heroes"]) == 3, f"Expected 3 heroes, got {len(tray['heroes'])}"
hero_names = [h["name"] for h in tray["heroes"]]
print("Hero names:", hero_names)
assert "Archer Queen" in hero_names
assert "Minion Prince" in hero_names
assert "Grand Warden" in hero_names

assert len(tray["spells"]) == 2, f"Expected 2 spell stacks, got {len(tray['spells'])}"
spell_names = [s["name"] for s in tray["spells"]]
spell_counts = [s["count"] for s in tray["spells"]]
print("Spell names:", spell_names)
print("Spell counts:", spell_counts)
assert "Earthquake Spell" in spell_names and 3 in spell_counts
assert "Lightning Spell" in spell_names and 4 in spell_counts

assert 7 in tray["empty"], "Expected empty slot 7"
print("  [PASS] Dynamic tray analysis accurately separated Electro Dragons (x10), 3 Heroes, 2 Spells, and 0 ghost slots!")

print("\n====================================================")
print("TEST 3: End Battle Button Detection")
print("====================================================")
surr_btn = detector.check_end_battle_button(battle_img_720)
print(f"Surrender button detected at: {surr_btn}")
assert surr_btn is not None
print("  [PASS] Surrender button detected cleanly at bottom-left in combat.")

print("\n====================================================")
print("TEST 4: Visual Depletion Check on Real Battle Screen")
print("====================================================")
# Slot 1 (Electro Dragon) has count=10 -> should NOT be depleted
assert not engine._is_card_depleted_visually(battle_img_720, 235), "Slot 1 should not be depleted!"
# Empty slot 7 (cx = 733) -> should be depleted/empty
assert engine._is_card_depleted_visually(battle_img_720, 733), "Slot 7 grass should be reported as depleted/empty!"
print("  [PASS] Visual depletion accurately distinguishes full troop stack (x10) from empty grass!")

print("\n====================================================")
print("TEST 5: 'Select a different unit' In-Game Warning Detection")
print("====================================================")
has_warning = engine._is_select_different_unit_warning(battle_img_720)
print(f"'Select a different unit' detected: {has_warning}")
assert has_warning, "Expected in-game 'Select a different unit' warning to be detected on battle screenshot!"
print("  [PASS] Red in-game alert correctly detected to avoid futile repetitive taps on depleted slots!")

print("\n====================================================")
print("TEST 6: Deployed Hero State Check")
print("====================================================")
is_prince_deployed = engine._is_hero_deployed(battle_img_720, 401)
print(f"Slot 3 (Minion Prince) deployed state: {is_prince_deployed}")
assert is_prince_deployed, "Minion Prince should be identified as already active/deployed on field!"
print("  [PASS] Deployed hero status correctly prevents tapping active heroes as new unit drops!")

print("\n====================================================")
print("TEST 7: Ice Hound False Positive Negative Filter")
print("====================================================")
all_names = [t["name"] for t in tray["troops"]] + [h["name"] for h in tray["heroes"]] + [s["name"] for s in tray["spells"]]
print("All detected names in tray:", all_names)
assert "Ice Hound" not in all_names, "Ice Hound should NEVER appear in this army!"
print("  [PASS] Broken Ice Hound check completely eliminated!")

print("\n====================================================")
print(">>> ALL VALIDATION CHECKS PASSED WITH 100% SUCCESS! <<<")
print("====================================================")

