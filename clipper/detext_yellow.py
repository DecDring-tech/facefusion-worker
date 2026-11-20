"""Inpaint only the saturated-yellow letter pixels inside a box (burned-in TikTok text over a face)."""
import sys, subprocess, cv2, numpy as np
src, dst, x, y, w, h = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
preview = len(sys.argv) > 7
cap = cv2.VideoCapture(src)
fps = cap.get(5); W = int(cap.get(3)); H = int(cap.get(4))
enc = None if preview else subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
    "-s", f"{W}x{H}", "-r", f"{fps:.3f}", "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
    "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", dst], stdin=subprocess.PIPE)
k = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    roi = f[y:y + h, x:x + w]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 38) & (hsv[:, :, 1] > 110) & (hsv[:, :, 2] > 150)).astype(np.uint8) * 255
    m = cv2.dilate(m, np.ones((5, 5), np.uint8), 2)
    f[y:y + h, x:x + w] = cv2.inpaint(roi, m, 5, cv2.INPAINT_TELEA)
    if preview and k == int(sys.argv[7]):
        cv2.imwrite(dst, np.hstack([cv2.resize(f, (W // 2, H // 2))]))
        break
    if enc:
        enc.stdin.write(f.tobytes())
    k += 1
if enc:
    enc.stdin.close(); enc.wait()
