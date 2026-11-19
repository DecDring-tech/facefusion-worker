#!/usr/bin/env python3
"""
decaption_ocr.py — remove burned-in captions/watermarks from b-roll with a real text detector.

    python clipper/decaption_ocr.py out_dir in1.mp4 [in2.mp4 ...] [--every 3] [--verify]

Runs EasyOCR's CRAFT detector on every Nth frame, holds each detected box for the
frames around it, inpaints the union, and (with --verify) re-detects on the cleaned
output and deletes the clip if text still shows up. Prints one line per clip:
KEPT/DROPPED <name> <residual-ratio>.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

DW, DH = 288, 512  # detection resolution


def detector(threads: int):
    import torch
    torch.set_num_threads(threads)
    import easyocr
    return easyocr.Reader(["en"], gpu=False, verbose=False)


def boxes(reader, frame) -> list[tuple[int, int, int, int]]:
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (DW, DH))
    found, _ = reader.detect(small, text_threshold=0.4, low_text=0.25, link_threshold=0.3,
                             min_size=4, mag_ratio=1.5)
    sx, sy = w / DW, h / DH
    out = []
    for x0, x1, y0, y1 in found[0]:
        x0, x1, y0, y1 = int(x0 * sx), int(x1 * sx), int(y0 * sy), int(y1 * sy)
        if (x1 - x0) * (y1 - y0) > 0.15 * w * h:  # whole-frame false positives
            continue
        out.append((max(0, x0), min(w, x1), max(0, y0), min(h, y1)))
    return out


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
    if not frames:
        raise RuntimeError("no frames")
    h, w = frames[0].shape[:2]
    det = {i: boxes(reader, frames[i]) for i in range(0, len(frames), every)}
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{w}x{h}", "-r", f"{fps:.3f}", "-i", "-", "-an", "-c:v", "libx264",
                            "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p", str(dst)],
                           stdin=subprocess.PIPE)
    for i, f in enumerate(frames):
        mask = np.zeros((h, w), np.uint8)
        for j in range(i - hold, i + hold + 1):
            for x0, x1, y0, y1 in det.get(j, []):
                cv2.rectangle(mask, (x0 - pad, y0 - pad), (x1 + pad, y1 + pad), 255, -1)
        if mask.any():
            f = cv2.inpaint(f, mask, 9, cv2.INPAINT_TELEA)
        enc.stdin.write(f.tobytes())
    enc.stdin.close()
    enc.wait()


def residual(reader, path: Path, step: int = 6) -> float:
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    hits = tot = 0
    for i in range(0, n, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if not ok:
            break
        tot += 1
        if boxes(reader, f):
            hits += 1
    cap.release()
    return hits / tot if tot else 1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--every", type=int, default=3)
    ap.add_argument("--hold", type=int, default=3)
    ap.add_argument("--pad", type=int, default=8)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--max-residual", type=float, default=0.08)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    reader = detector(args.threads)
    for p in map(Path, args.inputs):
        dst = out / p.name
        if dst.exists():
            continue
        tmp = out / (p.stem + ".part.mp4")
        try:
            clean(reader, p, tmp, args.every, args.hold, args.pad)
        except Exception as e:  # noqa: BLE001
            print(f"FAILED {p.name} {e}", flush=True)
            tmp.unlink(missing_ok=True)
            continue
        r = residual(reader, tmp) if args.verify else 0.0
        if r > args.max_residual:
            tmp.unlink(missing_ok=True)
            print(f"DROPPED {p.name} {r:.2f}", flush=True)
        else:
            os.replace(tmp, dst)
            print(f"KEPT {p.name} {r:.2f}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
