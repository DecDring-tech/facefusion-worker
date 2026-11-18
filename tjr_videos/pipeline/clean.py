"""Remove burned-in TikTok captions from each shot via temporal static-text mask + inpaint."""
import cv2, json, subprocess, sys, os, numpy as np
cat = json.load(open("shots/catalog.json"))
names = sys.argv[1:] or list(cat)
K_TOP = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 13))
K_DIL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
def candidate(frame, y0, y1):
    band = frame[y0:y1]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    mx = band.max(axis=2).astype(int); mn = band.min(axis=2).astype(int)
    white = (gray >= 200) & ((mx - mn) <= 50)
    top = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, K_TOP)
    thin = top >= 30
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    yellow = (hsv[..., 0] >= 15) & (hsv[..., 0] <= 35) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 150)
    blue = (hsv[..., 0] >= 85) & (hsv[..., 0] <= 115) & (hsv[..., 1] >= 70) & (hsv[..., 2] >= 140)
    return ((white & thin) | yellow | blue).astype(np.float32)
for n in names:
    cap = cv2.VideoCapture(f"src/{n}.mp4")
    fps = cap.get(cv2.CAP_PROP_FPS); W = int(cap.get(3)); H = int(cap.get(4))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frames.append(f)
    y0, y1 = int(H * 0.48), int(H * 0.84)
    out = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps}", "-i", "-",
                            "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", f"clean/{n}.mp4"], stdin=subprocess.PIPE)
    shots = cat[n]["shots"]
    bounds = [(int(round(s * fps)), int(round(e * fps))) for s, e in shots]
    bounds[-1] = (bounds[-1][0], len(frames))
    masks_dbg = []; cents = []
    for (a, b) in bounds:
        seg = frames[a:b]
        if not seg: continue
        acc = sum(candidate(f, y0, y1) for f in seg) / len(seg)
        static = (acc >= 0.45).astype(np.uint8) * 255
        # drop tiny specks, then grow to cover shadow/antialias
        static = cv2.morphologyEx(static, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        static = cv2.dilate(static, K_DIL, iterations=3)
        full = np.zeros((H, W), np.uint8); full[y0:y1] = static
        masks_dbg.append(full)
        ys = np.where(full.any(axis=1))[0]; cents.append(round(float(ys.mean()) / H, 3) if len(ys) else None)
        for f in seg:
            g = cv2.inpaint(f, full, 6, cv2.INPAINT_TELEA) if full.any() else f
            out.stdin.write(g.tobytes())
    out.stdin.close(); out.wait()
    cv2.imwrite(f"clean/{n}_mask.png", np.hstack([cv2.resize(m, (W // 3, H // 3)) for m in masks_dbg]))
    json.dump(cents, open(f"clean/{n}_cents.json", "w"))
    print(n, "done", len(frames), "frames", len(bounds), "shots", "caption y:", cents)
