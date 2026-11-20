#!/usr/bin/env python3
"""
make_cutaway.py — talking head interrupted by short b-roll cutaways, copied from a reference edit.

Structure (all timings copied from the reference): the speaker talks; at a word gap the
speaker is cut out completely and ~1.8 s of b-roll plays (two shots, cut on the sound's
transient) with the reference's cutaway sound and NO speaker audio; then the speaker
resumes exactly where he stopped. Repeats. A short sound hit plays at 0 s, the cutaway
sound tails a moment into each return, and after the second cutaway the reference's soft
bed runs under the speaker. Captions: one word at a time, big Anton caps at the top,
only while the speaker is on screen.

    python clipper/make_cutaway.py --speaker in.mp4 --voice voice.wav --broll dir \
        --ref reference.mp4 --out out.mp4 [--talk-max 23] [--crop-top 0.2]
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
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_clip as m  # noqa: E402

SR = 48000
W, H = m.W, m.H


def read_audio(path: str, start: float = 0.0, dur: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-i", path]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def write_wav(path: Path, x: np.ndarray) -> None:
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def rms(x: np.ndarray) -> float:
    return float(np.sqrt((x ** 2).mean()) + 1e-9)


def onset(x: np.ndarray, lo: float, hi: float) -> float:
    """Strongest energy jump between lo and hi seconds (the beat to cut on)."""
    mono = x.mean(1)
    hop = SR // 100
    e = np.array([rms(mono[i:i + hop]) for i in range(0, len(mono) - hop, hop)])
    d = np.diff(np.log(e + 1e-6))
    a, b = int(lo * 100), min(len(d), int(hi * 100))
    if b <= a:
        return (lo + hi) / 2
    return (a + int(np.argmax(d[a:b])) + 1) / 100


def cut_points(words: list[m.Word], total: float, first: float, gap_lo: float, gap_hi: float,
               tail_keep: float, rng: random.Random) -> list[float]:
    """Talk-timeline times to cut away, each in the middle of a pause between words."""
    gaps = [((a.out_end + b.out_start) / 2, b.out_start - a.out_end) for a, b in zip(words, words[1:])]
    cuts, target = [], first
    while target < total - tail_keep:
        near = [g for g in gaps if abs(g[0] - target) <= 0.9 and g[0] < total - tail_keep]
        if not near:
            near = [g for g in gaps if abs(g[0] - target) <= 1.6 and g[0] < total - tail_keep]
        if not near:
            break
        t = max(near, key=lambda g: g[1] - abs(g[0] - target) * 0.08)[0]  # prefer real pauses
        if cuts and t - cuts[-1] < 2.5:
            break
        cuts.append(t)
        target = t + rng.uniform(gap_lo, gap_hi)
    return cuts


def caption_size(word: str, base: int, max_w: int) -> int:
    return int(min(base, max_w / (0.36 * max(1, len(word)))))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speaker", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=999.0)
    ap.add_argument("--voice", required=True, help="clean voice wav on the tightened talk timeline")
    ap.add_argument("--broll", required=True)
    ap.add_argument("--ref", required=True, help="reference edit whose cutaway sound/timing is copied")
    ap.add_argument("--ref-cuts", default="5.35:7.20,11.05:12.90", help="cutaway windows in the reference (s)")
    ap.add_argument("--ref-hit", default="0.05:0.50", help="the sound hit at the very start of the reference")
    ap.add_argument("--ref-bed", default="13.0:49.5", help="soft bed that runs under the speaker later on")
    ap.add_argument("--ref-stem", required=True, help="reference no-vocals stem (for the hit and the bed)")
    ap.add_argument("--ref-voc", required=True, help="reference vocals stem (to match levels)")
    ap.add_argument("--first-cut", type=float, default=5.4)
    ap.add_argument("--talk-max", type=float, default=23.0)
    ap.add_argument("--talk-end", type=float, default=None, help="end the talk exactly here (talk timeline)")
    ap.add_argument("--tail", type=float, default=0.30, help="how far the cutaway sound runs into the return")
    ap.add_argument("--out", required=True)
    ap.add_argument("--look", default="noir")
    ap.add_argument("--broll-look", default="lift")
    ap.add_argument("--crop-top", type=float, default=0.0)
    ap.add_argument("--crop-bottom", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--font", default="Anton")
    ap.add_argument("--font-size", type=int, default=330)
    ap.add_argument("--caption-top", type=int, default=260)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    speaker = str(Path(args.speaker).resolve())
    sp = m.probe(speaker)
    end = min(args.end, sp["dur"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cache = out.parent / ".cache"
    cache.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="cut_", dir=str(cache)))

    words = m.transcribe(speaker, args.start, end, "small", cache)
    keep = m.build_keep_ranges(words, args.start, end, True)
    f = m.src_to_out(keep)
    for w in words:
        w.out_start, w.out_end = f(w.start), f(w.end)
    voice = read_audio(args.voice)
    talk_total = min(sum(b - a for a, b in keep), len(voice) / SR)

    # trim the talk to a sentence end before talk-max (or exactly at --talk-end)
    if args.talk_end:
        talk_total = min(talk_total, args.talk_end)
    elif talk_total > args.talk_max:
        ends = [w.out_end for w in words if w.text[-1] in ".?!" and 12 <= w.out_end <= args.talk_max + 0.5]
        if not ends:  # transcripts without full stops: take the longest pause before the limit
            cand = [(b.out_start - a.out_end, a.out_end) for a, b in zip(words, words[1:])
                    if 15 <= a.out_end <= args.talk_max + 0.5]
            ends = [max(cand)[1]] if cand else [args.talk_max]
        talk_total = ends[-1] + 0.25
    words = [w for w in words if w.out_start < talk_total - 0.05]
    voice = voice[: int(talk_total * SR)]
    print(f"talk {talk_total:.1f}s: " + " ".join(w.text for w in words))

    cuts = cut_points(words, talk_total, args.first_cut, 3.9, 5.2, 2.6, rng)
    ref_windows = [tuple(map(float, c.split(":"))) for c in args.ref_cuts.split(",")]
    print("cut away at", [round(c, 2) for c in cuts])

    # --- reference audio, level-matched so our voice sits where the reference voice sat
    ref_voc = read_audio(args.ref_voc)
    g = rms(voice[voice.std(1) > 0] if voice.size else voice) / rms(ref_voc[np.abs(ref_voc).mean(1) > 0.01])
    snippets = []
    for a, b in ref_windows:
        x = read_audio(args.ref, a, (b - a) + args.tail) * g
        snippets.append(x)
    ha, hb = map(float, args.ref_hit.split(":"))
    hit = read_audio(args.ref_stem, ha, hb - ha) * g
    ba, bb = map(float, args.ref_bed.split(":"))
    bed = read_audio(args.ref_stem, ba, bb - ba) * g

    # --- timeline: talk / cutaway / talk / ...
    segs = []  # (kind, out_start, out_end, talk_start or snippet index)
    t_out, t_talk = 0.0, 0.0
    for i, c in enumerate(cuts + [talk_total]):
        segs.append(("talk", t_out, t_out + (c - t_talk), t_talk))
        t_out += c - t_talk
        t_talk = c
        if c < talk_total:
            sn = i % len(snippets)
            d = (ref_windows[sn][1] - ref_windows[sn][0])
            segs.append(("cut", t_out, t_out + d, sn))
            t_out += d
    total = t_out

    # --- audio
    mix = np.zeros((int(total * SR) + SR, 2), np.float32)
    for kind, o0, o1, ref in segs:
        i0 = int(o0 * SR)
        if kind == "talk":
            v = voice[int(ref * SR): int((ref + (o1 - o0)) * SR)]
            mix[i0:i0 + len(v)] += v
        else:
            x = snippets[ref].copy()
            d = int((o1 - o0) * SR)
            if len(x) > d:  # fade the tail that runs into the return
                fade = np.linspace(1, 0, len(x) - d)[:, None]
                x[d:] *= fade
            mix[i0:i0 + len(x)] += x[: len(mix) - i0]
    mix[: len(hit)] += hit
    cut_segs = [s for s in segs if s[0] == "cut"]
    if len(cut_segs) >= 2:  # the soft bed comes in after the second cutaway, as in the reference
        b0 = int(cut_segs[1][2] * SR)
        n = len(mix) - b0
        reps = np.tile(bed, (n // max(1, len(bed)) + 1, 1))[:n]
        for kind, o0, o1, _ in segs:  # bed only under the talk, not over the cutaway sound
            if kind == "cut":
                a, b = max(b0, int(o0 * SR)), int(o1 * SR)
                if b > a:
                    reps[a - b0:b - b0] = 0
        mix[b0:] += reps
    mix = mix[: int(total * SR)]
    raw = tmp / "mix.wav"
    write_wav(raw, mix)
    audio = tmp / "mix_ln.wav"
    m.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", "alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11",
           "-ar", str(SR), str(audio)])

    # --- video pieces
    centre = m.detect_face_center(speaker, args.start, end)
    broll = sorted(str(p) for p in Path(args.broll).iterdir() if p.suffix.lower() in m.VIDEO_EXT)
    ranked = sorted(broll, key=lambda p: -m.motion_score(p))
    def bright(p: str) -> float:
        import cv2
        cap = cv2.VideoCapture(p)
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) * 0.5))
        ok, fr = cap.read()
        cap.release()
        return float(cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)[:, :, 2].mean()) if ok else 0.0
    ranked = [p for p in ranked if bright(p) >= 22] or ranked
    pool = ranked[: max(8, len(ranked) * 2 // 3)]
    rng.shuffle(pool)
    punches = [1.0, 1.12, 1.0, 1.18, 1.06, 1.12]
    pieces: list[m.Shot] = []
    face_i = 0
    for kind, o0, o1, ref in segs:
        if kind == "talk":
            # talk timeline [ref, ref+len) -> source pieces through the keep ranges
            sh = m.Shot("face", ref, ref + (o1 - o0), punch=punches[face_i % len(punches)])
            face_i += 1
            for p in m.split_by_keep([sh], keep):
                pieces.append(p)
        else:
            x = snippets[ref]
            d = o1 - o0
            c = onset(x[: int(d * SR)], 0.55, d - 0.55)
            for a, b in ((0.0, c), (c, d)):
                f = pool.pop() if pool else rng.choice(ranked)
                dur = m.probe(f)["dur"]
                pieces.append(m.Shot("broll", a, b, src=f, src_start=rng.uniform(0, max(0.0, dur - (b - a) - 0.1))))
    threads = 2
    files = []
    for i, p in enumerate(pieces):
        files.append(m.render_piece(i, p, speaker, sp, args.look, tmp, random.Random(args.seed + i), centre,
                                    threads, args.crop_top, args.crop_bottom, args.broll_look))
    lst = tmp / "concat.txt"
    lst.write_text("".join(f"file '{Path(x).name}'\n" for x in files))
    video = tmp / "video.mp4"
    m.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video)])

    # --- captions: one word, big Anton caps at the top, only while he's on screen
    talks = [s for s in segs if s[0] == "talk"]
    def to_out(t: float) -> float:
        for _, o0, o1, ref in talks:
            if ref <= t < ref + (o1 - o0) + 1e-6:
                return o0 + (t - ref)
        return talks[-1][2]
    def seg_end(t: float) -> float:
        for _, o0, o1, ref in talks:
            if ref <= t < ref + (o1 - o0) + 1e-6:
                return o1
        return total
    lines = [f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,{args.font},{args.font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,1,3,5,8,40,40,{args.caption_top},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""]
    for i, w in enumerate(words):
        txt = re.sub(r"[^\w$£%'’,.-]", "", w.text).strip(".,").upper()
        if not txt:
            continue
        a = to_out(w.out_start)
        nxt = to_out(words[i + 1].out_start) if i + 1 < len(words) else a + 0.6
        b = min(seg_end(w.out_start), nxt if nxt > a + 0.04 else a + 0.12)
        size = caption_size(txt, args.font_size, W - 120)
        lines.append(f"Dialogue: 0,{m.fmt_ass(a)},{m.fmt_ass(b)},T,,0,0,0,,{{\\fs{size}\\blur0.6}}{txt}\n")
    ass = tmp / "captions.ass"
    ass.write_text("".join(lines), encoding="utf-8")

    m.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio), "-vf", f"ass={ass}",
           "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-maxrate", "12M", "-bufsize", "24M",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{total:.3f}", str(out)])
    out.with_suffix(".plan.json").write_text(json.dumps({
        "speaker": speaker, "talk": talk_total, "total": total, "cuts": cuts,
        "segments": [list(s) for s in segs]}, indent=1))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"done → {out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
