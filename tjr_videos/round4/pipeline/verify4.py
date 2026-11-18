"""Sync proof: for every cut I placed (drop + each B-roll cut), offset to the nearest audio transient in the rendered file."""
import glob, os, json, subprocess, sys, numpy as np, librosa
d=sys.argv[1]; FPS=30
for f in sorted(glob.glob(f"{d}/*.mp4")):
    c=json.load(open(f[:-4]+".cuts.json"))
    subprocess.run(["ffmpeg","-v","error","-y","-i",f,"-vn","-ac","1","-ar","22050","tmp/v.wav"])
    y,sr=librosa.load("tmp/v.wav",sr=22050); hop=128
    o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,aggregate=np.median); ol=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,fmax=200,n_mels=32)
    o=o/o.max()+ol/ol.max(); t=librosa.frames_to_time(np.arange(len(o)),sr=sr,hop_length=hop)
    pk=librosa.util.peak_pick(o,pre_max=20,post_max=20,pre_avg=60,post_avg=60,delta=0.12,wait=20); hits=t[pk]
    offs=[]
    for fr in [c["drop_frame"]]+c["cut_frames"]:
        ct=fr/FPS; j=np.argmin(np.abs(hits-ct)); offs.append(int(round((hits[j]-ct)*1000)))
    print(f"{os.path.basename(f):22s} drop+{len(c['cut_frames'])} cuts  offset to nearest hit (ms): {offs}   worst={max(abs(x) for x in offs)}ms")
