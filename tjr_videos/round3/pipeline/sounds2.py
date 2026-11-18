import glob, os, json, numpy as np, librosa
out={}
for f in sorted(glob.glob("sounds_dl/*.mp3")):
    k=os.path.basename(f)[:-4]
    y,sr=librosa.load(f,sr=16000); dur=len(y)/sr
    rms=librosa.feature.rms(y=y,frame_length=1024,hop_length=160)[0]
    t=librosa.frames_to_time(np.arange(len(rms)),sr=sr,hop_length=160)
    w=int(0.5*sr/160); best=(0,0)
    for i in range(w,min(len(rms)-w,int(12*sr/160))):   # look for the biggest step-up inside the first 12 s
        a=rms[i-w:i].mean(); b=rms[i:i+w].mean()
        if b/(a+1e-6)>best[0]: best=(b/(a+1e-6),t[i])
    tempo,bt=librosa.beat.beat_track(y=y,sr=sr,units='time'); tp=float(np.atleast_1d(tempo)[0])
    on=librosa.onset.onset_detect(y=y,sr=sr,units='time')
    secs=[float(rms[(t>=s)&(t<s+1)].mean()*1000) for s in range(int(dur))]
    out[k]={"file":f,"dur":round(dur,3),"drop":round(float(best[1]),2),"ratio":round(float(best[0]),1),"tempo":round(tp,1),
            "beats":[round(float(b),3) for b in bt],"onsets":[round(float(o),3) for o in on]}
    print(f"{k:16s} dur={dur:5.1f} drop@{best[1]:.2f} x{best[0]:.1f} tempo={tp:.0f} rms/s:"," ".join(f"{v:.0f}" for v in secs[:16]))
json.dump(out,open("sounds2.json","w"),indent=1)
