#!/usr/bin/env python3
"""
make_voiceover.py — the cutaway edit (make_cutaway.py) with the speaker talking straight through.

The speaker's voice never stops. At the reference's cut times the picture flicks to ~1.8 s of
b-roll (two shots, cut on the reference sound's transient) while the reference's cutaway sound
plays under the voice, then back to the speaker. The reference's opening sound hits at 0 s.
Captions: 2–3 words at a time, big rough white caps that sit BEHIND the speaker's head (person
segmentation), and over the b-roll as normal.

    python clipper/make_voiceover.py --speaker in.mp4 --broll dir --ref reference.mp4 \
        --ref-stem no_vocals.wav --ref-voc vocals.wav --out out.mp4 [--voice voice.wav]
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
from make_cutaway import SR, read_audio, write_wav, rms, onset  # noqa: E402

W, H, FPS = m.W, m.H, m.FPS


def cut_times(words: list[m.Word], total: float, first: float, d: float, gap_lo: float, gap_hi: float,
              tail_keep: float, rng: random.Random) -> list[float]:
    """Output times to flick to b-roll, each on a word boundary near the reference's rhythm."""
    bounds = [((a.out_end + b.out_start) / 2, b.out_start - a.out_end) for a, b in zip(words, words[1:])]
    cuts, target = [], first
    while target + d < total - tail_keep:
        near = [g for g in bounds if abs(g[0] - target) <= 0.7 and g[0] + d < total - tail_keep]
        if not near:
            break
        t = max(near, key=lambda g: g[1] - abs(g[0] - target) * 0.1)[0]
        cuts.append(t)
        target = t + d + rng.uniform(gap_lo, gap_hi)
    return cuts


def chunks(words: list[m.Word], maxw: int = 3, maxc: int = 13) -> list[list[m.Word]]:
    out, cur = [], []
    for w in words:
        t = clean(w.text)
        if not t:
            continue
        if cur and (len(cur) >= maxw or len(" ".join(clean(x.text) for x in cur + [w])) > maxc
                    or w.out_start - cur[-1].out_end > 0.35):
            out.append(cur)
            cur = []
        cur.append(w)
        if w.text[-1] in ".?!,":
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def clean(t: str) -> str:
    return re.sub(r"[^\w$£%'’-]", "", t).upper()


RVM_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"


LIFT = (np.power(np.arange(256) / 255.0, 0.55) * 255).astype(np.uint8)


class Matter:
    """Robust Video Matting (ONNX): a temporally steady alpha matte of the speaker, frame by frame.
    Call reset() at the start of each speaker run so b-roll never leaks into the recurrent state."""

    def __init__(self, threads: int, lift: bool = True):
        import onnxruntime as ort
        self.lift = lift
        path = Path.home() / ".cache" / "rvm" / "rvm_mobilenetv3_fp32.onnx"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            m.run(["curl", "-sSL", "-o", str(path), RVM_URL])
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self) -> None:
        self.rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
        self.fresh = True

    def __call__(self, rgb: np.ndarray) -> np.ndarray:
        # see dark caps / hair against dark rooms: matte a lifted copy (the picture itself is untouched)
        x = ((LIFT[rgb] if self.lift else rgb).astype(np.float32) / 255).transpose(2, 0, 1)[None]
        for _ in range(8 if self.fresh else 1):  # lock the recurrent state on a run's first frame
            _, pha, *self.rec = self.sess.run(None, {"src": x, "r1i": self.rec[0], "r2i": self.rec[1],
                                                     "r3i": self.rec[2], "r4i": self.rec[3],
                                                     "downsample_ratio": np.array([0.25], np.float32)})
        self.fresh = False
        return pha[0, 0]


