"""Round 7: >=3 s bait -> drop -> fixed beat pattern (strict grid, phase locked to the drop) -> 7 s of TJR.
All shots play at 1x from a native-res pool; a slot is filled by the first listed shot with enough unused length."""
import json, os, subprocess, sys, numpy as np, librosa
sys.path.insert(0, "scripts"); from caption import render
B7 = json.load(open("beat7.json")); P = json.load(open("plan7.json")); H = json.load(open("hits5.json"))
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True)
C = "r7clean"; FPS = 30
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
    W = pl.get("snap", 0.25) * per; times = [drop]; tb = drop_s
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
    shots = sp["broll"] + [x for x in ["r_rear","r_street","r_pov","r_wheel","r_door","r_doorsup","r_dash","r_wide","r_dashred","r_carweek"] if x not in sp["broll"]]; pos = {s_: 0 for s_ in shots}; lens = {s_: nframes(f"{C}/{s_}.mp4") for s_ in shots}
    for k in range(len(bounds)-1):
        n = bounds[k+1]-bounds[k]; pick = None
        for s_ in shots:
            if lens[s_]-pos[s_] >= n: pick = s_; break
        assert pick, f"{name}: no shot long enough for slot {k} ({n} frames)"
        parts.append(seg(f"{C}/{pick}.mp4", pos[pick], n, idx)); idx += 1; pos[pick] += n + 2
    y = sp.get("y",0.64); render(sp["cap1"],"tmp/cap1.png",y_center=y); render(sp["cap2"],"tmp/cap2.png",y_center=y)
    open("tmp/list.txt","w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i","tmp/list.txt","-c","copy","tmp/joined.mp4"],check=True)
    out = f"{OUT}/{name}.mp4"; T = f_end/FPS
    subprocess.run(["ffmpeg","-v","error","-y","-i","tmp/joined.mp4","-i","tmp/cap1.png","-i","tmp/cap2.png","-i",H[snd]["file"],
        "-filter_complex",f"[0:v][1:v]overlay=0:0:enable='lt(n,{f_drop})'[a];[a][2:v]overlay=0:0:enable='gte(n,{f_drop})'[v];[3:a]atrim={off:.4f}:{off+T:.4f},asetpts=PTS-STARTPTS{(",adelay=%d|%d" % (int(pad*1000), int(pad*1000))) if pad > 0 else ""},atrim=0:{T:.4f}[au]",
        "-map","[v]","-map","[au]","-frames:v",str(f_end),"-c:v","libx264","-crf","17","-preset","slow","-pix_fmt","yuv420p","-r",str(FPS),"-c:a","aac","-b:a","192k","-movflags","+faststart",out],check=True)
    json.dump({"offset":off,"pad":pad,"period":per,"drop_frame":f_drop,"cut_frames":bounds[1:-1],"end_frame":f_end,"sound":snd,"pattern":pl["pattern"]},open(f"{OUT}/{name}.cuts.json","w"))
    print(f"{name}: {T:.2f}s  bait {drop:.2f}s | drop | {T-drop:.2f}s  {snd} {60/per:.0f}bpm shots={[round(b*per,2) for b in pl['pattern']]}")
specs = json.load(open(os.environ.get("SPECS","specs_round7.json"))); only = sys.argv[2:]
for sp in specs:
    if only and sp["name"] not in only: continue
    build(sp)
