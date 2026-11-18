"""Round 3 assembler: self-sourced bait + self-sourced Regera shots + TikTok sound fetched from TikTok."""
import json, os, subprocess, sys
sys.path.insert(0, "scripts"); from caption import render
SND = json.load(open("sounds2.json"))
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True)
C = "r3clean"
DROP = {"S1_ballerszn":2.95,"S2_bannu":6.11,"S3_salman":3.69,"S4_404oskar":6.41,"S5_gsgroup":4.0,"S6_luxuryxsh":4.89,"S7_useheadset":6.35,"S8_calebgordenn":2.73,"S9_northpole":5.02}
TAIL = {"S1_ballerszn":5.3,"S2_bannu":5.0,"S3_salman":6.0,"S4_404oskar":6.0,"S5_gsgroup":5.0,"S6_luxuryxsh":4.4,"S7_useheadset":5.0,"S8_calebgordenn":5.3,"S9_northpole":5.0}
def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True).stdout)
def seg(src, start, length, speed, idx):
    out = f"tmp/seg_{idx:02d}.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{start:.3f}","-i",src,"-t",f"{length/speed+0.05:.3f}","-vf",f"setpts=PTS/{speed},fps=30","-t",f"{length:.3f}",
                    "-c:v","libx264","-crf","16","-preset","fast","-pix_fmt","yuv420p",out],check=True)
    return out
def grid(snd, drop, end):
    s = SND[snd]; b = [x for x in s["beats"] if drop + 0.2 < x < end - 0.3]
    if len(b) < 4:
        per = 60.0 / s["tempo"]; b = [drop + per * i for i in range(1, 60)]; b = [x for x in b if x < end - 0.3]
    return b
def build(sp):
    name, snd = sp["name"], sp["sound"]; drop = DROP[snd]; end = drop + TAIL[snd]
    beats = grid(snd, drop, end); parts = []; idx = 0
    # part 1: bait (pre-cleaned, starts at its own 0)
    bait = f"{C}/{sp['bait']}.mp4"; bs = sp.get("bait_start", 0.0); avail = dur(bait) - bs
    speed = max(0.6, min(1.0, avail / drop)); L = min(avail / speed, drop)
    parts.append(seg(bait, bs, L, speed, idx)); idx += 1
    if drop - L > 0.05:
        hold = f"tmp/seg_{idx:02d}.mp4"
        subprocess.run(["ffmpeg","-v","error","-y","-sseof","-0.1","-i",parts[-1],"-vf",f"tpad=stop_mode=clone:stop_duration={drop-L+0.2:.3f}","-t",f"{drop-L:.3f}","-c:v","libx264","-crf","16","-pix_fmt","yuv420p",hold],check=True)
        parts.append(hold); idx += 1
    # part 2: B-roll on the beat grid
    steps = sp.get("steps", [2,2,1,1,1,2]); cuts=[]; i=-1
    for st in steps * 6:
        i += st
        if i >= len(beats): break
        cuts.append(beats[i])
    times = [drop] + [c for c in cuts if c - drop > 0.4] + [end]
    shots = sp["broll"]; si = 0
    for k in range(len(times)-1):
        L = times[k+1]-times[k]
        while L > 0.08:
            f = f"{C}/{shots[si % len(shots)]}.mp4"; si += 1; avail = dur(f)
            if avail >= L: parts.append(seg(f, 0, L, 1.0, idx)); idx += 1; L = 0
            elif avail/0.75 >= L: parts.append(seg(f, 0, L, avail/L, idx)); idx += 1; L = 0
            else: parts.append(seg(f, 0, avail, 1.0, idx)); idx += 1; L -= avail
    y = sp.get("y", 0.64)
    render(sp["cap1"], "tmp/cap1.png", y_center=y); render(sp["cap2"], "tmp/cap2.png", y_center=y)
    open("tmp/list.txt","w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg","-v","error","-y","-f","concat","-safe","0","-i","tmp/list.txt","-c","copy","tmp/joined.mp4"],check=True)
    out = f"{OUT}/{name}.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-i","tmp/joined.mp4","-i","tmp/cap1.png","-i","tmp/cap2.png","-i",SND[snd]["file"],
                    "-filter_complex",f"[0:v][1:v]overlay=0:0:enable='lt(t,{drop})'[a];[a][2:v]overlay=0:0:enable='gte(t,{drop})'[v];[3:a]atrim=0:{end:.3f},asetpts=PTS-STARTPTS[au]",
                    "-map","[v]","-map","[au]","-t",f"{end:.3f}","-c:v","libx264","-crf","18","-preset","medium","-pix_fmt","yuv420p","-r","30","-c:a","aac","-b:a","160k","-movflags","+faststart",out],check=True)
    print(f"{name}: {dur(out):.2f}s sound={snd} drop@{drop} cuts={[round(t,2) for t in times]}")
specs = json.load(open(os.environ.get("SPECS","specs_round3.json")))
only = sys.argv[2:]
for sp in specs:
    if only and sp["name"] not in only: continue
    build(sp)
