"""Round 4 assembler. Frame-accurate: every cut lands on a detected drum hit (hits.json); segments are exact frame counts."""
import json, os, subprocess, sys
sys.path.insert(0, "scripts"); from caption import render
H = json.load(open("hits5.json"))
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True)
C = "r4clean"; FPS = 30
def nframes(p): return int(subprocess.run(["ffprobe","-v","error","-count_packets","-select_streams","v:0","-show_entries","stream=nb_read_packets","-of","csv=p=0",p],capture_output=True,text=True).stdout.strip() or 0)
def seg(src, start_f, n, speed, idx):
    """exactly n frames from src starting at frame start_f; speed<1 slows; tpad guarantees length."""
    out = f"tmp/seg_{idx:02d}.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{start_f/FPS:.4f}","-i",src,"-vf",f"setpts=PTS/{speed},fps={FPS},tpad=stop_mode=clone:stop_duration=4","-frames:v",str(n),
                    "-c:v","libx264","-crf","16","-preset","fast","-pix_fmt","yuv420p",out],check=True)
    return out
def build(sp):
    name, snd = sp["name"], sp["sound"]; h = H[snd]
    off = h.get("offset", 0.0); drop, end = h["drop"]-off, h["end"]-off
    f_drop = int(drop*FPS)                          # cut just before the hit lands
    f_end = int(round(end*FPS))
    # pick hits: keep all strong hits spaced >= 0.33 s, optional max count
    cuts=[]; last=drop
    for t in [x-off for x in h["hits"]]:
        if t-last >= 0.33 and end-t >= 0.3: cuts.append(t); last=t
    maxc = sp.get("max_cuts", 8); cuts = cuts[:maxc]
    frames = [f_drop] + [int(round(t*FPS)) for t in cuts] + [f_end]
    parts=[]; idx=0
    # part 1: bait, exactly f_drop frames
    bait=f"{C}/{sp['bait']}.mp4"; avail=nframes(bait)-int(sp.get("bait_start",0)*FPS)
    speed = max(0.6, min(1.0, avail/f_drop)) if avail < f_drop else 1.0
    parts.append(seg(bait, int(sp.get("bait_start",0)*FPS), f_drop, speed, idx)); idx+=1
    # part 2: one shot per interval
    shots=sp["broll"]; si=0
    for k in range(len(frames)-1):
        n=frames[k+1]-frames[k]
        src=f"{C}/{shots[si%len(shots)]}.mp4"; si+=1
        avail=nframes(src); sp_=1.0
        if avail < n: sp_=max(0.6, avail/n)          # slow a short shot so it still reaches the next hit
        parts.append(seg(src, 0, n, sp_, idx)); idx+=1
    y=sp.get("y",0.64); render(sp["cap1"],"tmp/cap1.png",y_center=y); render(sp["cap2"],"tmp/cap2.png",y_center=y)
    open("tmp/list.txt","w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i","tmp/list.txt","-c","copy","tmp/joined.mp4"],check=True)
    out=f"{OUT}/{name}.mp4"; T=f_drop/FPS
    subprocess.run(["ffmpeg","-v","error","-y","-i","tmp/joined.mp4","-i","tmp/cap1.png","-i","tmp/cap2.png","-i",h["file"],
        "-filter_complex",f"[0:v][1:v]overlay=0:0:enable='lt(n,{f_drop})'[a];[a][2:v]overlay=0:0:enable='gte(n,{f_drop})'[v];[3:a]atrim={off:.4f}:{off+f_end/FPS:.4f},asetpts=PTS-STARTPTS[au]",
        "-map","[v]","-map","[au]","-frames:v",str(f_end),"-c:v","libx264","-crf","18","-preset","medium","-pix_fmt","yuv420p","-r",str(FPS),"-c:a","aac","-b:a","160k","-movflags","+faststart",out],check=True)
    json.dump({"offset":off,"drop_frame":f_drop,"cut_frames":frames[1:-1],"end_frame":f_end,"sound":snd},open(f"{OUT}/{name}.cuts.json","w"))
    print(f"{name}: {f_end/FPS:.2f}s sound={snd} drop@{drop:.3f} (frame {f_drop}) cuts={[round(t,2) for t in cuts]}")
specs=json.load(open(os.environ.get("SPECS","specs_round5.json")))
only=sys.argv[2:]
for sp in specs:
    if only and sp["name"] not in only: continue
    build(sp)
