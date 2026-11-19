"""Round 6: >=3 s bait -> drop -> ~7 s of B-roll cut on the song's beat grid (phase locked to the drop).
Sound can be offset (start later) or padded with leading silence so the drop lands at 3.0-3.6 s."""
import json, os, subprocess, sys, numpy as np, librosa
sys.path.insert(0, "scripts"); from caption import render
G = json.load(open("grid.json")); P = json.load(open("plan6.json"))
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True)
C = "r6clean"; FPS = 30
def nframes(p): return int(subprocess.run(["ffprobe","-v","error","-count_packets","-select_streams","v:0","-show_entries","stream=nb_read_packets","-of","csv=p=0",p],capture_output=True,text=True).stdout.strip() or 0)
def seg(src, start_f, n, speed, idx):
    out = f"tmp/seg_{idx:02d}.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{start_f/FPS:.4f}","-i",src,"-vf",f"setpts=PTS/{speed},fps={FPS},tpad=stop_mode=clone:stop_duration=4","-frames:v",str(n),
                    "-c:v","libx264","-crf","16","-preset","fast","-pix_fmt","yuv420p",out],check=True)
    return out
def build(sp):
    name, snd = sp["name"], sp["sound"]; g = G[snd]; pl = P[snd]
    off = pl["offset"]; pad = pl.get("pad", 0.0)            # pad = leading silence added before the sound
    drop = g["drop"] - off + pad; per = g["period"]
    # choose cut points among the sound's onset peaks after the drop: DP maximising sum(strength - cost),
    # shots between MIN (one full beat) and MAX seconds, part 2 ending 6.6-7.6 s after the drop
    MIN, MAX = pl.get("min", 0.7), pl.get("max", 1.6)
    ys, sr_ = librosa.load(g["file"], sr=22050); hop = 128
    o = librosa.onset.onset_strength(y=ys, sr=sr_, hop_length=hop, aggregate=np.median)
    ol = librosa.onset.onset_strength(y=ys, sr=sr_, hop_length=hop, fmax=200, n_mels=32)
    o = o/o.max() + ol/ol.max(); tt = librosa.frames_to_time(np.arange(len(o)), sr=sr_, hop_length=hop)
    pk = librosa.util.peak_pick(o, pre_max=15, post_max=15, pre_avg=40, post_avg=40, delta=0.06, wait=10)
    d_s = g["drop"]; win = (tt[pk] > d_s + MIN - 0.03) & (tt[pk] < d_s + 7.7)
    cand = [(float(tt[i]) - off + pad, float(o[i])) for i in pk[win]]
    avg = float(np.median([c[1] for c in cand])); PEN = pl.get("cost", 0.9) * avg
    pts = [drop] + [c[0] for c in cand]; sc = [0.0] + [c[1] - PEN for c in cand]
    best = [(-1e9, -1)] * len(pts); best[0] = (0.0, -1)
    for i in range(1, len(pts)):
        for j in range(0, i):
            gap = pts[i] - pts[j]
            if MIN - 0.03 <= gap <= MAX + 0.03 and best[j][0] > -1e8:
                v = best[j][0] + sc[i]
                if v > best[i][0]: best[i] = (v, j)
    cands = [i for i in range(1, len(pts)) if 6.6 <= pts[i] - drop <= 7.7 and best[i][0] > -1e8]
    if not cands: cands = [i for i in range(1, len(pts)) if pts[i] - drop >= 6.0 and best[i][0] > -1e8]
    end_i = max(cands, key=lambda i: best[i][0])
    chain = []; i = end_i
    while i > 0: chain.append(i); i = best[i][1]
    chain = chain[::-1]
    bounds_t = [drop] + [pts[i] for i in chain]
    pattern = [round(bounds_t[k+1] - bounds_t[k], 2) for k in range(len(bounds_t)-1)]
    f_drop = int(drop*FPS)
    bounds = [f_drop] + [int(round(x*FPS)) for x in bounds_t[1:]]
    f_end = bounds[-1]
    parts = []; idx = 0
    bait = f"{C}/{sp['bait']}.mp4"; bs = int(sp.get("bait_start",0)*FPS); avail = nframes(bait)-bs
    speed = max(0.75, min(1.0, avail/f_drop)) if avail < f_drop else 1.0
    parts.append(seg(bait, bs, f_drop, speed, idx)); idx += 1
    # assign shots to beat slots: a slot takes an unused window of a listed shot that is long enough (1x speed);
    # long shots are split into several windows; only if nothing fits is the longest remaining shot slowed (>=0.8x)
    shots = sp["broll"]; pos = {s_: 0 for s_ in shots}; lens = {s_: nframes(f"{C}/{s_}.mp4") for s_ in shots}
    order = list(shots)
    for k in range(len(bounds)-1):
        n = bounds[k+1]-bounds[k]; pick = None
        for s_ in order:
            if lens[s_]-pos[s_] >= n: pick = s_; break
        if pick is None:
            pick = max(order, key=lambda s_: lens[s_]-pos[s_])
            if lens[pick]-pos[pick] < 4: pos[pick] = 0
        rem = lens[pick]-pos[pick]; sp_ = 1.0 if rem >= n else max(0.8, rem/n)
        parts.append(seg(f"{C}/{pick}.mp4", pos[pick], n, sp_, idx)); idx += 1
        pos[pick] += int(n*sp_) + 1
        order.remove(pick); order.append(pick)              # rotate so the same shot is not reused back to back
    y = sp.get("y",0.64); render(sp["cap1"],"tmp/cap1.png",y_center=y); render(sp["cap2"],"tmp/cap2.png",y_center=y)
    open("tmp/list.txt","w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i","tmp/list.txt","-c","copy","tmp/joined.mp4"],check=True)
    out = f"{OUT}/{name}.mp4"; T = f_end/FPS
    afilt = f"[3:a]atrim={off:.4f}:{off+T-pad+0.1:.4f},asetpts=PTS-STARTPTS" + (f",adelay={int(pad*1000)}|{int(pad*1000)}" if pad>0 else "") + f",atrim=0:{T:.4f}[au]"
    subprocess.run(["ffmpeg","-v","error","-y","-i","tmp/joined.mp4","-i","tmp/cap1.png","-i","tmp/cap2.png","-i",g["file"],
        "-filter_complex",f"[0:v][1:v]overlay=0:0:enable='lt(n,{f_drop})'[a];[a][2:v]overlay=0:0:enable='gte(n,{f_drop})'[v];{afilt}",
        "-map","[v]","-map","[au]","-frames:v",str(f_end),"-c:v","libx264","-crf","18","-preset","medium","-pix_fmt","yuv420p","-r",str(FPS),"-c:a","aac","-b:a","160k","-movflags","+faststart",out],check=True)
    json.dump({"offset":off,"pad":pad,"period":per,"drop_frame":f_drop,"cut_frames":bounds[1:-1],"end_frame":f_end,"sound":snd},open(f"{OUT}/{name}.cuts.json","w"))
    print(f"{name}: {T:.2f}s  bait {drop:.2f}s | drop | {T-drop:.2f}s  sound={snd} {g['bpm']}bpm shots(s)={pattern}")
specs = json.load(open(os.environ.get("SPECS","specs_round6.json"))); only = sys.argv[2:]
for sp in specs:
    if only and sp["name"] not in only: continue
    build(sp)
