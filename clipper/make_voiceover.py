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
MW, MH = 288, 512  # segmentation resolution


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


def seg_model(threads: int):
    import torch
    from torchvision.models.segmentation import deeplabv3_resnet50, DeepLabV3_ResNet50_Weights
    torch.set_num_threads(threads)
    return deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT).eval()


def person_masks(video: Path, n: int, face: np.ndarray, step: int, threads: int) -> np.ndarray:
    """Person probability (MH x MW, uint8) for every frame; computed every `step` speaker frames
    and interpolated between; zero on b-roll frames."""
    import torch
    model = seg_model(threads)
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vf", f"scale={MW}:{MH}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    masks = np.zeros((n, MH, MW), np.uint8)
    key = {}
    sharp_top = np.full(n, np.nan)
    mean, std = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])
    for i in range(n):
        buf = p.stdout.read(MW * MH * 3)
        if len(buf) < MW * MH * 3:
            break
        if not face[i]:
            continue
        # always segment the first and last frame of each speaker run so nothing extrapolates
        first = i == 0 or not face[i - 1]
        last = i == n - 1 or not face[i + 1]
        if i % step and not first and not last:
            continue
        x = (np.frombuffer(buf, np.uint8).reshape(MH, MW, 3) / 255.0 - mean) / std
        with torch.inference_mode():
            o = model(torch.from_numpy(x.transpose(2, 0, 1)).float()[None])["out"]
        pr = o.softmax(1)[0, 15].numpy()
        key[i] = (pr * 255).astype(np.uint8)
        hard = refine(np.frombuffer(buf, np.uint8).reshape(MH, MW, 3), pr)
        sharp_top[i] = sharp_head_top(hard)
    p.stdout.close()
    p.wait()
    ks = sorted(key)
    for a, b in zip(ks, ks[1:]):
        masks[a] = key[a]
        if b - a > 1 and all(face[a:b + 1]):
            for i in range(a + 1, b):
                t = (i - a) / (b - a)
                masks[i] = (key[a] * (1 - t) + key[b] * t).astype(np.uint8)
    if ks:
        masks[ks[-1]] = key[ks[-1]]
    # fill head tops between keyframes
    idx = np.flatnonzero(np.isfinite(sharp_top))
    if len(idx):
        fr = np.flatnonzero(face)
        sharp_top[fr] = np.interp(fr, idx, sharp_top[idx])
    return masks, sharp_top


def sharp_head_top(hard: np.ndarray) -> float:
    x0, x1 = int(MW * 0.2), int(MW * 0.8)
    r = np.flatnonzero((hard[:, x0:x1] > 0.5).mean(1) > 0.06)
    return r[0] / MH * H if len(r) else np.nan


def box(x: np.ndarray, r: int) -> np.ndarray:
    import cv2
    return cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1), normalize=True, borderType=cv2.BORDER_REFLECT)


