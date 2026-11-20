import glob, os, json, numpy as np, librosa
from faster_whisper import WhisperModel
wm=WhisperModel("base",device="cpu",compute_type="int8")
out={}
for f in sorted(glob.glob("snd2/*.mp3")):
    k=os.path.basename(f)[:-4]
    try: y,sr=librosa.load(f,sr=16000)
    except Exception as e: print(k,"LOAD FAIL"); continue
    dur=len(y)/sr; hop=80
    r=librosa.feature.rms(y=y,frame_length=400,hop_length=hop)[0]; t=librosa.frames_to_time(np.arange(len(r)),sr=sr,hop_length=hop)
    w=int(0.6*sr/hop); c=[]
    for i in range(w,len(r)-w):
        if t[i]<1.0 or t[i]>dur-5.5: continue
        q=r[i:i+w].mean()/(r[i-w:i].mean()+1e-6); c.append((float(q),float(t[i])))
    c.sort(reverse=True); top=[]
    for q,tt in c:
        if all(abs(tt-x[1])>1.5 for x in top): top.append((round(q,1),round(tt,2)))
        if len(top)==3: break
    # beat regularity after best drop
    d=top[0][1] if top else 0
    o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=64); to=librosa.frames_to_time(np.arange(len(o)),sr=sr,hop_length=64)
    base=o[(to>d)&(to<d+6)].mean()+1e-9; ww=int(0.017*sr/64)
    best=(0,0)
    for p in np.arange(0.35,1.3,0.002):
        g=d+p*np.arange(1,int(6/p)+1); idx=np.clip((g*sr/64).round().astype(int),ww,len(o)-ww-1)
        s=np.mean([o[i-ww:i+ww+1].max() for i in idx])/base
        if s>best[0]: best=(s,p)
    segs,_=wm.transcribe(y[:int(12*sr)].astype(np.float32),beam_size=1,vad_filter=True)
    words=" ".join(s.text.strip() for s in segs)
    out[k]={"file":f,"dur":round(dur,1),"drops":top,"period":round(float(best[1]),3),"beatscore":round(float(best[0]),2),"words":words[:90]}
    print(f"{k:13s} {dur:5.1f}s drops={top} beat={best[1]:.3f}s({60/best[1]:.0f}bpm) score={best[0]:.1f} words='{words[:70]}'")
json.dump(out,open("snd2/scan.json","w"),indent=1)
