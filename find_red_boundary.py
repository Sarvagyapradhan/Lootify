import cv2
import numpy as np

p = r"C:\Users\sarva\.gemini\antigravity-ide\brain\3d0f3e62-0521-4442-babc-81868933e065\.tempmediaStorage\media_1791472630191.png"
img = cv2.imread(p)

b = img[:, :, 0]
g = img[:, :, 1]
r = img[:, :, 2]

# The red boundary line is distinctly red/orange: R > 150, G < 90, B < 90
red = (r > 150) & (g < 90) & (b < 90)
# exclude buttons and top text
red[:230, :260] = False
red[500:, :160] = False
red[640:, :] = False # exclude army tray

y_i, x_i = np.where(red)
print(f"Red line x: {x_i.min()}..{x_i.max()}, y: {y_i.min()}..{y_i.max()}")

# Let's inspect the 4 outer safe zones outside the red line:
# 1. Top Edge / Top Corner:
# Around y=80..130, x=500..780
# 2. Right Edge / Right Corner:
# Around x=1050..1220, y=280..450
# 3. Bottom Edge / Bottom Corner:
# Around y=580..630, x=500..780 (above the tray, below the red line)
# 4. Left Edge / Left Corner:
# Around x=60..180, y=280..450
print("Safe perimeter points outside red boundary:")
points = {
    "TOP_CORNER": (640, 95),
    "TOP_RIGHT_EDGE_1": (780, 140),
    "TOP_RIGHT_EDGE_2": (920, 200),
    "RIGHT_CORNER": (1140, 360),
    "BOTTOM_RIGHT_EDGE_1": (950, 480),
    "BOTTOM_RIGHT_EDGE_2": (800, 560),
    "BOTTOM_CORNER": (640, 615),
    "BOTTOM_LEFT_EDGE_1": (480, 560),
    "BOTTOM_LEFT_EDGE_2": (350, 490),
    "LEFT_CORNER": (140, 360),
    "TOP_LEFT_EDGE_1": (350, 210),
    "TOP_LEFT_EDGE_2": (480, 150),
}
for name, (x, y) in points.items():
    # Check if point is outside red:
    is_red = red[max(0, y-5):min(720, y+5), max(0, x-5):min(1280, x+5)].any()
    print(f"  {name}: ({x}, {y}) -> Near red line: {is_red}")
