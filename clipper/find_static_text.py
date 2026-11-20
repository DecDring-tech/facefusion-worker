"""Find burned-in text that stays put (TikTok text overlays) and print ffmpeg delogo boxes."""
import sys, cv2, numpy as np, easyocr
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from decaption_ocr import boxes
reader = easyocr.Reader(["en"], gpu=False, verbose=False)
for path in sys.argv[1:]:
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    found = []
    K = 14
    for k in range(K):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (k + 0.5) / K))
        ok, f = cap.read()
        if ok:
            found.append(boxes(reader, f))
    w = int(cap.get(3)); h = int(cap.get(4))
    # a pixel is "static text" if it is inside a box in >= 40% of the samples
    heat = np.zeros((h, w), np.float32)
    for bs in found:
        m = np.zeros((h, w), np.uint8)
        for x0, x1, y0, y1 in bs:
            m[y0:y1, x0:x1] = 1
        heat += m
    mask = (heat >= 0.4 * len(found)).astype(np.uint8)
    n_lab, lab, st, _ = cv2.connectedComponentsWithStats(mask)
    out = []
    for i in range(1, n_lab):
        x, y, bw, bh, area = st[i]
        if area < 200:
            continue
        p = 10
        x, y = max(1, x - p), max(1, y - p)
        bw, bh = min(w - x - 2, bw + 2 * p), min(h - y - 2, bh + 2 * p)
        out.append(f"delogo=x={x}:y={y}:w={bw}:h={bh}")
    print(path, ",".join(out) or "null", flush=True)
