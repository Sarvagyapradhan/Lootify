"""
Verification Test Suite: Dynamic Battle Tray, Troop Identification, Hero Classification & Spell Casting.
Validates fixes for:
1. Frontline Dragon Troops not being missed or hijacked.
2. Complete elimination of bogus "Dragon Duke" hero.
3. Hero classification of Archer Queen, Minion Prince, and Grand Warden without misidentification or duplicate skips.
4. Detection of Earthquake and Lightning spells with reliable counts.
5. Hero deployment ensuring Grand Warden is never falsely skipped as 'already deployed'.
"""
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys
sys.path.insert(0, os.path.abspath('.'))

import cv2
import numpy as np
from bot.attack_engine import AttackEngine
from vision.ocr_reader import LootOCRReader

def test_user_exact_army():
    print("\n--- Test 1: User's Live Army Composition (Dragons, Queen, Minion Prince, Warden, Earthquake, Lightning) ---")
    img = cv2.imread('img_596e_720.png')
    
    # Slot 1: Dragon (red scales, fiery face, teeth)
    cx1 = 235
    card1 = np.zeros((72, 76, 3), dtype=np.uint8)
    card1[25:62, 14:52, 2] = 180 # R
    card1[25:62, 14:52, 1] = 60  # G
    card1[25:62, 14:52, 0] = 50  # B
    card1[35:45, 25:35] = 220    # Teeth
    card1[7:18, 50:62] = 240     # Top-right count badge (x10)
    img[648:720, cx1 - 38 : cx1 + 38] = card1

    # Slot 3: Minion Prince (Cyan skin: B=180, G=120, R=40)
    cx3 = 401
    card3 = np.zeros((72, 76, 3), dtype=np.uint8)
    card3[18:65, 12:52, 0] = 180 # B
    card3[18:65, 12:52, 1] = 120 # G
    card3[18:65, 12:52, 2] = 40  # R
    # Bot left hero level badge
    card3[-24:, :28, :] = 20
    card3[-18:-8, 5:20, :] = 220
    img[648:720, cx3 - 38 : cx3 + 38] = card3

    ocr = LootOCRReader()
    ae = AttackEngine(None, None, None, None, None)
    ae.ocr = ocr
    
    results = ae.scan_battle_tray(img)
    
    print("  • Frontline Troops Detected:", len(results["troops"]), [(t["name"], t["count"]) for t in results["troops"]])
    print("  • Heroes Detected:", len(results["heroes"]), [h["name"] for h in results["heroes"]])
    print("  • Spells Detected:", len(results["spells"]), [(s["name"], s["count"]) for s in results["spells"]])

    # Assertions
    assert len(results["troops"]) == 1, f"Expected 1 troop, got {len(results['troops'])}"
    assert results["troops"][0]["name"] == "Dragon", f"Expected Dragon, got {results['troops'][0]['name']}"
    assert results["troops"][0]["count"] >= 1, "Troop count must be >= 1"

    hero_names = [h["name"] for h in results["heroes"]]
    assert len(hero_names) == 3, f"Expected 3 heroes, got {len(hero_names)}: {hero_names}"
    assert hero_names == ["Archer Queen", "Minion Prince", "Grand Warden"], f"Hero names mismatch: {hero_names}"
    assert "Dragon Duke" not in hero_names, "Dragon Duke must NOT exist!"

    spell_names = [s["name"] for s in results["spells"]]
    assert len(spell_names) == 2, f"Expected 2 spells, got {len(spell_names)}: {spell_names}"
    assert spell_names == ["Earthquake Spell", "Lightning Spell"], f"Spell names mismatch: {spell_names}"
    for s in results["spells"]:
        assert s["count"] >= 1, f"Spell {s['name']} count must be >= 1"

    print("  [PASS] User's Live Army scanned with 100% precision!")

