#!/usr/bin/env python3
"""
strip_music.py — remove background music from finished clips, keeping only the voice.

    python clipper/strip_music.py out/markov_01.mp4 out/markov_02.mp4 ...
    python clipper/strip_music.py --inplace out/*.mp4

Runs Demucs (htdemucs, two stems) on each file's audio, keeps the vocal stem,
re-normalises loudness and re-muxes it under the untouched video stream.
Output goes next to the input as <name>_voice.mp4 unless --inplace.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-3000:] + "\n")
        raise SystemExit(f"failed: {cmd[0]}")


def isolate_voice(audio_in: Path, workdir: Path, model: str = "htdemucs_ft", passes: int = 2,
                  shifts: int = 2) -> Path:
    """Return a wav holding only the vocal stem of audio_in.
    Fine-tuned model + test-time shifts, run twice: the second pass cleans the bleed the first leaves."""
    cur = audio_in
    for i in range(passes):
        out = workdir / f"pass{i}"
        run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", model, "-d", "cpu",
             "--shifts", str(shifts), "--overlap", "0.5", "-o", str(out), str(cur)])
        cur = out / model / cur.stem / "vocals.wav"
    return cur


def speech_gate_filter(voice: Path, pad: float = 0.12, min_gap: float = 0.35) -> str:
    """ffmpeg audio filter that mutes everything between spoken words (residual music lives there)."""
    import os
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    import numpy as np
    from faster_whisper import WhisperModel
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(voice), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    segs, _ = WhisperModel("small", device="cpu", compute_type="int8").transcribe(
        audio, word_timestamps=True, vad_filter=True)
    spans = []
    for sg in segs:
        for w in sg.words or []:
            a, b = w.start - pad, w.end + pad
            if spans and a <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], b)
            else:
                spans.append([a, b])
    total = len(audio) / 16000
    gaps, t = [], 0.0
    for a, b in spans:
        if a - t >= min_gap:
            gaps.append((t, a))
        t = max(t, b)
    if total - t >= min_gap:
        gaps.append((t, total))
    if not gaps:
        return "anull"
    return ",".join(f"volume=enable='between(t,{a:.3f},{b:.3f})':volume=0" for a, b in gaps)


def strip(path: Path, inplace: bool, model: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="strip_", dir=str(path.parent)))
    try:
        wav = tmp / "mix.wav"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "2", "-ar", "44100", str(wav)])
        voice = isolate_voice(wav, tmp, model)
        gate = speech_gate_filter(voice)
        out = path if inplace else path.with_name(path.stem + "_voice" + path.suffix)
        tmp_out = tmp / "out.mp4"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-i", str(voice),
             "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
             "-af", f"{gate},highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=9",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(tmp_out)])
        shutil.move(str(tmp_out), str(out))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--inplace", action="store_true", help="overwrite the input files")
    ap.add_argument("--model", default="htdemucs_ft")
    args = ap.parse_args()
    for f in args.files:
        out = strip(Path(f), args.inplace, args.model)
        print(f"voice only → {out}", flush=True)


if __name__ == "__main__":
    main()
