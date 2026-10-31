import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import cv2
from core.adb_client import ADBController
from core.screen_capture import ScreenCapture
from vision.detector import UIDetector
from vision.ocr_reader import LootOCRReader

adb = ADBController()
sc = ScreenCapture(adb_controller=adb)
detector = UIDetector()
ocr = LootOCRReader()

print('Tapping Build button at (1210, 630)...')
adb.tap(1210, 630)
time.sleep(1.2)

frame = sc.get_frame((1280, 720))
cv2.imwrite('scratch/drawer_scroll_0.png', frame)

walls = detector.find_all_walls_in_builder_menu(frame, ocr_reader=ocr)
print(f"Scroll 0: found {len(walls)} walls: {[(w['cost'], w['pos']) for w in walls]}")

for i in range(1, 7):
    adb.swipe(1050, 480, 1050, 240, duration_ms=450)
    time.sleep(0.9)
    f = sc.get_frame((1280, 720))
    cv2.imwrite(f'scratch/drawer_scroll_{i}.png', f)
    walls = detector.find_all_walls_in_builder_menu(f, ocr_reader=ocr)
    print(f"Scroll {i}: found {len(walls)} walls: {[(w['cost'], w['pos']) for w in walls]}")

# Close build drawer safely
adb.tap_empty_grass()
print("Done. Build drawer closed.")
