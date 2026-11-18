#!/usr/bin/env python3
"""
make_clip.py — turn a talking-head recording + a folder of luxury b-roll into a
TikTok-style motivational clip: speaker on camera for the strong lines, moody
b-roll over the rest, word-by-word captions, no music, 1080x1920 @ 30 fps.

    python clipper/make_clip.py \
        --speaker markov_podcast.mp4 --start 412 --end 441 \
        --broll ./broll \
        --style serif --look moody \
        --out out/markov_01.mp4

Pipeline
  1. transcribe the chosen range with faster-whisper (word timestamps)
  2. optional "tighten": cut dead air between words (pauses > 0.45 s)
  3. plan shots: open on the face for the hook, then alternate b-roll / face,
     every cut snapped to a word boundary; last line always lands on the face
  4. render each shot (face: 9:16 reframe around the detected face + alternating
     punch-ins; b-roll: cover-crop + slow push) through the same colour grade
  5. concat, burn captions (libass), lay the cleaned speech audio underneath

Everything is CPU ffmpeg + python; ~1–2x realtime on 4 cores.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

W, H, FPS = 1080, 1920, 30
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}

# ----------------------------------------------------------------------------- helpers


def run(cmd: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        sys.stderr.write(" ".join(cmd) + "\n" + p.stderr[-4000:] + "\n")
        raise SystemExit(f"command failed ({p.returncode}): {cmd[0]}")
    return p


def probe(path: str) -> dict:
    p = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate,duration:format=duration",
             "-of", "json", path])
    j = json.loads(p.stdout)
    s = j["streams"][0]
    dur = float(s.get("duration") or j["format"]["duration"])
    return {"w": int(s["width"]), "h": int(s["height"]), "dur": dur}


def fmt_ass(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ----------------------------------------------------------------------------- data


@dataclass
class Word:
    text: str
    start: float  # source seconds
    end: float
    out_start: float = 0.0  # output-timeline seconds
    out_end: float = 0.0


@dataclass
class Shot:
    kind: str  # "face" | "broll"
    out_start: float
    out_end: float
    src_start: float = 0.0  # face: speaker source time; broll: offset in broll file
    src: str = ""           # broll file
    punch: float = 1.0      # face zoom factor
    hit: float = 0.0        # extra zoom punch on the first frames of the shot
    word_text: str = ""     # debugging only

    @property
    def dur(self) -> float:
        return self.out_end - self.out_start


@dataclass
class Plan:
    words: list[Word]
    keep: list[tuple[float, float]]  # source ranges kept, in order
    shots: list[Shot] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return sum(b - a for a, b in self.keep)


# ----------------------------------------------------------------------------- transcription


def transcribe(path: str, start: float, end: float, model_size: str, cache: Path) -> list[Word]:
    key = cache / f"{Path(path).stem}_{start:.2f}_{end:.2f}_{model_size}.json"
    if key.exists():
        return [Word(**w) for w in json.loads(key.read_text())]
    from faster_whisper import WhisperModel  # lazy: slow import
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    # cut the range to a wav first so whisper only sees what we need
    wav = cache / (key.stem + ".wav")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", path,
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(wav)])
    # hand whisper raw samples: avoids the PyAV decode path, which breaks across av versions
    import numpy as np
    audio = np.frombuffer(wav.read_bytes()[44:], dtype=np.int16).astype(np.float32) / 32768.0
    segs, _ = model.transcribe(audio, word_timestamps=True, vad_filter=True,
                               vad_parameters={"min_silence_duration_ms": 300})
    words: list[Word] = []
    for s in segs:
        for w in s.words or []:
            txt = w.word.strip()
            if not txt:
                continue
            if words and (txt.startswith("-") or txt.startswith("'")):
                words[-1].text += txt
                words[-1].end = start + w.end
                continue
            words.append(Word(txt, start + w.start, start + w.end))
    wav.unlink(missing_ok=True)
    key.write_text(json.dumps([w.__dict__ for w in words]))
    return words


# ----------------------------------------------------------------------------- planning


def build_keep_ranges(words: list[Word], start: float, end: float, tighten: bool,
                      max_gap: float = 0.45, keep_gap: float = 0.18, pad: float = 0.12) -> list[tuple[float, float]]:
    if not tighten or not words:
        return [(start, end)]
    ranges: list[list[float]] = [[max(start, words[0].start - pad), words[0].end]]
    for prev, cur in zip(words, words[1:]):
        gap = cur.start - prev.end
        if gap > max_gap:
            ranges[-1][1] = prev.end + keep_gap / 2
            ranges.append([cur.start - keep_gap / 2, cur.end])
        else:
            ranges[-1][1] = cur.end
    ranges[-1][1] = min(end, words[-1].end + pad * 2)
    return [(a, b) for a, b in ranges if b - a > 0.05]


def src_to_out(keep: list[tuple[float, float]]):
    offs = []
    acc = 0.0
    for a, b in keep:
        offs.append((a, b, acc))
        acc += b - a

    def f(t: float) -> float:
        for a, b, o in offs:
            if t <= b:
                return o + max(0.0, t - a)
        return acc
    return f


def plan_shots(words: list[Word], total: float, rng: random.Random, hook: float, face_len: tuple[float, float],
               broll_len: tuple[float, float], face_ratio: float, closer: float,
               hard_cuts: list[float] | None = None, hits: bool = True) -> list[Shot]:
    """Alternate face / b-roll, snapping every cut to the end of a word."""
    bounds = sorted({round(w.out_end, 3) for w in words} | {0.0, round(total, 3)})
    hard = sorted(hard_cuts or [])

    def snap(t: float) -> float:
        # a cut that lands exactly on a tightened silence hides the jump cut under the b-roll change
        near = [h for h in hard if abs(h - t) <= 0.7]
        if near:
            return min(near, key=lambda h: abs(h - t))
        return min(bounds, key=lambda b: abs(b - t))

    shots: list[Shot] = []
    t = 0.0
    kind = "face"
    first = True
    while t < total - 0.05:
        if first:
            length = hook
            first = False
        elif kind == "face":
            length = rng.uniform(*face_len)
        else:
            length = rng.uniform(*broll_len)
        # keep roughly face_ratio of screen time on the speaker
        face_time = sum(s.dur for s in shots if s.kind == "face")
        if shots and kind == "broll" and face_time / max(t, 0.01) < face_ratio - 0.15:
            kind = "face"
            length = rng.uniform(*face_len)
        cut = snap(t + length)
        if cut <= t + 0.6:  # too short: take the next boundary
            nxt = [b for b in bounds if b > t + 0.6]
            cut = nxt[0] if nxt else total
        if total - cut < closer:  # last line stays on the face
            cut = total
            if kind == "broll" and shots:
                kind = "face"
        shots.append(Shot(kind, t, cut))
        t = cut
        kind = "broll" if kind == "face" else "face"
    # merge accidental adjacent same-kind shots
    merged: list[Shot] = []
    for s in shots:
        if merged and merged[-1].kind == s.kind:
            merged[-1].out_end = s.out_end
        else:
            merged.append(s)
    # punch-in pattern on face shots: 1.0 → 1.12 → 1.0 → 1.18 …
    pattern = [1.0, 1.12, 1.0, 1.18, 1.06]
    i = 0
    for s in merged:
        if s.kind == "face":
            s.punch = pattern[i % len(pattern)]
            s.hit = (0.10 if i == 0 else 0.05) if hits else 0.0
            i += 1
    return merged


def split_by_keep(shots: list[Shot], keep: list[tuple[float, float]]) -> list[Shot]:
    """Face shots must map back to source time; a tightened edit can put a
    silence-cut inside a shot, so split into pieces that each map to one keep range."""
    pieces: list[Shot] = []
    acc = 0.0
    spans = []
    for a, b in keep:
        spans.append((acc, acc + (b - a), a))
        acc += b - a
    for s in shots:
        if s.kind != "face":
            pieces.append(s)
            continue
        for o0, o1, a in spans:
            lo, hi = max(s.out_start, o0), min(s.out_end, o1)
            if hi - lo > 0.04:
                pieces.append(Shot("face", lo, hi, src_start=a + (lo - o0), punch=s.punch,
                                   hit=s.hit if abs(lo - s.out_start) < 0.02 else 0.0))
    pieces.sort(key=lambda p: p.out_start)
    # a face sliver under 0.35 s next to a b-roll shot reads as a flash frame: give that time to the b-roll
    out: list[Shot] = []
    for p in pieces:
        if p.kind == "face" and p.dur < 0.35 and out and out[-1].kind == "broll":
            out[-1].out_end = p.out_end
            continue
        if p.kind == "broll" and out and out[-1].kind == "face" and out[-1].dur < 0.35:
            p.out_start = out.pop().out_start
        out.append(p)
    return out


def assign_broll(shots: list[Shot], files: list[str], rng: random.Random) -> None:
    infos = {f: probe(f) for f in files}
    order = files[:]
    rng.shuffle(order)
    i = 0
    used: dict[str, float] = {}
    for s in shots:
        if s.kind != "broll":
            continue
        for _ in range(len(order)):
            f = order[i % len(order)]
            i += 1
            dur = infos[f]["dur"]
            if dur >= s.dur + 0.2:
                break
        else:
            raise SystemExit("every b-roll clip is shorter than the shot it should fill — add longer clips")
        # new offset each time the same file comes round
        lo = used.get(f, 0.0)
        if lo + s.dur + 0.2 > dur:
            lo = 0.0
        start = rng.uniform(lo, max(lo, dur - s.dur - 0.1))
        used[f] = start + s.dur
        s.src, s.src_start = f, start


# ----------------------------------------------------------------------------- rendering


LOOKS = {
    # deep, cool, lifted-then-crushed blacks — the "1make.more.money1" / stoic look
    "moody": ("eq=contrast=1.10:brightness=-0.02:saturation=0.72,"
              "colorbalance=rs=-0.05:gs=-0.01:bs=0.07:rm=-0.03:bm=0.05:rh=-0.02:bh=0.03,"
              "curves=m='0/0 0.1/0.07 0.5/0.49 1/1',"
              "vignette=angle=PI/5,noise=c0s=4:c1s=2:allf=t+u"),
    # same but heavier: for b-roll that is shot bright and needs pulling down
    "noir": ("eq=contrast=1.22:brightness=-0.11:saturation=0.55,"
             "colorbalance=rs=-0.07:gs=-0.02:bs=0.10:rm=-0.05:bm=0.07:rh=-0.04:bh=0.04,"
             "curves=m='0/0 0.18/0.1 0.55/0.46 1/0.86',"
             "vignette=angle=PI/4.2,noise=c0s=5:c1s=2:allf=t+u"),
    # editorial black and white — the "goldenlife.mindset" look
    "bw": ("hue=s=0,eq=contrast=1.18:brightness=0.0,"
           "curves=m='0/0 0.15/0.1 0.55/0.56 1/1',vignette=angle=PI/4.4,noise=c0s=7:allf=t+u"),
    # mostly natural, slight punch
    "clean": "eq=contrast=1.06:saturation=0.9,vignette=angle=PI/5.5",
}


def detect_face_center(path: str, t0: float, t1: float) -> tuple[float, float] | None:
    """Median face centre (normalised 0-1) over a few frames of the range; None if no face."""
    try:
        import cv2
    except ImportError:
        return None
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(path)
    xs, ys = [], []
    for k in range(5):
        cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * (t0 + (t1 - t0) * (k + 0.5) / 5))
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        scale = 480 / w
        small = cv2.resize(frame, (480, int(h * scale)))
        faces = cas.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.15, 5, minSize=(40, 40))
        if len(faces):
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + fw / 2) / 480)
            ys.append((y + fh / 2) / (h * scale))
    cap.release()
    if not xs:
        return None
    xs.sort(); ys.sort()
    return float(xs[len(xs) // 2]), float(ys[len(ys) // 2])


def push_filter(z0: float, z1: float, dur: float, punch: float = 0.0, punch_frames: int = 7) -> str:
    """Smooth zoom from factor z0 to z1 over the shot without changing frame size:
    a perspective warp whose source quad shrinks (push in) or grows (push out).
    punch > 0 adds a quick extra zoom on the first frames that settles back (a cut 'hit')."""
    n = max(1, int(round(dur * FPS)))
    z = f"({z0}+({z1}-{z0})*min(on,{n})/{n})"
    if punch > 0:
        z = f"({z}*(1+{punch}*max(0,1-on/{punch_frames})))"
    k = f"0.5*(1-1/{z})"
    return (f"perspective=x0='W*({k})':y0='H*({k})':x1='W*(1-({k}))':y1='H*({k})':"
            f"x2='W*({k})':y2='H*(1-({k}))':x3='W*(1-({k}))':y3='H*(1-({k}))':"
            f"interpolation=cubic:eval=frame")


def face_filter(info: dict, punch: float, dur: float, centre: tuple[float, float] | None,
                crop_top: float = 0.0, crop_bottom: float = 0.0, hit: float = 0.0) -> str:
    """Reframe any aspect to 9:16 around the face, then punch-in + slow push.
    crop_top / crop_bottom exclude a band of the source (burned-in TikTok text, UI)."""
    sw, sh = info["w"], info["h"]
    # crop window with 9:16 aspect inside the source
    if sw / sh > W / H:
        ch, cw = sh, int(sh * W / H)
    else:
        cw, ch = sw, int(sw * H / W)
    # zoom far enough that the excluded bands fall outside the window
    punch = max(punch, 1.0 / max(0.3, 1.0 - crop_top - crop_bottom))
    cw, ch = int(cw / punch) // 2 * 2, int(ch / punch) // 2 * 2
    cx, cy = (0.5, 0.42) if centre is None else centre
    # keep the face around 38 % down the frame (eyes in the upper third)
    x = min(max(cx * sw - cw / 2, 0), sw - cw)
    y = min(max(cy * sh - ch * 0.38, crop_top * sh), sh * (1 - crop_bottom) - ch)
    push = 0.035  # 3.5 % slow push over the shot, keeps static interviews alive
    return (f"crop={cw}:{ch}:{int(x)}:{int(y)},scale={W}:{H},"
            + push_filter(1.0, 1.0 + push, dur, hit))


def broll_filter(info: dict, dur: float, rng: random.Random) -> str:
    """Cover-crop to 9:16 with a slow push in or out (alternates)."""
    zoom = rng.choice([0.07, -0.07, 0.05, 0.09])
    z0, z1 = (1.0, 1.0 + zoom) if zoom > 0 else (1.0 - zoom, 1.0)
    return (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            + push_filter(z0, z1, dur))


def render_piece(idx: int, s: Shot, speaker: str, sp_info: dict, look: str, tmp: Path, rng: random.Random,
                 centre: tuple[float, float] | None, threads: int, crop_top: float = 0.0,
                 crop_bottom: float = 0.0) -> str:
    out = tmp / f"piece_{idx:03d}.mp4"
    if s.kind == "face":
        src, ss = speaker, s.src_start
        vf = face_filter(sp_info, s.punch, s.dur, centre, crop_top, crop_bottom, s.hit)
    else:
        src, ss = s.src, s.src_start
        vf = broll_filter(probe(src), s.dur, rng)
    vf += "," + LOOKS[look] + f",fps={FPS},format=yuv420p"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.3f}", "-i", src, "-t", f"{s.dur:.3f}",
         "-vf", vf, "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "14",
         "-threads", str(threads), "-video_track_timescale", "90000", str(out)])
    return str(out)


def write_impulse(path: Path, seconds: float = 1.4, decay: float = 6.0, pre_delay: float = 0.03) -> None:
    """Synthesise a plate-style reverb impulse: exponentially decaying noise that darkens along the tail."""
    import numpy as np
    import wave
    sr = 48000
    n = int(sr * seconds)
    t = np.arange(n) / sr
    noise = np.random.default_rng(3).standard_normal(n) * np.exp(-t * decay)
    y = np.empty(n)
    acc = 0.0
    for i in range(n):  # one-pole low-pass whose cut-off closes as the tail dies
        coef = 0.15 + 0.6 * (t[i] / seconds)
        acc += (noise[i] - acc) * (1 - coef)
        y[i] = acc
    y = np.concatenate([np.zeros(int(pre_delay * sr)), y])[:n]
    y /= (np.abs(y).max() + 1e-9) * 4
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype(np.int16).tobytes())


def echo_chain(words: list["Word"], total: float, amount: float) -> str:
    """Dry voice + convolution reverb (input 1 is the impulse). The wet level sits low under the
    speech and swells for ~1 s after every sentence-final word, so punchlines ring out."""
    if amount <= 0:
        return "[g]acopy[mix]"
    tails = [w for w in words if w.text[-1] in ".?!"]
    if words and words[-1] not in tails:
        tails.append(words[-1])
    swell = "".join(f",volume=enable='between(t,{w.out_end - 0.05:.3f},{min(total + 1.5, w.out_end + 1.2):.3f})':volume=2.6"
                    for w in tails)
    return (f"[g]asplit[dry][w];[w][1:a]afir=dry=1:wet=1:gtype=-1,volume={0.22 * amount:.3f}{swell}[wet];"
            f"[dry][wet]amix=inputs=2:duration=longest:normalize=0[mix]")


def gate_chain(words: list["Word"], total: float, pad: float = 0.12, min_gap: float = 0.35) -> str:
    """Mute the gaps between words (where separation bleed lives)."""
    spans: list[list[float]] = []
    for w in words:
        a, b = w.out_start - pad, w.out_end + pad
        if spans and a <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    gaps, t = [], 0.0
    for a, b in spans:
        if a - t >= min_gap:
            gaps.append((t, a))
        t = max(t, b)
    if total - t >= min_gap:
        gaps.append((t, total))
    return "".join(f",volume=enable='between(t,{a:.3f},{b:.3f})':volume=0" for a, b in gaps)


def render_audio(speaker: str, keep: list[tuple[float, float]], tmp: Path, denoise: bool,
                 isolate: bool = True, words: list["Word"] | None = None, echo: float = 1.0) -> str:
    out = tmp / "voice.wav"
    src = speaker
    if isolate:
        # TikTok sources carry a music bed under the speech: keep only the vocal stem
        from strip_music import isolate_voice  # same two-pass fine-tuned separation as strip_music.py
        mix = tmp / "mix.wav"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", speaker, "-vn", "-ac", "2", "-ar", "44100", str(mix)])
        src = str(isolate_voice(mix, tmp / "sep"))
    parts = []
    for i, (a, b) in enumerate(keep):
        parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}]")
    chain = "".join(f"[a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=0:a=1[cat]"
    total = sum(b - a for a, b in keep)
    # silence after the last word so the echo has room to ring out
    post = "[cat]apad=pad_dur=1.3,highpass=f=70,lowpass=f=12000,"
    if denoise:
        post += "afftdn=nf=-28:nr=10,"
    post += "acompressor=threshold=-18dB:ratio=2.5:attack=8:release=120"
    post += (gate_chain(words, total) if words else "") + "[g]"
    mix = echo_chain(words or [], total, echo)
    fin = f"[mix]atrim=0:{total + 1.2:.3f},loudnorm=I=-14:TP=-1.5:LRA=9[out]"
    fc = ";".join(parts + [chain, post, mix, fin])
    ir = tmp / "ir.wav"
    write_impulse(ir)
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", str(ir), "-filter_complex", fc, "-map", "[out]",
         "-ar", "48000", "-ac", "2", str(out)])
    return str(out)


# ----------------------------------------------------------------------------- captions


STYLES = {
    # bold serif, 1–3 words at a time, dead centre — stoicstoriesx
    "serif": dict(font="Caladea", size=92, bold=-1, caps=False, chunk=3, maxchars=18, align=2, mv=690,
                  shadow=3, blur=2.0, pop=True, spacing=0),
    # small all-caps sans phrases, centre — lifelesson401
    "caps": dict(font="Inter", size=44, bold=-1, caps=True, chunk=5, maxchars=28, align=2, mv=700,
                 shadow=2, blur=1.5, pop=False, spacing=1),
    # medium sans sentence fragments, upper third — calverne_brand
    "phrase": dict(font="Inter", size=56, bold=-1, caps=False, chunk=6, maxchars=30, align=8, mv=520,
                   shadow=3, blur=2.0, pop=False, spacing=0),
    # single lowercase word, small, centre — 1make.more.money1
    "word": dict(font="Inter", size=50, bold=0, caps=False, chunk=1, maxchars=14, align=2, mv=700,
                 shadow=2, blur=1.5, pop=False, spacing=0),
}


def chunk_words(words: list[Word], chunk: int, maxchars: int) -> list[tuple[float, float, str]]:
    """Group words into caption chunks; break on punctuation, size, or long pauses."""
    out: list[tuple[float, float, str]] = []
    cur: list[Word] = []

    def flush():
        if cur:
            out.append((cur[0].out_start, cur[-1].out_end, " ".join(w.text for w in cur)))
            cur.clear()

    for i, w in enumerate(words):
        if cur:
            text_len = len(" ".join(x.text for x in cur)) + 1 + len(w.text)
            pause = w.out_start - cur[-1].out_end
            ends_sentence = cur[-1].text[-1] in ".?!"
            ends_clause = cur[-1].text[-1] == ","
            # don't strand a short last word of a sentence on its own card
            nxt_alone = (i + 1 == len(words) or words[i + 1].text[-1] in ".?!,") and len(w.text) <= 4
            full = len(cur) >= chunk or text_len > maxchars
            if (full and not (nxt_alone and text_len <= maxchars + 4)) or pause > 0.5 or ends_sentence \
                    or (ends_clause and len(cur) >= max(1, chunk - 1)):
                flush()
        cur.append(w)
    flush()
    # hold each caption until the next one starts (no flicker gaps), cap the hold at 1.2 s
    held = []
    for i, (a, b, t) in enumerate(out):
        nxt = out[i + 1][0] if i + 1 < len(out) else b + 0.6
        held.append((a, min(nxt, b + 1.2), t))
    return held


EMPHASIS = {
    "money", "rich", "broke", "poor", "lazy", "laziness", "discipline", "focus", "locked", "dream", "dreams",
    "win", "lose", "fight", "fear", "scared", "excuse", "excuses", "nobody", "cares", "alone", "lonely", "god",
    "future", "change", "quit", "never", "success", "successful", "fail", "failure", "prove", "sacrifice", "pain",
    "truth", "respect", "family", "lesson", "wake", "hustle", "millionaire", "million", "billionaire", "lamborghini",
    "peace", "happiness", "happy", "stop", "start", "now", "right", "scrolling", "competition", "bot", "lobby",
    "boring", "comfortable", "uncomfortable", "weekend", "job", "boss", "phone", "filming", "victories",
}


def emphasise(text: str, size: int) -> str:
    """Scale the hitting words up a notch inside the caption."""
    out = []
    for tok in text.split(" "):
        core = re.sub(r"[^a-z0-9']", "", tok.lower())
        if core in EMPHASIS or core.endswith("k") and core[:-1].isdigit() or core.startswith("£") or core.startswith("$"):
            out.append(f"{{\\fs{int(size * 1.16)}}}{tok}{{\\fs{size}}}")
        else:
            out.append(tok)
    return " ".join(out)


def write_ass(words: list[Word], style: str, path: Path, handle: str | None, emphasis: bool = False) -> None:
    st = STYLES[style]
    # ASS colours are &HAABBGGRR
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{st['size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,{st['bold']},0,0,0,100,100,{st['spacing']},0,1,0,{st['shadow']},{st['align']},90,90,{st['mv']},1
Style: Handle,Inter,30,&H66FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,0,1,2,0,0,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for a, b, text in chunk_words(words, st["chunk"], st["maxchars"]):
        if st["caps"]:
            text = text.upper()
        text = text.replace("\\", "").replace("{", "").replace("}", "")
        fx = f"{{\\blur{st['blur']}"
        if st["pop"]:
            fx += "\\fscx90\\fscy90\\t(0,70,\\fscx100\\fscy100)"
        fx += "}"
        if emphasis:
            text = emphasise(text, st["size"])
        lines.append(f"Dialogue: 0,{fmt_ass(a)},{fmt_ass(b)},Cap,,0,0,0,,{fx}{text}\n")
    if handle and words:
        end = words[-1].out_end + 1
        lines.append(f"Dialogue: 0,{fmt_ass(0)},{fmt_ass(end)},Handle,,0,0,0,,{{\\blur1}}{handle}\n")
    path.write_text("".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speaker", required=True, help="talking-head source video")
    ap.add_argument("--start", type=float, required=True, help="source start (s)")
    ap.add_argument("--end", type=float, required=True, help="source end (s)")
    ap.add_argument("--broll", required=True, help="folder of luxury b-roll clips")
    ap.add_argument("--out", required=True)
    ap.add_argument("--style", choices=STYLES, default="serif", help="caption style")
    ap.add_argument("--look", choices=LOOKS, default="moody", help="colour grade")
    ap.add_argument("--hook", type=float, default=3.2, help="seconds on the face before the first b-roll")
    ap.add_argument("--face-ratio", type=float, default=0.5, help="target share of screen time on the speaker")
    ap.add_argument("--closer", type=float, default=2.5, help="final seconds that always stay on the face")
    ap.add_argument("--no-tighten", action="store_true", help="keep pauses instead of cutting dead air")
    ap.add_argument("--no-denoise", action="store_true")
    ap.add_argument("--energy", choices=["classic", "punchy"], default="classic",
                    help="classic: no echo, no zoom hits, slower cuts, plain captions (the posted look); "
                         "punchy: reverb, cut hits, faster b-roll, key-word emphasis")
    ap.add_argument("--echo", type=float, default=None,
                    help="voice echo amount: 0 = dry, 1 = default room echo with swells on punchlines, 1.5 = heavy")
    ap.add_argument("--keep-music", action="store_true",
                    help="skip the Demucs voice isolation (default strips any music bed under the speech)")
    ap.add_argument("--handle", default=None, help="small @handle at the bottom (off by default)")
    ap.add_argument("--model", default="small", help="faster-whisper model size")
    ap.add_argument("--seed", type=int, default=7, help="shot-pattern / b-roll order seed; change for a different cut")
    ap.add_argument("--face-only", action="store_true", help="no b-roll at all")
    ap.add_argument("--crop-top", type=float, default=0.0,
                    help="fraction of the speaker frame to exclude at the top (burned-in TikTok text), e.g. 0.14")
    ap.add_argument("--crop-bottom", type=float, default=0.0, help="same for the bottom (captions, UI)")
    ap.add_argument("--keep-tmp", action="store_true")
    args = ap.parse_args()

    punchy = args.energy == "punchy"
    if args.echo is None:
        args.echo = 1.0 if punchy else 0.0
    rng = random.Random(args.seed)
    speaker = str(Path(args.speaker).resolve())
    sp_info = probe(speaker)
    args.end = min(args.end, sp_info["dur"])
    if args.end <= args.start:
        raise SystemExit(f"--end must be after --start (source is {sp_info['dur']:.1f}s)")
    broll = sorted(str(p) for p in Path(args.broll).iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not broll and not args.face_only:
        raise SystemExit(f"no video files in {args.broll}")

    cache = Path(args.out).resolve().parent / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="clip_", dir=str(cache)))

    print(f"[1/5] transcribing {args.start:.1f}-{args.end:.1f}s …")
    words = transcribe(speaker, args.start, args.end, args.model, cache)
    if not words:
        raise SystemExit("no speech found in that range")
    print("      " + " ".join(w.text for w in words))

    keep = build_keep_ranges(words, args.start, args.end, not args.no_tighten)
    f = src_to_out(keep)
    for w in words:
        w.out_start, w.out_end = f(w.start), f(w.end)
    plan = Plan(words, keep)
    total = plan.duration
    print(f"[2/5] {len(keep)} speech range(s), {total:.1f}s after tightening")

    if args.face_only:
        shots = [Shot("face", 0.0, total, punch=1.0)]
    else:
        hard = []
        acc = 0.0
        for a, b in keep[:-1]:
            acc += b - a
            hard.append(round(acc, 3))
        face_len, broll_len = ((2.0, 3.8), (1.3, 2.4)) if punchy else ((2.4, 4.6), (1.8, 3.4))
        shots = plan_shots(words, total, rng, args.hook, face_len, broll_len, args.face_ratio, args.closer, hard,
                           hits=punchy)
    pieces = split_by_keep(shots, keep)
    if not args.face_only:
        assign_broll(pieces, broll, rng)
    face_t = sum(p.dur for p in pieces if p.kind == "face")
    print(f"[3/5] {len(shots)} shots ({face_t / total:.0%} on the face), {len(pieces)} render pieces")
    for p in pieces:
        src = "speaker" if p.kind == "face" else Path(p.src).name
        print(f"      {p.out_start:6.2f}-{p.out_end:6.2f}  {p.kind:5s} x{p.punch:.2f}  {src}@{p.src_start:.1f}")

    centre = detect_face_center(speaker, args.start, args.end)
    print(f"      face centre: {tuple(round(float(c), 3) for c in centre) if centre else 'not detected, using centre framing'}")

    print("[4/5] rendering pieces …")
    threads = max(1, (os.cpu_count() or 4) // 2)
    with ThreadPoolExecutor(max_workers=2) as ex:
        files = list(ex.map(lambda ip: render_piece(ip[0], ip[1], speaker, sp_info, args.look, tmp,
                                                    random.Random(args.seed + ip[0]), centre, threads,
                                                    args.crop_top, args.crop_bottom),
                            enumerate(pieces)))
    lst = tmp / "concat.txt"
    lst.write_text("".join(f"file '{Path(fp).name}'\n" for fp in files))
    video = tmp / "video.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video)])
    # hold the last frame under the echo tail
    held = tmp / "video_held.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "tpad=stop_mode=clone:stop_duration=1",
         "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-an", str(held)])
    video = held
    audio = render_audio(speaker, keep, tmp, not args.no_denoise, not args.keep_music, words, args.echo)

    print("[5/5] captions + mux …")
    ass = tmp / "captions.ass"
    write_ass(words, args.style, ass, args.handle, emphasis=punchy)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", audio,
         "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
         "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total + 0.8:.3f}", str(out)])
    (out.with_suffix(".plan.json")).write_text(json.dumps({
        "speaker": speaker, "start": args.start, "end": args.end, "style": args.style, "look": args.look,
        "seed": args.seed, "keep": keep, "duration": total,
        "transcript": " ".join(w.text for w in words),
        "shots": [p.__dict__ for p in pieces]}, indent=1))
    if not args.keep_tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"done → {out}  ({total:.1f}s)")


if __name__ == "__main__":
    main()
