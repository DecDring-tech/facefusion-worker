#!/usr/bin/env python3
"""
harvest_broll.py — turn downloaded luxury-edit videos into a caption-free b-roll library.

    python clipper/harvest_broll.py downloads/ library/ [--min-len 1.6] [--max-bright 115]

For every source video: find the cuts (scene change), split into shots, drop shots
that are short, bright, show a face, or are an outro card; strip burned-in
captions and corner marks with decaption.py; write each shot as its own mp4
and a labelled contact sheet so the keepers can be picked by eye.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def duration(path: Path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def scene_cuts(path: Path, thresh: float = 0.28) -> list[float]:
    p = run(["ffmpeg", "-nostdin", "-i", str(path), "-vf", f"select='gt(scene,{thresh})',showinfo", "-an", "-f", "null", "-"])
    return [float(x) for x in re.findall(r"pts_time:\s*([0-9.]+)", p.stderr)]


def shot_stats(path: Path, t0: float, t1: float, cas) -> dict:
    cap = cv2.VideoCapture(str(path))
    bright, faces, text, n = [], 0, [], 0
    for k in range(4):
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * (t0 + (t1 - t0) * (k + 0.5) / 4))
        ok, f = cap.read()
        if not ok:
            continue
        n += 1
        small = cv2.resize(f, (270, 480))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        bright.append(float(hsv[:, :, 2].mean()))
        if len(cas.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.15, 4, minSize=(30, 30))):
            faces += 1
        # share of bright low-saturation pixels: high = white card / big text block
        text.append(float(((hsv[:, :, 2] > 200) & (hsv[:, :, 1] < 40)).mean()))
    cap.release()
    return {"bright": np.mean(bright) if bright else 255, "faces": faces, "white": max(text) if text else 1, "n": n}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--min-len", type=float, default=1.6)
    ap.add_argument("--max-len", type=float, default=9.0)
    ap.add_argument("--max-bright", type=float, default=115, help="mean brightness ceiling (keeps the dark look)")
    ap.add_argument("--crop", type=float, default=0.04)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    index = {}
    files = sorted(p for p in Path(args.src).iterdir() if p.suffix.lower() in VIDEO_EXT)
    for vi, f in enumerate(files, 1):
        dur = duration(f)
        if dur < 3:
            continue
        cuts = [0.0] + scene_cuts(f) + [dur]
        kept = 0
        for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
            a, b = a + 0.08, b - 0.08  # trim the frames around the cut
            if b - a < args.min_len:
                continue
            if b - a > args.max_len:
                b = a + args.max_len
            st = shot_stats(f, a, b, cas)
            if st["n"] == 0 or st["bright"] > args.max_bright or st["faces"] >= 2 or st["white"] > 0.06:
                continue
            name = f"{f.stem}__s{i:02d}"
            raw = out / f"{name}.raw.mp4"
            clean = out / f"{name}.mp4"
            if not clean.exists():
                run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(f),
                     "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "14", str(raw)])
                run([sys.executable, str(HERE / "decaption.py"), str(raw), str(clean), "--crop", str(args.crop)])
                raw.unlink(missing_ok=True)
            index[name] = {"src": f.name, "start": round(a, 2), "end": round(b, 2), "bright": round(st["bright"], 1)}
            kept += 1
        print(f"[{vi}/{len(files)}] {f.name}: {len(cuts) - 1} shots, kept {kept}", flush=True)
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(index)} shots in {out}")


if __name__ == "__main__":
    main()
