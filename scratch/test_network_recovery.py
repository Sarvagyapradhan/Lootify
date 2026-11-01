import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np
from vision.detector import UIDetector
from vision.ocr_reader import LootOCRReader

def main():
    print("=======================================================")
    print(">>> VERIFYING NETWORK RECOVERY & DIALOG DETECTION <<<")
    print("=======================================================")

    det = UIDetector()
    ocr = LootOCRReader()

    im_wifi = cv2.imread("scratch/net_wifi_720.png")
    im_dialog = cv2.imread("scratch/net_dialog_720.png")
    im_attack = cv2.imread("scratch/live_attack_1_720.png")

    assert im_wifi is not None, "scratch/net_wifi_720.png not found"
    assert im_dialog is not None, "scratch/net_dialog_720.png not found"

    # Test 1: Wi-Fi Poor Network Warning Detection
    wifi_on_wifi = det.check_poor_network_wifi_icon(im_wifi)
    wifi_on_dialog = det.check_poor_network_wifi_icon(im_dialog)
    wifi_on_attack = det.check_poor_network_wifi_icon(im_attack) if im_attack is not None else False

    print(f"Test 1 - Wi-Fi Icon Detection:")
    print(f"  net_wifi_720.png   -> {wifi_on_wifi} (Expected: True)")
    print(f"  net_dialog_720.png -> {wifi_on_dialog} (Expected: False)")
    print(f"  live_attack.png    -> {wifi_on_attack} (Expected: False)")
    assert wifi_on_wifi is True, "Failed to detect Wi-Fi warning icon on net_wifi_720.png!"
    assert wifi_on_dialog is False, "False positive Wi-Fi icon on net_dialog_720.png!"
    assert wifi_on_attack is False, "False positive Wi-Fi icon on live_attack.png!"

    # Test 2: 'Connection lost' Dialog Detection & 'TRY AGAIN' button coordinates
    dialog_on_dialog = det.check_connection_lost_dialog(im_dialog)
    dialog_on_wifi = det.check_connection_lost_dialog(im_wifi)
    dialog_on_attack = det.check_connection_lost_dialog(im_attack) if im_attack is not None else None

    print(f"\nTest 2 - Connection Lost Dialog Detection:")
    print(f"  net_dialog_720.png -> {dialog_on_dialog} (Expected: around (345, 464))")
    print(f"  net_wifi_720.png   -> {dialog_on_wifi} (Expected: None)")
    print(f"  live_attack.png    -> {dialog_on_attack} (Expected: None)")
    assert dialog_on_dialog is not None, "Failed to detect 'Connection lost' dialog on net_dialog_720.png!"
    assert abs(dialog_on_dialog[0] - 345) < 30 and abs(dialog_on_dialog[1] - 464) < 20, f"Incorrect TRY AGAIN coordinates: {dialog_on_dialog}"
    assert dialog_on_wifi is None, "False positive dialog on net_wifi_720.png!"
    assert dialog_on_attack is None, "False positive dialog on live_attack.png!"

    # Test 3: check_disconnect_or_reload unification
    reload_on_dialog = det.check_disconnect_or_reload(im_dialog)
    reload_on_wifi = det.check_disconnect_or_reload(im_wifi)
    print(f"\nTest 3 - check_disconnect_or_reload Unification:")
    print(f"  net_dialog_720.png -> {reload_on_dialog} (Expected: coords)")
    print(f"  net_wifi_720.png   -> {reload_on_wifi} (Expected: None)")
    assert reload_on_dialog is not None, "check_disconnect_or_reload failed on net_dialog_720.png!"
    assert reload_on_wifi is None, "check_disconnect_or_reload false positive on net_wifi_720.png!"

    # Test 4: Screen Classification (OCR detect_screen)
    screen_dialog = ocr.detect_screen(im_dialog)
    screen_wifi = ocr.detect_screen(im_wifi)
    print(f"\nTest 4 - Screen Classification:")
    print(f"  net_dialog_720.png -> {screen_dialog} (Expected: DISCONNECTED)")
    print(f"  net_wifi_720.png   -> {screen_wifi} (Expected: BATTLE_RESULTS)")
    assert screen_dialog == "DISCONNECTED", f"Expected DISCONNECTED for net_dialog_720, got {screen_dialog}"
    assert screen_wifi == "BATTLE_RESULTS", f"Expected BATTLE_RESULTS for net_wifi_720, got {screen_wifi}"

    # Test 5: Return Home Button Safeguard
    rh_dialog = det.check_return_home_button(im_dialog)
    rh_wifi = det.check_return_home_button(im_wifi)
    print(f"\nTest 5 - Return Home Safeguard:")
    print(f"  net_dialog_720.png -> {rh_dialog} (Expected: None, blocked by dialog)")
    print(f"  net_wifi_720.png   -> {rh_wifi} (Expected: around (635, 635))")
    assert rh_dialog is None, "Return Home must return None when connection lost dialog is open!"
    assert rh_wifi is not None, "Return Home button must be detected on Battle Results when no dialog is open!"

    print("\n=======================================================")
    print(">>> ALL 5 NETWORK RECOVERY & DIALOG TESTS PASSED! <<<")
    print("=======================================================")

if __name__ == "__main__":
    main()