class Occluder:
    """The speaker's outline as a per-column 'top of silhouette' profile, built to look like a real
    head: two mattes (plain + lifted, so dark caps are kept) are merged, specks dropped, the head
    region is made convex (heads have no dents), and the profile is smoothed over time."""

    def __init__(self, threads: int, band: float = 0.24, keep: float = 0.4):
        self.mattes = [Matter(threads, lift=False)]
        self.band, self.keep = band, keep
        self.reset()

    def reset(self) -> None:
        for mt in self.mattes:
            mt.reset()
        self.prev = None

    def __call__(self, rgb: np.ndarray) -> np.ndarray:
        import cv2
        a = self.mattes[0](rgb)
        hard = (a > 0.5).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(hard)
        h, w = hard.shape
        if n <= 1:
            self.prev = None
            return np.full(w, float(h), np.float32)
        big = st[1:, cv2.CC_STAT_AREA].max()
        hard = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.03 * big]).astype(np.uint8)
        t0 = int(np.flatnonzero(hard.any(1))[0])
        t1 = min(h, t0 + int(self.band * h))
        ys, xs = np.nonzero(hard[t0:t1])
        if len(xs) > 10:  # convex head: fill every dent in the top band
            hull = cv2.convexHull(np.stack([xs, ys + t0], 1).astype(np.int32))
            cv2.fillConvexPoly(hard, hull, 1)
        top = np.where(hard.any(0), hard.argmax(0), h).astype(np.float32)
        on = top < h
        if on.sum() > 30:  # smooth the outline along x (no jagged steps), keep its ends where they are
            idx = np.flatnonzero(on)
            seg = top[idx[0]:idx[-1] + 1].copy()
            seg = cv2.GaussianBlur(seg.reshape(1, -1), (0, 0), 6).ravel()
            top[idx[0]:idx[-1] + 1] = np.where(on[idx[0]:idx[-1] + 1], seg, h)
        if self.prev is not None:  # steady outline: blend with the last frame where both see him
            both = (top < h) & (self.prev < h)
            top[both] = self.keep * top[both] + (1 - self.keep) * self.prev[both]
        self.prev = top.copy()
        return top


def profile_alpha(top: np.ndarray, y0: int, y1: int) -> np.ndarray:
    """Occluder alpha for rows y0..y1 from a top profile: 1 below the outline, crisp ~1 px edge."""
    import cv2
    rows = np.arange(y0, y1, dtype=np.float32)[:, None]
    a = np.clip(rows - top[None, :] + 0.5, 0, 1)
    return cv2.GaussianBlur(a, (0, 0), 0.8)


