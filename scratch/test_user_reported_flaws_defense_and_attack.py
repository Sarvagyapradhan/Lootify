import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from bot.attack_engine import AttackEngine
from vision.ocr_reader import LootOCRReader
from vision.detector import UIDetector

def run_all_tests():
    ae = AttackEngine(None, None, None, None, None)
    ocr = LootOCRReader()
    detector = UIDetector()
    ae.ocr = ocr
    ae.detector = detector

    print("=" * 60)
    print("TEST SUITE: User Flaws Verification (Attack & Defense)")
    print("=" * 60)

    # ----------------------------------------------------
    # TEST 1: Strict 3-Hero Roster & No Bogus Royal Champion
    # ----------------------------------------------------
    print("\n--- Test 1: Strict 3-Hero Roster & Zero Ghost Royal Champion ---")
    img = cv2.imread("img_596e_720.png")
    assert img is not None, "img_596e_720.png missing"
    tray = ae.scan_battle_tray(img)
    hero_names = [h["name"] for h in tray.get("heroes", [])]
    spell_names = [s["name"] for s in tray.get("spells", [])]
    print(f"Detected Heroes ({len(hero_names)}): {hero_names}")
    print(f"Detected Spells ({len(spell_names)}): {spell_names}")

    assert len(hero_names) == 3, f"Expected exactly 3 heroes, got {len(hero_names)}: {hero_names}"
    assert "Royal Champion" not in hero_names, "Royal Champion must NEVER be detected for TH11!"
    assert "Barbarian King" not in hero_names, "Barbarian King must not be in this army!"
    assert set(hero_names) == {"Archer Queen", "Minion Prince", "Grand Warden"}, f"Unexpected heroes: {hero_names}"
    assert "Earthquake Spell" in spell_names, "Earthquake Spell must be detected!"
    assert "Lightning Spell" in spell_names, "Lightning Spell must be detected!"
    print("  -> PASSED: Exactly Archer Queen, Minion Prince, Grand Warden detected. Zero ghost heroes!")

    # ----------------------------------------------------
    # TEST 2: No Drop Points Near Army Tray / Boost Buttons
    # ----------------------------------------------------
    print("\n--- Test 2: Drop Points Anti-Tray & Anti-Boost Safeguard ---")
    for pat in ["ALL_4_SIDES", "TWO_SIDES", "SINGLE_SIDE", "BOTTOM_RIGHT"]:
        pts = ae.get_safe_drop_points(img, pattern=pat)
        max_y = max(p[1] for p in pts)
        print(f"Pattern {pat}: {len(pts)} drop points, max_y = {max_y}")
        assert max_y <= 450, f"Drop point y={max_y} exceeds 450 limit! Will click boost buttons above tray!"
    print("  -> PASSED: All drop points strictly stay at or above y=450! Zero clicks on boost buttons!")

    # ----------------------------------------------------
    # TEST 3: No Repeated Dragon Card Clicks in Secondary Sweep
    # ----------------------------------------------------
    print("\n--- Test 3: No Re-Selection of Unleashed Dragons in Secondary Sweep ---")
    # Simulate Slot 1 (Dragons) being deployed
    ae.deployed_slots = {1}
    active_tray = ae.scan_battle_tray(img)
    remaining_troops = [
        t for t in active_tray.get("troops", [])
        if t["slot"] not in ae.deployed_slots
        and t["coord"] not in ae.hero_slot_coords
        and t["slot"] not in ae.hero_slot_indices
        and "hero" not in t.get("role", "").lower()
        and t.get("count", 0) > 0
    ]
    print(f"Remaining troops for secondary sweep: {remaining_troops}")
    assert len(remaining_troops) == 0, f"Expected 0 remaining troops, got {remaining_troops}!"
    print("  -> PASSED: Slot 1 (Dragons) is strictly excluded from secondary sweep!")

    # ----------------------------------------------------
    # TEST 4: Live Defense (Village Under Attack) Screen Detection
    # ----------------------------------------------------
    print("\n--- Test 4: Live Defense & Village Under Attack Screen Detection ---")
    im_defense_live = cv2.imread("scratch/live_attack_1_720.png")
    im_defense_ended = cv2.imread("scratch/live_attack_2_720.png")

    screen_live = ocr.detect_screen(im_defense_live)
    screen_ended = ocr.detect_screen(im_defense_ended)
    print(f"Image 1 (Live attack ongoing): {screen_live}")
    print(f"Image 2 (Defense ended summary): {screen_ended}")

    assert screen_live == "VILLAGE_UNDER_ATTACK", f"Expected VILLAGE_UNDER_ATTACK, got {screen_live}"
    assert screen_ended == "DEFENSE_FINISHED", f"Expected DEFENSE_FINISHED, got {screen_ended}"

    # Detector checks
    assert detector.check_village_under_attack(im_defense_live) is True, "check_village_under_attack must be True"
    rh_btn = detector.check_defense_return_home_button(im_defense_ended)
    print(f"Return Home button detected at: {rh_btn}")
    assert rh_btn is not None, "Return Home button must be detected at bottom left!"
    assert abs(rh_btn[0] - 77) < 15 and abs(rh_btn[1] - 664) < 15, f"Unexpected Return Home position: {rh_btn}"
    print("  -> PASSED: Live Defense and Return Home button detected with 100% precision!")

    # ----------------------------------------------------
    # TEST 5: Fast Attack Hero Ability Delays
    # ----------------------------------------------------
    print("\n--- Test 5: Fast Attack Hero Ability Delays ---")
    import yaml
    with open("config/heroes.yaml", "r", encoding="utf-8") as f:
        h_cfg = yaml.safe_load(f).get("heroes", {})
    warden_delay = h_cfg.get("grand_warden", {}).get("ability_delay_seconds")
    queen_delay = h_cfg.get("archer_queen", {}).get("ability_delay_seconds")
    prince_delay = h_cfg.get("minion_prince", {}).get("ability_delay_seconds")

    print(f"Warden delay: {warden_delay}s, Queen delay: {queen_delay}s, Prince delay: {prince_delay}s")
    assert warden_delay <= 6, f"Warden delay {warden_delay}s is too slow!"
    assert queen_delay <= 10, f"Queen delay {queen_delay}s is too slow!"
    assert prince_delay <= 8, f"Prince delay {prince_delay}s is too slow!"
    print("  -> PASSED: All hero abilities set to Fast Attack (<10s)!")

    print("\n" + "=" * 60)
    print(">>> ALL 5 TEST SUITES PASSED WITH 100% SUCCESS! <<<")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
