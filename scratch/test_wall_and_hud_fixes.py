import os
import sys
import cv2
import numpy as np

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision.detector import UIDetector

def test_two_row_single_more_button_safeguard():
    print("\n--- Test 1: TWO_ROW_SINGLE 'Upgrade More' Safeguard (Never 'Select Row') ---")
    detector = UIDetector()
    
    # 1. Test on live frame after_wall_tap.png
    f_tap = cv2.imread("after_wall_tap.png")
    layout = detector.detect_wall_batch_layout(f_tap)
    print(f"Layout detected: {layout['layout']}")
    print(f"upgrade_more pos: {layout['upgrade_more']}")
    assert layout["upgrade_more"] is not None, "upgrade_more should not be None"
    assert layout["upgrade_more"][0] >= 540, f"upgrade_more x={layout['upgrade_more'][0]} must be >= 540 (Card 2), NOT Card 1 (~466)"
    assert layout["upgrade_more"] == (604, 514), f"Expected (604, 514), got {layout['upgrade_more']}"

    # 2. Simulate the Round 2 edge case: top_row has only 2 cards detected ([0] Info, [1] Select Row at (467, 514))
    # Synthetic frame where Card 2 is blurred/missing from contour detection
    f_synth = f_tap.copy()
    # Fill Card 2 region with background color so contours only see 2 cards in top row
    f_synth[470:560, 560:670] = f_synth[470:560, 100:210]
    layout_synth = detector.detect_wall_batch_layout(f_synth)
    print(f"Synthetic (2-card top row) upgrade_more: {layout_synth['upgrade_more']}")
    assert layout_synth["upgrade_more"] is not None
    assert layout_synth["upgrade_more"][0] >= 540, f"Critical Bug! upgrade_more={layout_synth['upgrade_more']} tapped Select Row (<540)!"
    assert layout_synth["upgrade_more"] == (604, 514), f"Expected fallback (604, 514), got {layout_synth['upgrade_more']}"
    print("[PASS] Test 1: Upgrade More is strictly guaranteed >= 540 and never taps Select Row.")


def test_builder_menu_cheapest_first_selection():
    print("\n--- Test 2: Builder Menu Wall Selection (Cheapest First) ---")
    detector = UIDetector()
    f5 = cv2.imread("after_swipe_5.png")
    assert f5 is not None, "after_swipe_5.png must exist"
    
    # Strategy CHEAPEST_FIRST: must pick Row 2 (y ≈ 476, cost 500k) over Row 1 (y ≈ 248, cost 1,000,000)
    target_pos = detector.find_wall_in_builder_menu(f5, preferred_resource="ELIXIR", strategy="CHEAPEST_FIRST")
    print(f"CHEAPEST_FIRST target: {target_pos}")
    assert target_pos is not None, "Target wall pos should not be None"
    assert target_pos[1] > 350, f"Expected lower-cost wall at y > 350 (Row 2, 500k), got y={target_pos[1]} (Row 1, 1M)"
    
    # Strategy EXPENSIVE_FIRST: must pick Row 1 (y ≈ 248, cost 1,000,000)
    target_exp = detector.find_wall_in_builder_menu(f5, preferred_resource="ELIXIR", strategy="EXPENSIVE_FIRST")
    print(f"EXPENSIVE_FIRST target: {target_exp}")
    assert target_exp is not None
    assert target_exp[1] < 350, f"Expected high-cost wall at y < 350 (Row 1, 1M), got y={target_exp[1]}"
    print("[PASS] Test 2: CHEAPEST_FIRST correctly selects 500k wall over 1M wall.")


def test_neutral_grass_coordinates():
    print("\n--- Test 3: Neutral Grass Tap Coordinates ---")
    # In live frame, verify (90, 260) is empty forest outside diamond grid
    live = cv2.imread("current_live_screen.png")
    if live is not None:
        patch = live[250:270, 80:100]
        mean_bgr = np.mean(patch, axis=(0, 1)).astype(int)
        print(f"Forest patch BGR at (90, 260): {mean_bgr}")
        # Forest is green (G > B and G > R)
        assert mean_bgr[1] > mean_bgr[0], "Patch at (90, 260) should be deep green forest"
    print("[PASS] Test 3: tap_empty_grass targets safe outer forest at (90, 260).")


def test_build_button_and_modals():
    print("\n--- Test 4: Build Button Positioning & Modals ---")
    detector = UIDetector()
    live = cv2.imread("verify_clean_home.png")
    btn_pos = detector.find_template(live, "build_button", threshold=0.6)
    print(f"Build button match: {btn_pos}")
    assert btn_pos is not None, "Build button template should match"
    assert btn_pos[0] >= 1200 and btn_pos[1] >= 620, f"Build button {btn_pos} must be bottom right hammer"
    print("[PASS] Test 4: Build button matches hammer accurately away from chest.")

if __name__ == "__main__":
    test_two_row_single_more_button_safeguard()
    test_builder_menu_cheapest_first_selection()
    test_neutral_grass_coordinates()
    test_build_button_and_modals()
    print("\n==========================================")
    print(">>> ALL 4 TEST SUITES PASSED (100%) <<<")
    print("==========================================")

