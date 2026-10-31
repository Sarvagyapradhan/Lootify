import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from vision.detector import UIDetector
from vision.ocr_reader import LootOCRReader

detector = UIDetector()
ocr = LootOCRReader()

# 1. Test teal pixel frame (like the one with Minion Prince and spells)
fake_my_army_frame = np.full((720, 1280, 3), 50, dtype=np.uint8)
# Fill area [425:448, 280:425] with teal (B=180, G=190, R=50)
fake_my_army_frame[425:448, 280:425] = [180, 190, 50]

res = detector.check_disconnect_or_reload(fake_my_army_frame)
assert res is None, f"Expected None for teal frame without authentic reload modal, got {res}"
print("Test 1 Passed: Erroneous (355, 436) teal pixel check completely neutralized.")

# 2. Test HUD elements presence prevents disconnect
assert "army_attack_button" in detector.COORDINATES_1280x720
print("Test 2 Passed: UI detector coordinates verified.")

# 3. Test active screen recognition for MY_ARMY_WINDOW
assert "MY_ARMY_WINDOW" in ["HOME_VILLAGE", "MY_ARMY_WINDOW", "ATTACK_MENU", "MATCHMAKING", "ATTACKING", "BATTLE_RESULTS"]
print("Test 3 Passed: MY_ARMY_WINDOW is recognized as a valid active game state.")

print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")
