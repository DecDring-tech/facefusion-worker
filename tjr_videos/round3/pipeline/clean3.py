"""Cut a segment from a 1080x1920 source, strip burned-in captions (static thin white/yellow/blue text), write clean segment.
usage: clean3.py out.mp4 src.mp4 start end [band_top band_bottom]"""
import cv2, subprocess, sys, numpy as np
out, src, s, e = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
bt, bb = (float(sys.argv[5]), float(sys.argv[6])) if len(sys.argv) > 6 else (0.40, 0.86)
OPEN = int(sys.argv[7]) if len(sys.argv) > 7 else 2   # min stroke width kept (px); 5 ignores thin chain links
K_TOP = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)); K_DIL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
def cand(frame, y0, y1):
    band = frame[y0:y1]; gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    mx = band.max(axis=2).astype(int); mn = band.min(axis=2).astype(int)
    white = (gray >= 195) & ((mx - mn) <= 55)
    thin = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, K_TOP) >= 30
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    gthin = cv2.morphologyEx(hsv[..., 1], cv2.MORPH_TOPHAT, K_TOP) >= 40
    yellow = (hsv[..., 0] >= 15) & (hsv[..., 0] <= 35) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 150)
    blue = (hsv[..., 0] >= 85) & (hsv[..., 0] <= 115) & (hsv[..., 1] >= 70) & (hsv[..., 2] >= 140)
    green = (hsv[..., 0] >= 40) & (hsv[..., 0] <= 80) & (hsv[..., 1] >= 120) & (hsv[..., 2] >= 120)
    text = ((white & thin) | (yellow & thin) | (blue & thin) | (green & (thin | gthin))).astype(np.uint8)
    near = cv2.dilate(text, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) > 0
    dark = (gray <= 70) & (cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, K_TOP) >= 40) & near   # only the outline hugging the text
    return ((text > 0) | dark).astype(np.float32)
# decode frames via ffmpeg (hevc sources), scaled to 1080x1920 cover
W, H = 1080, 1920
p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{s:.3f}", "-i", src, "-t", f"{e - s:.3f}", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                      "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
frames = []
while True:
    buf = p.stdout.read(W * H * 3)
    if len(buf) < W * H * 3: break
    frames.append(np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy())
p.wait()
y0, y1 = int(H * bt), int(H * bb)
# word-by-word captions change every few frames: use a short temporal window instead of the whole segment
n = len(frames); win = 8
masks = [cand(f, y0, y1) for f in frames]
o = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
                      "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
for i, f in enumerate(frames):
    a, b = max(0, i - win), min(n, i + win + 1)
    acc = sum(masks[a:b]) / (b - a)
    m = (acc >= 0.5).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((OPEN, OPEN), np.uint8)); m = cv2.dilate(m, K_DIL, iterations=2)
    full = np.zeros((H, W), np.uint8); full[y0:y1] = m
    g = cv2.inpaint(f, full, 7, cv2.INPAINT_TELEA) if full.any() else f
    o.stdin.write(g.tobytes())
o.stdin.close(); o.wait()
print(out, n, "frames")
