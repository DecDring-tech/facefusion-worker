"""Per placed cut, on the RENDERED audio: onset strength within one frame of the cut vs the track average (a hit is >=2.5x),
and the offset from the cut to the local onset maximum within +-50 ms."""
import glob, os, json, subprocess, sys, numpy as np
sys.path.insert(0,"scripts"); from onsets import peaks
FPS=30
for f in sorted(glob.glob(sys.argv[1]+"/*.mp4")):
    c=json.load(open(f[:-4]+".cuts.json"))
    subprocess.run(["ffmpeg","-v","error","-y","-i",f,"-vn","-ac","1","-ar","22050","tmp/v.wav"])
    _,_,o,t=peaks("tmp/v.wav"); base=o[t>c["drop_frame"]/FPS].mean()
    ratios=[]; offs=[]
    for fr in [c["drop_frame"]]+c["cut_frames"]:
        ct=fr/FPS; m=(t>=ct-0.034)&(t<=ct+0.034); ratios.append(o[m].max()/base)
        w=(t>=ct-0.05)&(t<=ct+0.05); offs.append(int(round((t[w][np.argmax(o[w])]-ct)*1000)))
    print(f"{os.path.basename(f):20s} hit strength at each cut (x avg)={[round(r,1) for r in ratios]}  min={min(ratios):.1f}x  offset to peak (ms)={offs}")