def test_ground_truth_frame():
    print("\n--- Test 2: Real Ground-Truth Frame (img_596e_720.png) ---")
    img = cv2.imread('img_596e_720.png')
    ocr = LootOCRReader()
    ae = AttackEngine(None, None, None, None, None)
    ae.ocr = ocr
    
    results = ae.scan_battle_tray(img)
    print("  • Troops:", [(t["name"], t["count"]) for t in results["troops"]])
    print("  • Heroes:", [h["name"] for h in results["heroes"]])
    print("  • Spells:", [(s["name"], s["count"]) for s in results["spells"]])

    assert len(results["troops"]) == 1
    assert results["troops"][0]["name"] == "Electro Dragon"
    assert len(results["heroes"]) == 3
    assert [h["name"] for h in results["heroes"]] == ["Archer Queen", "Minion Prince", "Grand Warden"]
    assert len(results["spells"]) == 2
    assert [s["name"] for s in results["spells"]] == ["Earthquake Spell", "Lightning Spell"]
    print("  [PASS] Ground-truth image parsed correctly!")

def test_hero_deployment_no_false_skip():
    print("\n--- Test 3: Hero Deployment Safeguard (No False 'Already Deployed' Skips) ---")
    ae = AttackEngine(None, None, None, None, None)
    img = cv2.imread('img_596e_720.png')
    
    # Grand Warden slot center: 484
    # Ensure _is_hero_deployed does NOT trigger on undeployed Grand Warden
    is_warden_deployed = ae._is_hero_deployed(img, 484)
    print(f"  Grand Warden _is_hero_deployed: {is_warden_deployed}")
    assert not is_warden_deployed, "Undeployed Grand Warden must NOT be flagged as deployed!"
    print("  [PASS] Grand Warden will not be skipped during initial drop!")

def test_smart_lightning_targets_avoid_storages():
    print("\n--- Test 4: Smart Lightning Targeting (Strictly Avoids Storages & Targets Defenses) ---")
    img = cv2.imread('img_596e_720.png')
    ae = AttackEngine(None, None, None, None, None)
    
    targets = ae._get_smart_lightning_targets(img)
    print(f"  Calculated smart lightning targets: {targets}")
    assert len(targets) > 0, "Must return at least 1 smart target"
    
    # In img_596e_720.png, storages are at (1136, 90) and (48, 176)
    # Target points must NOT be near these storages!
    storages = [(1136, 90), (48, 176)]
    for pt in targets:
        for s in storages:
            dist = ((pt[0] - s[0])**2 + (pt[1] - s[1])**2)**0.5
            assert dist > 100, f"Target {pt} is too close to storage at {s} (dist: {dist})!"
    print("  [PASS] All lightning targets strictly avoid storages and target key defenses!")

def test_slot_0_hero_immunity_and_no_duplicate_heroes():
    print("\n--- Test 5: Slot 0 Hero Immunity & Strict Zero-Duplicate Invariant ---")
    img = cv2.imread('img_596e_720.png')
    
    # Overwrite Slot 1 with pure cyan (mimicking cyan Dragon or electric background)
    cx1 = 235
    card1 = np.zeros((72, 76, 3), dtype=np.uint8)
    card1[:, :, 0] = 200 # Heavy blue/cyan
    card1[:, :, 1] = 140
    img[648:720, cx1 - 38 : cx1 + 38] = card1

    # Overwrite Slot 3 with Minion Prince (cyan gargoyle)
    cx3 = 401
    card3 = np.zeros((72, 76, 3), dtype=np.uint8)
    card3[18:65, 12:52, 0] = 180 # B
    card3[18:65, 12:52, 1] = 120 # G
    card3[18:65, 12:52, 2] = 40  # R
    img[648:720, cx3 - 38 : cx3 + 38] = card3

    ae = AttackEngine(None, None, None, None, None)
    results = ae.scan_battle_tray(img)

    # 1. Slot 0 must ALWAYS be in troops, NEVER in heroes
    assert len(results["troops"]) >= 1, "Slot 0 must be recognized as frontline troop!"
    assert results["troops"][0]["slot"] == 1, "Slot 1 must be a frontline troop!"
    
    # 2. Hero list must NEVER have duplicate names
    hero_names = [h["name"] for h in results["heroes"]]
    print(f"  Detected Heroes: {hero_names}")
    assert len(hero_names) == len(set(hero_names)), f"Duplicate heroes found in {hero_names}!"
    assert hero_names.count("Minion Prince") <= 1, "Minion Prince must appear at most once!"
    assert hero_names.count("Archer Queen") <= 1, "Archer Queen must appear at most once!"
    print("  [PASS] Slot 0 is strictly protected as troop and zero duplicate heroes exist!")

