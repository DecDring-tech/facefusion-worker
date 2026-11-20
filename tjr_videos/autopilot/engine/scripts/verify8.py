"""Round-8 checks on the rendered file: (1) hit strength + offset at every placed cut; (2) scene-change scan: every visual cut
must be one of the placed cuts, and no two visual cuts closer than 0.9 s (catches any stray flash frame)."""
import glob, os, json, subprocess, sys, re, numpy as np
sys.path.insert(0,"scripts"); from onsets import peaks
FPS=30
for f in sorted(glob.glob(sys.argv[1]+"/*.mp4")):
    c=json.load(open(f[:-4]+".cuts.json")); placed=[c["drop_frame"]]+c["cut_frames"]
    subprocess.run(["ffmpeg","-v","error","-y","-i",f,"-vn","-ac","1","-ar","22050","tmp/v.wav"])
    _,_,o,t=peaks("tmp/v.wav"); base=o[t>c["drop_frame"]/FPS].mean(); ratios=[]; offs=[]
    for fr in placed:
        ct=fr/FPS; m=(t>=ct-0.034)&(t<=ct+0.034); ratios.append(float(o[m].max()/base))
        w=(t>=ct-0.05)&(t<=ct+0.05); offs.append(int(round((t[w][np.argmax(o[w])]-ct)*1000)))
    err=subprocess.run(["ffmpeg","-i",f,"-vf","select='gt(scene,0.25)',showinfo","-an","-f","null","-"],capture_output=True,text=True).stderr
    vis=[int(round(float(x)*FPS)) for x in re.findall(r"pts_time:([0-9.]+)",err)]
    stray=[v for v in vis if min(abs(v-p) for p in placed)>1]
    gaps=np.diff(sorted(set(vis+placed))); mingap=gaps.min()/FPS if len(gaps) else 9
    print(f"{os.path.basename(f):18s} hits={[round(r,1) for r in ratios]} offs(ms)={offs}  stray_visual_cuts={stray}  shortest_shot={mingap:.2f}s")
