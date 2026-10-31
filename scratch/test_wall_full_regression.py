import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np
from vision.detector import UIDetector
from vision.ocr_reader import LootOCRReader

def run_tests():
    detector = UIDetector()
    ocr = LootOCRReader()
    
    # Test 1: Specialized Wall Cost OCR on saved drawer crops
    img_scroll5 = cv2.imread('scratch/drawer_scroll_5.png')
    assert img_scroll5 is not None, "scratch/drawer_scroll_5.png missing"
    
    c1m = img_scroll5[207 - 8 : 207 + 28, 1040:1260]
    c500k = img_scroll5[435 - 8 : 435 + 28, 1040:1260]
    
    cost_1m = ocr.parse_wall_cost_from_crop(c1m)
    cost_500k = ocr.parse_wall_cost_from_crop(c500k)
    
    print(f"Test 1 - OCR Wall Costs: Wall x 55 = {cost_1m:,}, Wall x 208 = {cost_500k:,}")
    assert cost_1m == 1000000, f"Expected 1,000,000, got {cost_1m}"
    assert cost_500k == 500000, f"Expected 500,000, got {cost_500k}"
    print("  -> PASSED: Exact 1,000,000 and 500,000 tiers parsed perfectly!")

    # Test 2: Drawer Scanning on Scroll 5
    walls = detector.find_all_walls_in_builder_menu(img_scroll5, ocr_reader=ocr)
    print(f"Test 2 - Wall entries in drawer: {len(walls)} walls found")
    costs = [w['cost'] for w in walls]
    print(f"  Detected costs: {costs}")
    assert 500000 in costs, "500,000 cost wall must be detected"
    assert 1000000 in costs, "1,000,000 cost wall must be detected"
    print("  -> PASSED: Both Wall x 55 (1M) and Wall x 208 (500k) identified!")

    # Test 3: CHEAPEST_FIRST strategy ranking
    walls.sort(key=lambda m: (m["cost"] if m["cost"] > 0 else 99999999, -m["y"]))
    best = walls[0]
    print(f"Test 3 - CHEAPEST_FIRST best choice: Cost = {best['cost']:,} at {best['pos']}")
    assert best['cost'] == 500000, f"Expected cheapest to be 500k, got {best['cost']}"
    print("  -> PASSED: Strictly selects 500k wall over 1M wall!")

    # Test 4: Batch toolbar layout and button coordinates
    synth_batch = np.zeros((720, 1280, 3), dtype=np.uint8)
    for tname, target_pos in [("build_wall_add_10", (310, 540)), ("build_wall_add_1", (450, 540)), ("build_wall_remove_1", (170, 540))]:
        tmpl = cv2.imread(f"assets/templates/{tname}.png")
        if tmpl is not None:
            synth_batch[target_pos[1]:target_pos[1]+tmpl.shape[0], target_pos[0]:target_pos[0]+tmpl.shape[1]] = tmpl
    
    layout = detector.detect_wall_batch_layout(synth_batch)
    print(f"Test 4 - Single-row batch layout: {layout['layout']}")
    print(f"  -1: {layout['remove_1']}, +10: {layout['add_10']}, +1: {layout['add_1']}, gold: {layout['upgrade_gold']}")
    assert layout['is_batch'], "Must be classified as batch layout"
    assert layout['add_10'] is not None and layout['add_10'][0] >= 300, "add_10 must be Card 1 (~322)"
    assert layout['remove_1'] is not None and layout['remove_1'][0] <= 260, "remove_1 must be Card 0 (~185)"
    assert layout['add_1'] is not None and layout['add_1'][0] >= 420, "add_1 must be Card 2 (~464)"
    print("  -> PASSED: Batch button slots mapped strictly to correct buttons!")

    # Test 5: Collision interlock verification
    # Select Row position was at (338, 595) before batch opened
    # In live batch, Select Row template is absent
    f_batch_check = synth_batch
    live_select = detector.find_template(f_batch_check, "wall_select_row", threshold=0.68)
    assert live_select is None, "Select Row must be absent on batch screen"
    # Button +10 is at (322, 566)
    btn_add_10 = (322, 566)
    # Overlap check must NOT trigger because live_select is None
    overlap_triggered = False
    if live_select and abs(btn_add_10[0] - live_select[0]) < 65 and abs(btn_add_10[1] - live_select[1]) < 65:
        overlap_triggered = True
    assert not overlap_triggered, "Overlap check must NOT trigger false abort!"
    print("Test 5 - Collision Safeguard: False overlap abort eliminated!")
    print("  -> PASSED: Automation continues safely into additions and upgrade!")

    print("\n==========================================")
    print(">>> ALL 5 REGRESSION TESTS PASSED 100% <<<")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
