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


def isolate_voice(audio_in: Path, workdir: Path, model: str = "htdemucs") -> Path:
    """Return a wav holding only the vocal stem of audio_in."""
    run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", model, "-d", "cpu",
         "-o", str(workdir), str(audio_in)])
    return workdir / model / audio_in.stem / "vocals.wav"


def strip(path: Path, inplace: bool, model: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="strip_", dir=str(path.parent)))
    try:
        wav = tmp / "mix.wav"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "2", "-ar", "44100", str(wav)])
        voice = isolate_voice(wav, tmp, model)
        out = path if inplace else path.with_name(path.stem + "_voice" + path.suffix)
        tmp_out = tmp / "out.mp4"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-i", str(voice),
             "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
             "-af", "highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=9",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(tmp_out)])
        shutil.move(str(tmp_out), str(out))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--inplace", action="store_true", help="overwrite the input files")
    ap.add_argument("--model", default="htdemucs")
    args = ap.parse_args()
    for f in args.files:
        out = strip(Path(f), args.inplace, args.model)
        print(f"voice only → {out}", flush=True)


if __name__ == "__main__":
    main()
