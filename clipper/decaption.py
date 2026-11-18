#!/usr/bin/env python3
"""
decaption.py — remove burned-in captions and corner watermarks from a clip.

    python clipper/decaption.py in.mp4 out.mp4 [--band 0.30 0.70] [--crop 0.06]

Captions on these edits are white text in the middle band of a dark frame.
Each frame: threshold bright, low-saturation pixels inside the band, grow the
mask a little, inpaint. Corner watermarks (TikTok logo / @handle) are removed
by cropping the border and scaling back up.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import cv2
import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--band", type=float, nargs=2, default=(0.28, 0.72), help="vertical band holding captions")
    ap.add_argument("--crop", type=float, default=0.07, help="border fraction to crop (watermarks)")
    ap.add_argument("--thresh", type=int, default=170, help="min brightness of caption pixels")
    ap.add_argument("--maxsat", type=int, default=70, help="max saturation of caption pixels")
    ap.add_argument("--grow", type=int, default=7)
    ap.add_argument("--radius", type=int, default=6)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.inp)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cx, cy = int(w * args.crop), int(h * args.crop)
    ow, oh = w - 2 * cx, h - 2 * cy
    y0, y1 = int(oh * args.band[0]), int(oh * args.band[1])
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{ow}x{oh}", "-r", f"{fps:.3f}", "-i", "-", "-an",
                            "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p", args.out],
                           stdin=subprocess.PIPE)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (args.grow, args.grow))
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = frame[cy:cy + oh, cx:cx + ow]
        band = frame[y0:y1]
        hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
        mask = ((hsv[:, :, 2] >= args.thresh) & (hsv[:, :, 1] <= args.maxsat)).astype(np.uint8) * 255
        # text strokes are thin: drop big bright blobs (headlights, sky) by size
        num, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        keep = np.zeros_like(mask)
        for i in range(1, num):
            x, y, bw, bh, area = stats[i]
            if 2 <= bh <= oh * 0.06 and area < oh * ow * 0.004:
                keep[lab == i] = 255
        keep = cv2.dilate(keep, kernel)
        if keep.any():
            band = cv2.inpaint(band, keep, args.radius, cv2.INPAINT_TELEA)
            frame[y0:y1] = band
        enc.stdin.write(frame.tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    print(f"{n} frames → {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