def head_profiles(video: Path, n: int, face: np.ndarray, threads: int) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame outline profiles (n x W, row of the silhouette top per column; H = nothing) and
    per-frame head-top y (NaN on b-roll). Computed once and reused for the composite."""
    occ = Occluder(threads)
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    prof = np.full((n, W), float(H), np.float32)
    tops = np.full(n, np.nan)
    x0, x1 = int(W * 0.2), int(W * 0.8)
    fb = W * H * 3
    for i in range(n):
        buf = p.stdout.read(fb)
        if len(buf) < fb:
            break
        if not face[i]:
            occ.reset()
            continue
        prof[i] = occ(np.frombuffer(buf, np.uint8).reshape(H, W, 3))
        c = prof[i, x0:x1]
        if (c < H).any():
            tops[i] = float(c.min())
    p.stdout.close()
    p.wait()
    return prof, tops


def grunge(seed: int) -> np.ndarray:
    """Static rough-print texture for the caption layer: mostly 1, with worn specks and streaks."""
    import cv2
    r = np.random.default_rng(seed)
    # fine print wear only — no big blotches (those read as the words being cut out)
    a = cv2.resize(r.random((H // 2, W // 2)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    b = r.random((H, W)).astype(np.float32)
    worn = (a > 0.90).astype(np.float32) * 0.45 + (b > 0.95).astype(np.float32) * 0.4
    return np.clip(1 - cv2.GaussianBlur(worn, (3, 3), 0), 0.35, 1)[:, :, None]


def build_audio(args, voice: np.ndarray, segs: list, total: float, ref_windows: list, tmp: Path) -> Path:
    """Voice throughout; the reference's opening sound at --hit-at; the reference cutaway sound at
    full power on every flick; and a continuous loop of that same music under the speaker at
    --music-db (relative to the voice), dipping a little while he speaks."""
    ref_voc = read_audio(args.ref_voc)
    g = rms(voice[np.abs(voice).mean(1) > 0.01]) / rms(ref_voc[np.abs(ref_voc).mean(1) > 0.01])
    n_tot = int(total * SR)
    mix = np.zeros((n_tot + 2 * SR, 2), np.float32)
    mix[: len(voice)] += voice
    # opening sound, starting on its attack, at --hit-at seconds
    ha, hb = map(float, args.ref_hit.split(":"))
    hit = read_audio(args.ref_stem, ha, hb - ha) * g * args.hit_gain
    lead = int(np.argmax(np.abs(hit).mean(1) > 0.02 * np.abs(hit).max()))
    hit = hit[max(0, lead - int(0.005 * SR)):]
    hit[-int(0.25 * SR):] *= np.linspace(1, 0, int(0.25 * SR))[:, None]
    h0 = int(args.hit_at * SR)
    mix[h0:h0 + len(hit)] += hit[: len(mix) - h0]
    # cutaway sound on each flick
    for kind, o0, o1, sn in segs:
        if kind == "cut":
            a, b = ref_windows[sn]
            x = read_audio(args.ref, a, (b - a) + args.tail) * g * args.snip_gain
            n = int(args.tail * SR)
            x[-n:] *= np.linspace(1, 0, n)[:, None]
            i0 = int(o0 * SR)
            mix[i0:i0 + len(x)] += x[: len(mix) - i0]
    # continuous music: loop the reference's un-ducked music (its cutaway windows, no-vocals stem)
    if args.music_db > -60:
        parts = [read_audio(args.ref_stem, a, b - a) for a, b in ref_windows]
        xf = int(0.08 * SR)
        loop = parts[0]
        for q in parts[1:] + [parts[0][: xf * 2]]:
            ramp = np.linspace(0, 1, xf)[:, None]
            loop = np.concatenate([loop[:-xf], loop[-xf:] * (1 - ramp) + q[:xf] * ramp, q[xf:]])
        loop = loop[:-xf]
        bed = np.tile(loop, (n_tot // len(loop) + 2, 1))[: n_tot]
        target = rms(voice[np.abs(voice).mean(1) > 0.01]) * 10 ** (args.music_db / 20)
        bed *= target / rms(bed)
        # dip ~4 dB under the voice so every word stays clear
        env = np.abs(voice[:n_tot]).mean(1)
        env = np.convolve(env, np.ones(int(0.12 * SR)) / int(0.12 * SR), mode="same")
        env = env / (np.percentile(env, 95) + 1e-9)
        duck = 1 - 0.37 * np.clip(env, 0, 1)
        if len(duck) < n_tot:
            duck = np.pad(duck, (0, n_tot - len(duck)), constant_values=1)
        bed *= duck[:, None]
        # fade in under the opening sound; out on the cuts the reference sound already fills
        fin = int(max(0.05, args.hit_at) * SR)
        bed[:fin] *= np.linspace(0, 1, fin)[:, None]
        for kind, o0, o1, _ in segs:
            if kind == "cut":
                a0, b0 = int(o0 * SR), min(n_tot, int(o1 * SR))
                bed[a0:b0] *= 0.35
        mix[:n_tot] += bed
    mix = mix[:n_tot]
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
    return audio


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speaker")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=999.0)
    ap.add_argument("--voice", help="clean voice wav on the tightened timeline (made with Demucs if absent)")
    ap.add_argument("--broll")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-cuts", default="5.35:7.20,11.05:12.90")
    ap.add_argument("--ref-hit", default="0.0:1.0", help="opening sound in the reference (stem time, s)")
    ap.add_argument("--ref-bed", default="13.0:49.5")
    ap.add_argument("--ref-stem", required=True)
    ap.add_argument("--ref-voc", required=True)
    ap.add_argument("--snip-gain", type=float, default=2.2, help="cutaway sound level (x reference level)")
    ap.add_argument("--hit-gain", type=float, default=2.6)
    ap.add_argument("--hit-at", type=float, default=0.5, help="when the opening sound plays (s)")
    ap.add_argument("--music-db", type=float, default=-99.0, help="music loop under the voice, dB vs voice")
    ap.add_argument("--lufs", type=float, default=-11.0)
    ap.add_argument("--remix", help="only rebuild the audio of this finished video (uses its plan + voice)")
    ap.add_argument("--first-cut", type=float, default=5.4)
    ap.add_argument("--talk-max", type=float, default=29.0)
    ap.add_argument("--talk-end", type=float, default=None)
    ap.add_argument("--tail", type=float, default=0.30)
    ap.add_argument("--out", required=True)
    ap.add_argument("--look", default="noir")
    ap.add_argument("--broll-look", default="black")
    ap.add_argument("--crop-top", type=float, default=0.0)
    ap.add_argument("--crop-bottom", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--font", default="Anton")
    ap.add_argument("--font-size", type=int, default=250)
    ap.add_argument("--texture", type=float, default=1.0, help="0 = solid letters, 1 = worn print texture")
    ap.add_argument("--sharpen", type=float, default=0.6, help="unsharp amount on the picture (not the captions)")
    ap.add_argument("--overlap", type=float, default=0.08, help="share of the caption height behind the head")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    if args.remix:
        src = Path(args.remix)
        plan = json.loads(src.with_suffix(".plan.json").read_text())
        total = plan["total"]
        voice = read_audio(str(src.with_suffix(".voice.wav")))[: int(total * SR)]
        tmp = Path(tempfile.mkdtemp(prefix="rx_", dir=str(src.parent)))
        ref_windows = [tuple(map(float, c.split(":"))) for c in args.ref_cuts.split(",")]
        audio = build_audio(args, voice, [tuple(x) for x in plan["segments"]], total, ref_windows, tmp)
        m.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-i", str(audio), "-map", "0:v", "-map", "1:a",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", "-t", f"{total:.3f}",
               args.out])
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"remixed → {args.out}")
        return

    rng = random.Random(args.seed)
    speaker = str(Path(args.speaker).resolve())
    sp = m.probe(speaker)
    end = min(args.end, sp["dur"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cache = out.parent / ".cache"
    cache.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="vo_", dir=str(cache)))

    words = m.transcribe(speaker, args.start, end, "small", cache)
    keep = m.build_keep_ranges(words, args.start, end, True)
    f = m.src_to_out(keep)
    for w in words:
        w.out_start, w.out_end = f(w.start), f(w.end)
    vpath = Path(args.voice) if args.voice else out.with_suffix(".voice.wav")
    if not vpath.exists():
        shutil.copy(m.render_audio(speaker, keep, tmp, False, True, words, 0.0), vpath)
    voice = read_audio(str(vpath))
    total = min(sum(b - a for a, b in keep), len(voice) / SR)

    if args.talk_end:
        total = min(total, args.talk_end)
    elif total > args.talk_max:
        ends = [w.out_end for w in words if w.text[-1] in ".?!" and 15 <= w.out_end <= args.talk_max + 0.5]
        if not ends:
            cand = [(b.out_start - a.out_end, a.out_end) for a, b in zip(words, words[1:])
                    if 18 <= a.out_end <= args.talk_max + 0.5]
            ends = [max(cand)[1]] if cand else [args.talk_max]
        total = ends[-1] + 0.25
    words = [w for w in words if w.out_start < total - 0.05]
    total = round(total * FPS) / FPS
    voice = voice[: int(total * SR)]
    print(f"talk {total:.1f}s: " + " ".join(w.text for w in words))

    ref_windows = [tuple(map(float, c.split(":"))) for c in args.ref_cuts.split(",")]
    d = round((ref_windows[0][1] - ref_windows[0][0]) * FPS) / FPS
    cuts = [round(c * FPS) / FPS for c in cut_times(words, total, args.first_cut, d, 3.9, 5.2, 1.5, rng)]
    print("flick to b-roll at", cuts)

    segs = []  # (kind, out_start, out_end, snippet index)
    t = 0.0
    for i, c in enumerate(cuts):
        segs.append(("talk", t, c, -1))
        segs.append(("cut", c, c + d, i % len(ref_windows)))
        t = c + d
    segs.append(("talk", t, total, -1))
    snippets = [read_audio(args.ref, a, (b - a) + args.tail) for a, b in ref_windows]
    audio = build_audio(args, voice, segs, total, ref_windows, tmp)

    # --- video
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
    for k, (kind, o0, o1, sn) in enumerate(segs):
        if o1 - o0 < 1 / FPS:
            continue
        if kind == "talk":
            sh = m.Shot("face", o0, o1, punch=punches[(k // 2) % len(punches)])
            pieces.extend(m.split_by_keep([sh], keep))
        else:
            x = snippets[sn]
            c = round(onset(x[: int(d * SR)], 0.55, d - 0.55) * FPS) / FPS
            for a, b in ((0.0, c), (c, d)):
                fp = pool.pop() if pool else rng.choice(ranked)
                dur = m.probe(fp)["dur"]
                pieces.append(m.Shot("broll", o0 + a, o0 + b, src=fp,
                                     src_start=rng.uniform(0, max(0.0, dur - (b - a) - 0.1))))
    files = [m.render_piece(i, p, speaker, sp, args.look, tmp, random.Random(args.seed + i), centre,
                            2, args.crop_top, args.crop_bottom, args.broll_look) for i, p in enumerate(pieces)]
    (tmp / "concat.txt").write_text("".join(f"file '{Path(x).name}'\n" for x in files))
    video = tmp / "video.mp4"
    m.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "concat.txt"),
           "-t", f"{total:.3f}", "-vf", f"unsharp=5:5:{args.sharpen}:5:5:0", "-c:v", "libx264", "-preset", "fast",
           "-crf", "10", "-r", str(FPS),
           "-pix_fmt", "yuv420p", str(video)])
    n = int(round(total * FPS))
    face = np.ones(n, bool)
    for kind, o0, o1, _ in segs:
        if kind == "cut":
            face[int(round(o0 * FPS)):int(round(o1 * FPS))] = False

    # --- speaker masks -> where his head is
    prof, tops = head_profiles(video, n, face, args.threads)
    top = float(np.nanmedian(tops)) if np.isfinite(tops).any() else H * 0.3
    print(f"head top at y={top:.0f}")

    # --- captions: 2–3 words, big caps, bottom edge tucked behind the head
    lines = [f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T,{args.font},{args.font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H8C000000,0,0,0,0,100,100,0,0,1,0,4,2,30,30,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""]
    cs = chunks(words)
    for i, ch in enumerate(cs):
        txt = " ".join(clean(w.text) for w in ch)
        a = ch[0].out_start
        b = cs[i + 1][0].out_start if i + 1 < len(cs) else min(total, ch[-1].out_end + 0.5)
        if b - ch[-1].out_end > 0.6:
            b = ch[-1].out_end + 0.35
        span = tops[int(a * FPS):max(int(a * FPS) + 1, int(b * FPS))]
        t_here = float(np.nanpercentile(span, 15)) if np.isfinite(span).any() else top  # head at its highest
        # close-up with the head near the top: shrink so the words still fit above it
        room = (t_here - 70) / (0.74 * (1 - args.overlap))
        size = int(min(args.font_size, (W - 80) / (0.40 * max(1, len(txt))), max(170, room)))
        cap = 0.74 * size  # Anton cap height
        # line box bottom ≈ baseline + 0.2·size; tuck `overlap` of the caps behind the head
        y = t_here + args.overlap * cap + 0.2 * size
        y = max(y, 70 + cap + 0.2 * size)  # never off the top
        lines.append(f"Dialogue: 0,{m.fmt_ass(a)},{m.fmt_ass(min(b, total))},T,,0,0,0,,"
                     f"{{\\an2\\pos({W // 2},{y:.0f})\\blur0.8}}{txt}\n")
    ass = tmp / "captions.ass"
    ass.write_text("".join(lines), encoding="utf-8")

    # --- composite: captioned frame, speaker pasted back over the text, rough texture on the letters
    import cv2
    tex = 1.0 + args.texture * (grunge(args.seed) - 1.0)
    rd = lambda vf: subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    plain, capd = rd("null"), rd(f"ass={ass}")
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio),
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
                            "-maxrate", "20M", "-bufsize", "40M", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)],
                           stdin=subprocess.PIPE)
    fb = W * H * 3
    for i in range(n):
        p, c = plain.stdout.read(fb), capd.stdout.read(fb)
        if len(p) < fb or len(c) < fb:
            break
        p = np.frombuffer(p, np.uint8).reshape(H, W, 3).astype(np.float32)
        c = np.frombuffer(c, np.uint8).reshape(H, W, 3).astype(np.float32)
        delta = (c - p) * tex
        if face[i]:
            rows = np.flatnonzero(np.abs(c - p).max(2).max(1) > 2)
            if len(rows):
                y0, y1 = max(0, rows[0] - 40), min(H, rows[-1] + 41)
                delta[y0:y1] *= (1 - profile_alpha(prof[i], y0, y1))[:, :, None]
        enc.stdin.write(np.clip(p + delta, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()
    for q in (plain, capd):
        q.stdout.close()
        q.wait()
    out.with_suffix(".plan.json").write_text(json.dumps({
        "speaker": speaker, "total": total, "cuts": cuts, "head_top": top,
        "segments": [list(s) for s in segs]}, indent=1))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"done → {out} ({total:.1f}s)")


if __name__ == "__main__":
    main()