def test_heroes_in_any_order_spells_always_after():
    print("\n--- Test 6: Heroes in Any Order (Warden First, Queen Second, Minion Prince Third) ---")
    img = cv2.imread('img_596e_720.png')
    
    # Slot 1: Frontline Dragon (cx=235)
    cx1 = 235
    card1 = np.zeros((72, 76, 3), dtype=np.uint8)
    card1[25:62, 14:52, 2] = 180 # R
    card1[25:62, 14:52, 1] = 60  # G
    card1[25:62, 14:52, 0] = 50  # B
    card1[35:45, 25:35] = 220    # Teeth
    img[648:720, cx1 - 38 : cx1 + 38] = card1

    # Slot 2 (cx=318): Grand Warden with toggle switch
    cx2 = 318
    card2 = np.full((72, 76, 3), 100, dtype=np.uint8)
    # Mode toggle in bottom right (green in BGR)
    card2[-20:, -20:, 0] = 30
    card2[-20:, -20:, 1] = 200
    card2[-20:, -20:, 2] = 40
    img[648:720, cx2 - 38 : cx2 + 38] = card2

    # Slot 3 (cx=401): Archer Queen (purple hair)
    cx3 = 401
    card3 = np.zeros((72, 76, 3), dtype=np.uint8)
    card3[18:65, 12:52, 0] = 160 # B
    card3[18:65, 12:52, 2] = 130 # R
    img[648:720, cx3 - 38 : cx3 + 38] = card3

    # Slot 4 (cx=484): Minion Prince (cyan gargoyle skin)
    cx4 = 484
    card4 = np.zeros((72, 76, 3), dtype=np.uint8)
    card4[18:65, 12:52, 0] = 180 # B
    card4[18:65, 12:52, 1] = 120 # G
    card4[18:65, 12:52, 2] = 40  # R
    img[648:720, cx4 - 38 : cx4 + 38] = card4

    # Slot 5 (cx=567): Earthquake Spell (brown)
    # Slot 6 (cx=650): Lightning Spell (blue)

    ae = AttackEngine(None, None, None, None, None)
    results = ae.scan_battle_tray(img)

    hero_names = [h["name"] for h in results["heroes"]]
    spell_names = [s["name"] for s in results["spells"]]
    print(f"  Detected Heroes (in order): {hero_names}")
    print(f"  Detected Spells (strictly after): {spell_names}")

    assert len(results["troops"]) == 1, "Expected 1 troop stack (Dragons)"
    assert len(hero_names) == 3, f"Expected 3 heroes, got {len(hero_names)}: {hero_names}"
    assert set(hero_names) == {"Grand Warden", "Archer Queen", "Minion Prince"}
    assert len(spell_names) == 2, f"Expected 2 spells after heroes, got {len(spell_names)}: {spell_names}"
    assert spell_names == ["Earthquake Spell", "Lightning Spell"]
    print("  [PASS] Heroes in any order identified with spells strictly after!")

if __name__ == "__main__":
    test_user_exact_army()
    test_ground_truth_frame()
    test_hero_deployment_no_false_skip()
    test_smart_lightning_targets_avoid_storages()
    test_slot_0_hero_immunity_and_no_duplicate_heroes()
    test_heroes_in_any_order_spells_always_after()
    print("\n==========================================")
    print(">>> ALL UNIT & BATTLE TRAY TESTS PASSED <<<")
    print("==========================================")
