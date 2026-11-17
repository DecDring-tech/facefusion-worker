#!/usr/bin/env python3
"""
screen_talking.py — screen a folder of downloaded clips for "talking to camera"
moments and rank them for clipping.

    python clipper/screen_talking.py dl/ --out screened.json

For every video: transcribe (faster-whisper), measure how much of the runtime
is speech, score the transcript for quotable lines, and detect whether a face
is on screen. Prints a ranked table and writes everything to JSON so the
clipper can take --start/--end straight from it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}

# words that tend to sit inside the lines these accounts clip
HOT = {
    "money", "rich", "broke", "poor", "work", "hard", "lazy", "discipline", "focus", "mindset",
    "dream", "goal", "win", "lose", "fight", "fear", "scared", "comfortable", "uncomfortable",
    "excuse", "excuses", "nobody", "no one", "cares", "alone", "god", "faith", "believe", "pray",
    "young", "years", "life", "future", "change", "quit", "never", "every", "day", "grind",
    "success", "fail", "failure", "prove", "haters", "doubt", "sacrifice", "pain", "truth",
    "honest", "respect", "loyal", "family", "mum", "dad", "brother", "lesson", "advice",
    "listen", "realise", "realize", "stop", "start", "wake", "chase", "bag", "hustle",
}


def probe_dur(path: Path) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0


def pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def face_share(path: Path, dur: float) -> float:
    """Fraction of sampled frames with a detectable frontal face."""
    try:
        import cv2
    except ImportError:
        return -1.0
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(path))
    hits = n = 0
    for k in range(8):
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * dur * (k + 0.5) / 8)
        ok, frame = cap.read()
        if not ok:
            continue
        n += 1
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (360, int(h * 360 / w)))
        if len(cas.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.15, 4, minSize=(36, 36))):
            hits += 1
    cap.release()
    return hits / n if n else 0.0


def score_text(text: str) -> float:
    words = re.findall(r"[a-z']+", text.lower())
    if not words:
        return 0.0
    hot = sum(1 for w in words if w in HOT)
    return hot / len(words) * 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default="screened.json")
    ap.add_argument("--model", default="small")
    ap.add_argument("--min-speech", type=float, default=0.45, help="min share of runtime that is speech")
    args = ap.parse_args()

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device="cpu", compute_type="int8")

    out_path = Path(args.out)
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    files = sorted(p for p in Path(args.folder).iterdir() if p.suffix.lower() in VIDEO_EXT)
    for i, f in enumerate(files, 1):
        if f.name in results:
            continue
        dur = probe_dur(f)
        if dur < 5:
            continue
        audio = pcm(f)
        segs, info = model.transcribe(audio, vad_filter=True, word_timestamps=True,
                                      vad_parameters={"min_silence_duration_ms": 400})
        segs = list(segs)
        speech = sum(s.end - s.start for s in segs)
        text = " ".join(s.text.strip() for s in segs)
        music_like = info.language_probability < 0.6 or (len(text.split()) / max(speech, 1)) < 1.2
        r = {
            "file": str(f), "duration": round(dur, 1), "speech_share": round(speech / dur, 2),
            "words": len(text.split()), "lang": info.language, "lang_p": round(info.language_probability, 2),
            "music_like": bool(music_like), "face_share": round(face_share(f, dur), 2),
            "hot": round(score_text(text), 1), "text": text,
            "segments": [{"s": round(s.start, 2), "e": round(s.end, 2), "t": s.text.strip()} for s in segs],
        }
        results[f.name] = r
        out_path.write_text(json.dumps(results, indent=1))
        print(f"[{i}/{len(files)}] {f.name} {dur:5.0f}s speech={r['speech_share']:.2f} face={r['face_share']:.2f} "
              f"hot={r['hot']:4.1f} {'MUSIC? ' if music_like else ''}{text[:90]}", flush=True)

    print("\n=== talking-to-camera candidates, best first ===")
    ranked = sorted(results.values(), key=lambda r: -(r["speech_share"] * 2 + r["face_share"] + r["hot"] / 10))
    for r in ranked:
        if r["speech_share"] < args.min_speech or r["music_like"] or r["face_share"] < 0.3:
            continue
        print(f"{Path(r['file']).stem}  {r['duration']:4.0f}s  speech={r['speech_share']:.2f} face={r['face_share']:.2f} "
              f"hot={r['hot']:4.1f}\n    {r['text'][:200]}")


if __name__ == "__main__":
    main()
