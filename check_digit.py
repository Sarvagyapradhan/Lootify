import cv2

img = cv2.imread('step3_after_attack_tap.png')
g_crop = img[95:125, 60:240]
b, g, r = cv2.split(g_crop)
mask = (r > 190) & (g > 180) & (b > 140)
thresh = (mask * 255).astype('uint8')
d3 = thresh[7:22, 9:20]

print("Matching extracted '3' against templates 0..9:")
for i in range(10):
    tmpl = cv2.imread(f'assets/digits/{i}.png', 0)
    th, tw = tmpl.shape
    rz = cv2.resize(tmpl, (max(1, int(tw * 15 / th)), 15))
    if d3.shape[1] < rz.shape[1]:
        ch = cv2.resize(d3, (rz.shape[1], 15))
    else:
        ch = d3
    res = cv2.matchTemplate(ch, rz, cv2.TM_CCOEFF_NORMED)
    print(f"Digit {i}: score = {cv2.minMaxLoc(res)[1]:.4f}")
