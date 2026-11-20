"""Round 7: >=3 s bait -> drop -> fixed beat pattern (strict grid, phase locked to the drop) -> 7 s of TJR.
All shots play at 1x from a native-res pool; a slot is filled by the first listed shot with enough unused length."""
import json, os, subprocess, sys, numpy as np, librosa
sys.path.insert(0, "scripts"); from caption import render
B7 = json.load(open("beat7.json")); P = json.load(open(os.environ.get("PLAN","plan8.json"))); H = json.load(open("hits5.json"))
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True)
C = "r8clean"; FPS = 30
def nframes(p): return int(subprocess.run(["ffprobe","-v","error","-count_packets","-select_streams","v:0","-show_entries","stream=nb_read_packets","-of","csv=p=0",p],capture_output=True,text=True).stdout.strip() or 0)
def seg(src, start_f, n, idx):
    out = f"tmp/seg_{idx:02d}.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{start_f/FPS:.4f}","-i",src,"-vf",f"fps={FPS},tpad=stop_mode=clone:stop_duration=2","-frames:v",str(n),
                    "-c:v","libx264","-crf","15","-preset","medium","-pix_fmt","yuv420p",out],check=True)
    return out
def build(sp):
    name, snd = sp["name"], sp["sound"]; pl = P[snd]
    off = pl["offset"]; per = pl["period"]; drop_s = B7[snd]["drop"]; pad = pl.get("pad", 0.0)
    drop = drop_s - off + pad
    f_drop = int(drop*FPS)
    # strict grid from the drop, then each grid point snapped to the strongest onset within +-SNAP s
    from onsets import peaks as _pk
    peaks, _, o, tt = _pk(H[snd]["file"])
    # grid from the drop; each grid point moves to the STRONGEST onset peak within +-25% of a beat (so every cut is a real hit
    # while spacing stays regular); the next grid point is measured from the moved one so the pattern never drifts
    pks, pst, _, _ = _pk(H[snd]["file"])
    W = pl.get("snap", 0.05); times = [drop]; tb = drop_s   # +-50 ms: a cut may move at most ~1.5 frames to sit on the hit
    for b in pl["pattern"]:
        tgt = tb + b*per; m = (pks > tgt-W) & (pks < tgt+W)
        tb = float(pks[m][np.argmax(pst[m])]) if m.any() else tgt
        times.append(tb - off + pad)
    bounds = [f_drop] + [int(round(x*FPS)) for x in times[1:]]
    f_end = bounds[-1]
    parts = []; idx = 0
    bait = f"{C}/{sp['bait']}.mp4"; bs = int(sp.get("bait_start",0)*FPS)
    assert nframes(bait)-bs >= f_drop, f"{name}: bait too short ({nframes(bait)-bs} < {f_drop})"
    parts.append(seg(bait, bs, f_drop, idx)); idx += 1
    SRC = json.load(open(os.environ.get("SRCS","sources9.json")))
    def segsrc(src, t0, n, idx, crop=None, speed=1.0):
        out = f"tmp/seg_{idx:02d}.mp4"
        subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{t0:.4f}","-i",src,"-an","-vf",
                        (crop + ",unsharp=5:5:0.4," if crop else "") + (f"setpts=PTS/{speed:.4f}," if speed < 0.999 else "") + f"scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,fps={FPS}","-frames:v",str(n),
                        "-c:v","libx264","-crf","15","-preset","medium","-pix_fmt","yuv420p",out],check=True)
        assert nframes(out) == n, f"{name}: window short ({nframes(out)}/{n})"
        return out
    slots = [bounds[k+1]-bounds[k] for k in range(len(bounds)-1)]
    for n in slots: assert n >= 25, f"{name}: slot of {n} frames"
    plan = []                                                    # (source, count, start)
    for e in sp["sources"]: plan.append((e[0], e[1], e[2] if len(e) > 2 else None))
    assert sum(c for _, c, _ in plan) == len(slots), f"{name}: plan covers {sum(c for _,c,_ in plan)} of {len(slots)} slots"
    k = 0; log = []; usedmap = {}; skip_prev = 0
    for sname, cnt, start in plan:
        S = SRC[sname]; segs = [tuple(x) for x in S["segs"]]
        cur = start if start is not None else segs[0][0]
        for j in range(cnt):
            L = slots[k]/FPS + 0.02
            rem = [(max(a, cur), b) for a, b in segs if b > cur]
            usable = sum(max(0, b - a) for a, b in rem); left = sum(slots[k:k+cnt-j])/FPS
            skip = max(0.3, min(2.0, (usable - left) / max(1, cnt - j)))
            used = usedmap.setdefault(sname, [])
            def free(a, b): return all(b <= u0 or a >= u1 for u0, u1 in used)
            def find(c0):
                for a, b in segs:
                    t = max(a, c0)
                    while t + L <= b:
                        if free(t, t + L): return t
                        t += 0.1
                return None
            place = find(cur); spd = 1.0
            if place is None and S.get("minspeed"):
                a0, b0 = max(segs, key=lambda x: x[1]-x[0])
                if (b0 - a0) >= S["minspeed"] * L and free(a0, b0): place = a0; spd = (b0 - a0) / L
            if place is None and log: place = find(cur - skip_prev + 0.3) if skip_prev else None
            if place is None: place = find(segs[0][0])
            assert place is not None, f"{name}: no unused window of {L:.2f}s left in {sname}"
            used.append((place, place + L)); skip_prev = skip
            parts.append(segsrc(S["file"], place, slots[k], idx, S.get("crop"), spd)); idx += 1
            log.append(f"{sname}@{place:.2f}" + (f"x{spd:.2f}" if spd < 0.999 else "")); cur = place + L + skip; k += 1
    print("   windows:", " ".join(log))
    y = sp.get("y",0.64); render(sp["cap1"],"tmp/cap1.png",y_center=sp.get("cap1y",y)); render(sp["cap2"],"tmp/cap2.png",y_center=y)
    open("tmp/list.txt","w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i","tmp/list.txt","-c","copy","tmp/joined.mp4"],check=True)
    out = f"{OUT}/{name}.mp4"; T = f_end/FPS
    sdur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",H[snd]["file"]],capture_output=True,text=True).stdout)
    assert off + T - pad <= sdur + 0.02, f"{name}: sound runs out ({off+T-pad:.2f}s needed, {sdur:.2f}s available)"
    subprocess.run(["ffmpeg","-v","error","-y","-i","tmp/joined.mp4","-i","tmp/cap1.png","-i","tmp/cap2.png","-i",H[snd]["file"],
        "-filter_complex",f"[0:v][1:v]overlay=0:0:enable='lt(n,{f_drop})'[a];[a][2:v]overlay=0:0:enable='gte(n,{f_drop})'[v];[3:a]atrim={off:.4f}:{off+T:.4f},asetpts=PTS-STARTPTS{(",adelay=%d|%d" % (int(pad*1000), int(pad*1000))) if pad > 0 else ""},atrim=0:{T:.4f}{(",afade=t=in:st=0:d=%.2f" % pl["fade"]) if pl.get("fade") else ""}[au]",
        "-map","[v]","-map","[au]","-frames:v",str(f_end),"-c:v","libx264","-crf","17","-preset","slow","-pix_fmt","yuv420p","-r",str(FPS),"-c:a","aac","-b:a","192k","-movflags","+faststart",out],check=True)
    json.dump({"offset":off,"pad":pad,"fade":pl.get("fade",0),"period":per,"drop_frame":f_drop,"cut_frames":bounds[1:-1],"end_frame":f_end,"sound":snd,"pattern":pl["pattern"]},open(f"{OUT}/{name}.cuts.json","w"))
    print(f"{name}: {T:.2f}s  bait {drop:.2f}s | drop | {T-drop:.2f}s  {snd} {60/per:.0f}bpm shots={[round(b*per,2) for b in pl['pattern']]}")
specs = json.load(open(os.environ.get("SPECS","specs_round9.json"))); only = sys.argv[2:]
for sp in specs:
    if only and sp["name"] not in only: continue
    try: build(sp)
    except AssertionError as e: print('FAILED', e)
