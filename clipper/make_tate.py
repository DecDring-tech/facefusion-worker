#!/usr/bin/env python3
"""
make_tate.py — the classic "Tate edit": the speaker's voice only, never on screen, over dark car
b-roll that hard-cuts every 3 s, a dark music bed underneath the whole way, and one small
lowercase word at a time in the centre.

    python clipper/make_tate.py --speaker in.mp4 --broll dir --music bed.wav --out out.mp4 \
        [--voice voice.wav] [--talk-max 45] [--shot 3.0]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_clip as m  # noqa: E402
from make_cutaway import SR, read_audio, write_wav, rms  # noqa: E402

W, H, FPS = m.W, m.H, m.FPS


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speaker", required=True)
    ap.add_argument("--voice", help="clean voice wav on the tightened timeline (made with Demucs if absent)")
    ap.add_argument("--broll", required=True)
    ap.add_argument("--music", required=True, help="music bed (e.g. the reference's no-vocals stem)")
    ap.add_argument("--music-db", type=float, default=-2.0, help="music level vs the voice (dB)")
    ap.add_argument("--lead", type=float, default=0.4, help="music alone before the voice comes in (s)")
    ap.add_argument("--shot", type=float, default=3.0)
    ap.add_argument("--talk-max", type=float, default=45.0)
    ap.add_argument("--talk-end", type=float, default=None)
    ap.add_argument("--look", default="night")
    ap.add_argument("--min-bright", type=float, default=28, help="skip b-roll darker than this (HSV V mean)")
    ap.add_argument("--max-bright", type=float, default=110, help="skip daylight b-roll brighter than this")
    ap.add_argument("--font", default="Inter")
    ap.add_argument("--font-size", type=int, default=40)
    ap.add_argument("--lufs", type=float, default=-11.0)
    ap.add_argument("--sharpen", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    speaker = str(Path(args.speaker).resolve())
    sp = m.probe(speaker)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cache = out.parent / ".cache"
    cache.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="tate_", dir=str(cache)))

    words = m.transcribe(speaker, 0.0, sp["dur"], "small", cache)
    keep = m.build_keep_ranges(words, 0.0, sp["dur"], True)
    f = m.src_to_out(keep)
    for w in words:
        w.out_start, w.out_end = f(w.start), f(w.end)
    vpath = Path(args.voice) if args.voice else out.with_suffix(".voice.wav")
    if not vpath.exists():
        shutil.copy(m.render_audio(speaker, keep, tmp, False, True, words, 0.0), vpath)
    voice = read_audio(str(vpath))
    talk = min(sum(b - a for a, b in keep), len(voice) / SR)
    if args.talk_end:
        talk = min(talk, args.talk_end)
    elif talk > args.talk_max:  # end on a full stop (or the longest pause) before the limit
        ends = [w.out_end for w in words if w.text[-1] in ".?!" and 15 <= w.out_end <= args.talk_max]
        if not ends:
            cand = [(b.out_start - a.out_end, a.out_end) for a, b in zip(words, words[1:])
                    if 18 <= a.out_end <= args.talk_max]
            ends = [max(cand)[1]] if cand else [args.talk_max]
        talk = ends[-1] + 0.2
    words = [w for w in words if w.out_start < talk - 0.05]
    voice = voice[: int(talk * SR)]
    total = round((args.lead + talk + 0.9) * FPS) / FPS  # music rings out a beat after the last word
    print(f"talk {talk:.1f}s, video {total:.1f}s: " + " ".join(w.text for w in words))

    # --- audio: music bed the whole way, voice on top
    mus = read_audio(args.music)
    mus = mus[int(np.argmax(np.abs(mus).mean(1) > 0.01)):]  # start where the bed starts
    n = int(total * SR)
    bed = np.tile(mus, (n // len(mus) + 1, 1))[:n]
    vr = rms(voice[np.abs(voice).mean(1) > 0.01])
    bed *= vr * 10 ** (args.music_db / 20) / rms(bed)
    fi, fo = int(0.25 * SR), int(0.8 * SR)
    bed[:fi] *= np.linspace(0, 1, fi)[:, None]
    bed[-fo:] *= np.linspace(1, 0, fo)[:, None]
    mix = bed.copy()
    v0 = int(args.lead * SR)
    mix[v0:v0 + len(voice)] += voice[: n - v0]
    raw = tmp / "mix.wav"
    write_wav(raw, mix / max(1.0, float(np.abs(mix).max()) / 0.99))
    meas = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(raw), "-af",
                           f"loudnorm=I={args.lufs}:TP=-1.0:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    js = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    audio = tmp / "mix_ln.wav"
    m.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
           f"loudnorm=I={args.lufs}:TP=-1.0:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
           f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:"
           f"linear=true,alimiter=limit=0.9:attack=1:release=40", "-ar", str(SR), str(audio)])

    # --- video: a new dark car shot every --shot seconds, no repeats until the pool runs out
    import cv2

    def bright(p: str) -> float:
        cap = cv2.VideoCapture(p)
        v = []
        for q in (0.25, 0.5, 0.75):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) * q))
            ok, fr = cap.read()
            if ok:
                v.append(float(cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)[:, :, 2].mean()))
        cap.release()
        return float(np.mean(v)) if v else 0.0
    broll = sorted(str(p) for p in Path(args.broll).iterdir() if p.suffix.lower() in m.VIDEO_EXT)
    broll = [p for p in broll if args.min_bright <= bright(p) <= args.max_bright] or broll
    pool: list[str] = []
    pieces, t = [], 0.0
    while t < total - 1e-3:
        d = min(args.shot, total - t)
        if not pool:
            pool = broll[:]
            rng.shuffle(pool)
        src = pool.pop()
        dur = m.probe(src)["dur"]
        pieces.append(m.Shot("broll", t, t + d, src=src, src_start=rng.uniform(0, max(0.0, dur - d - 0.1))))
        t += d
    files = [m.render_piece(i, p, speaker, sp, args.look, tmp, random.Random(args.seed + i), None, 2,
                            0.0, 0.0, args.look) for i, p in enumerate(pieces)]
    (tmp / "concat.txt").write_text("".join(f"file '{Path(x).name}'\n" for x in files))
    video = tmp / "video.mp4"
    m.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "concat.txt"),
           "-t", f"{total:.3f}", "-c", "copy", str(video)])

    # --- captions: one small lowercase word at a time, dead centre
    lines = [f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,{args.font},{args.font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,0,2,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""]
    for i, w in enumerate(words):
        txt = re.sub(r"[^\w$£%'’-]", "", w.text).lower()
        if not txt:
            continue
        a = args.lead + w.out_start
        nxt = args.lead + words[i + 1].out_start if i + 1 < len(words) else a + 9
        b = min(nxt, a + max(0.5, w.out_end - w.out_start + 0.25)) if nxt - a > 1.2 else nxt
        if b - a < 0.06:
            continue
        lines.append(f"Dialogue: 0,{m.fmt_ass(a)},{m.fmt_ass(b)},T,,0,0,0,,{{\\blur0.4}}{txt}\n")
    ass = tmp / "captions.ass"
    ass.write_text("".join(lines), encoding="utf-8")

    m.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
           "-vf", f"unsharp=5:5:{args.sharpen}:5:5:0,ass={ass}", "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-maxrate", "20M", "-bufsize", "40M",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
           "-t", f"{total:.3f}", str(out)])
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"done → {out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
