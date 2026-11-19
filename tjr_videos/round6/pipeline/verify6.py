"""On-beat proof: for each render, onset strength at the placed cut frames vs the average, plus offset to nearest onset peak."""
import glob, os, json, subprocess, numpy as np, librosa
FPS=30
for f in sorted(glob.glob("out6/*.mp4")):
    c=json.load(open(f[:-4]+".cuts.json"))
    subprocess.run(["ffmpeg","-v","error","-y","-i",f,"-vn","-ac","1","-ar","22050","tmp/v.wav"])
    y,sr=librosa.load("tmp/v.wav",sr=22050); hop=128
    o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,aggregate=np.median); ol=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,fmax=200,n_mels=32)
    o=o/o.max()+ol/ol.max(); t=librosa.frames_to_time(np.arange(len(o)),sr=sr,hop_length=hop)
    pk=librosa.util.peak_pick(o,pre_max=15,post_max=15,pre_avg=40,post_avg=40,delta=0.08,wait=15); hits=t[pk]
    cuts=[c["drop_frame"]]+c["cut_frames"]; offs=[]; strength=[]
    for fr in cuts:
        ct=fr/FPS; j=np.argmin(np.abs(hits-ct)); offs.append(int(round((hits[j]-ct)*1000)))
        m=(t>=ct-0.04)&(t<=ct+0.07); strength.append(o[m].max())
    base=o[(t>c["drop_frame"]/FPS)].mean()
    print(f"{os.path.basename(f):20s} offsets(ms)={offs}  onset@cut/avg={np.mean(strength)/base:.1f}x")