def refine(guide_rgb: np.ndarray, prob: np.ndarray) -> np.ndarray:
    """Turn the soft person probability into a sharp cut-out that hugs the real outline:
    GrabCut (colour models seeded by the probability) at half res decides the uncertain band,
    then a small guided filter gives a clean ~1 px edge at full res."""
    import cv2
    h, w = prob.shape
    hs, ws = h // 2, w // 2
    img = cv2.resize(guide_rgb, (ws, hs), interpolation=cv2.INTER_AREA)
    # dark scenes: stretch contrast so hood-vs-background colour differences count
    f = img.astype(np.float32)
    lo, hi = np.percentile(f, 1), np.percentile(f, 99.5)
    img = np.clip((f - lo) * 255 / max(1.0, hi - lo), 0, 255).astype(np.uint8)
    pr = cv2.resize(prob, (ws, hs), interpolation=cv2.INTER_AREA)
    gc = np.full((hs, ws), cv2.GC_PR_BGD, np.uint8)
    gc[pr >= 0.5] = cv2.GC_PR_FGD
    gc[cv2.erode((pr > 0.97).astype(np.uint8), np.ones((15, 15), np.uint8)) > 0] = cv2.GC_FGD
    gc[cv2.erode((pr < 0.03).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0] = cv2.GC_BGD
    if (gc == cv2.GC_FGD).any() and (gc == cv2.GC_BGD).any():
        try:
            cv2.grabCut(img, gc, None, np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64), 2,
                        cv2.GC_INIT_WITH_MASK)
        except cv2.error:
            pass
    hard = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.float32)
    hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(hard.astype(np.uint8))
    if n > 2:  # drop specks: keep only real parts of the person
        big = st[1:, cv2.CC_STAT_AREA].max()
        hard = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.05 * big]).astype(np.float32)
    hard = cv2.resize(hard, (w, h), interpolation=cv2.INTER_LINEAR)
    I = cv2.cvtColor(guide_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    r, eps = 4, 1e-3
    mI, mp = box(I, r), box(hard, r)
    a = (box(I * hard, r) - mI * mp) / (box(I * I, r) - mI * mI + eps)
    q = box(a, r) * I + box(mp - a * mI, r)
    return np.clip((q - 0.5) * 6 + 0.5, 0, 1)


def grunge(seed: int) -> np.ndarray:
    """Static rough-print texture for the caption layer: mostly 1, with worn specks and streaks."""
    import cv2
    r = np.random.default_rng(seed)
    # fine print wear only — no big blotches (those read as the words being cut out)
    a = cv2.resize(r.random((H // 2, W // 2)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    b = r.random((H, W)).astype(np.float32)
    worn = (a > 0.90).astype(np.float32) * 0.45 + (b > 0.95).astype(np.float32) * 0.4
    return np.clip(1 - cv2.GaussianBlur(worn, (3, 3), 0), 0.35, 1)[:, :, None]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speaker", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=999.0)
    ap.add_argument("--voice", help="clean voice wav on the tightened timeline (made with Demucs if absent)")
    ap.add_argument("--broll", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--ref-cuts", default="5.35:7.20,11.05:12.90")
    ap.add_argument("--ref-hit", default="0.0:1.0", help="opening sound in the reference (stem time, s)")
    ap.add_argument("--ref-bed", default="13.0:49.5")
    ap.add_argument("--ref-stem", required=True)
    ap.add_argument("--ref-voc", required=True)
    ap.add_argument("--snip-gain", type=float, default=0.85, help="cutaway sound level under the voice")
    ap.add_argument("--hit-gain", type=float, default=1.4)
    ap.add_argument("--first-cut", type=float, default=5.4)
    ap.add_argument("--talk-max", type=float, default=29.0)
    ap.add_argument("--talk-end", type=float, default=None)
    ap.add_argument("--tail", type=float, default=0.30)
    ap.add_argument("--out", required=True)
    ap.add_argument("--look", default="noir")
    ap.add_argument("--broll-look", default="lift")
    ap.add_argument("--crop-top", type=float, default=0.0)
    ap.add_argument("--crop-bottom", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--font", default="Anton")
    ap.add_argument("--font-size", type=int, default=250)
    ap.add_argument("--overlap", type=float, default=0.25, help="share of the caption height behind the head")
    ap.add_argument("--seg-step", type=int, default=2)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

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

    # --- audio: voice throughout; opening hit at 0; reference cutaway sound under each flick
    ref_voc = read_audio(args.ref_voc)
    g = rms(voice[np.abs(voice).mean(1) > 0.01]) / rms(ref_voc[np.abs(ref_voc).mean(1) > 0.01])
    mix = np.zeros((int(total * SR) + SR, 2), np.float32)
    mix[: len(voice)] += voice
    ha, hb = map(float, args.ref_hit.split(":"))
    hit = read_audio(args.ref_stem, ha, hb - ha) * g * args.hit_gain
    lead = int(np.argmax(np.abs(hit).mean(1) > 0.02 * np.abs(hit).max()))  # start on the attack
    hit = hit[max(0, lead - int(0.005 * SR)):]
    hit[-int(0.25 * SR):] *= np.linspace(1, 0, int(0.25 * SR))[:, None]
    mix[: len(hit)] += hit[: len(mix)]
    segs = []  # (kind, out_start, out_end, snippet index)
    t = 0.0
    for i, c in enumerate(cuts):
        segs.append(("talk", t, c, -1))
        segs.append(("cut", c, c + d, i % len(ref_windows)))
        t = c + d
    segs.append(("talk", t, total, -1))
    snippets = []
    for a, b in ref_windows:
        x = read_audio(args.ref, a, (b - a) + args.tail) * g * args.snip_gain
        n = int(args.tail * SR)
        x[-n:] *= np.linspace(1, 0, n)[:, None]
        snippets.append(x)
    for kind, o0, o1, sn in segs:
        if kind == "cut":
            x = snippets[sn]
            i0 = int(o0 * SR)
            mix[i0:i0 + len(x)] += x[: len(mix) - i0]
    ba, bb = map(float, args.ref_bed.split(":"))
    bed = read_audio(args.ref_stem, ba, bb - ba) * g
    cut_segs = [s for s in segs if s[0] == "cut"]
    if len(cut_segs) >= 2:
        b0 = int(cut_segs[1][2] * SR)
        n = len(mix) - b0
        reps = np.tile(bed, (n // max(1, len(bed)) + 1, 1))[:n]
        for kind, o0, o1, _ in segs:
            if kind == "cut":
                a, b = max(b0, int(o0 * SR)), int(o1 * SR)
                if b > a:
                    reps[a - b0:b - b0] = 0
        mix[b0:] += reps
    mix = mix[: int(total * SR)]
    raw = tmp / "mix.wav"
    write_wav(raw, mix)
    # two-pass linear loudnorm: one constant gain, so the opening hit isn't swallowed by a gain ramp
    meas = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(raw), "-af",
                           "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    js = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    audio = tmp / "mix_ln.wav"
    m.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
           f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
           f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:"
           f"linear=true,alimiter=limit=0.89:attack=1:release=40", "-ar", str(SR), str(audio)])

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
           "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-r", str(FPS),
           "-pix_fmt", "yuv420p", str(video)])
    n = int(round(total * FPS))
    face = np.ones(n, bool)
    for kind, o0, o1, _ in segs:
        if kind == "cut":
            face[int(round(o0 * FPS)):int(round(o1 * FPS))] = False

    # --- speaker masks -> where his head is
    masks, tops = person_masks(video, n, face, args.seg_step, args.threads)
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
    tex = grunge(args.seed)
    rd = lambda vf: subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    plain, capd = rd("null"), rd(f"ass={ass}")
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio),
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
                            "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-c:a", "aac",
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
                prob = cv2.resize(masks[i], (W, H), interpolation=cv2.INTER_CUBIC)[y0:y1].astype(np.float32) / 255
                a = refine(p[y0:y1].astype(np.uint8), np.clip(prob, 0, 1))
                delta[y0:y1] *= (1 - a)[:, :, None]
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
