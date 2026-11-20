#!/usr/bin/env python3
"""
detext_letters.py — erase burned-in captions from b-roll by repainting ONLY the letter strokes.

    python clipper/detext_letters.py out_dir in1.mp4 [in2.mp4 ...] [--every 2] [--hold 2]

EasyOCR's detector finds where text is (every Nth frame, held for a few frames around it);
inside those boxes only thin bright strokes (white top-hat) and their outline are masked and
inpainted with a tiny radius, so there is never a blurred rectangle — the background inside
the box is left untouched.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decaption_ocr import boxes, detector  # noqa: E402


def letter_mask(frame: np.ndarray, rects: list[tuple[int, int, int, int]], pad: int) -> np.ndarray:
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = np.zeros((h, w), np.uint8)
    for x0, x1, y0, y1 in rects:
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
        roi = gray[y0:y1, x0:x1]
        if roi.size == 0:
            continue
        k = max(9, int(min(41, (y1 - y0) * 0.6)) | 1)
        th = cv2.morphologyEx(roi, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        m = ((th > 45) & (roi > 120)).astype(np.uint8)
        mask[y0:y1, x0:x1] |= m
    # grow over the drop shadow / outline that TikTok text carries (offset down-right)
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    mask = mask | np.roll(np.roll(mask, 3, 0), 2, 1)
    return mask * 255


def clean(reader, src: Path, dst: Path, every: int, hold: int, pad: int) -> None:
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    h, w = frames[0].shape[:2]
    det = {i: boxes(reader, frames[i]) for i in range(0, len(frames), every)}
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{w}x{h}", "-r", f"{fps:.3f}", "-i", "-", "-an", "-c:v", "libx264",
                            "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p", str(dst)], stdin=subprocess.PIPE)
    for i, f in enumerate(frames):
        rects = [r for j in range(i - hold, i + hold + 1) for r in det.get(j, [])]
        if rects:
            m = letter_mask(f, rects, pad)
            if m.any():
                f = cv2.inpaint(f, m, 6, cv2.INPAINT_TELEA)
        enc.stdin.write(f.tobytes())
    enc.stdin.close()
    enc.wait()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--every", type=int, default=2)
    ap.add_argument("--hold", type=int, default=2)
    ap.add_argument("--pad", type=int, default=6)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    reader = detector(args.threads)
    for p in map(Path, args.inputs):
        dst = out / p.name
        if dst.exists():
            continue
        clean(reader, p, dst, args.every, args.hold, args.pad)
        print(f"CLEANED {p.name}", flush=True)


if __name__ == "__main__":
    main()
