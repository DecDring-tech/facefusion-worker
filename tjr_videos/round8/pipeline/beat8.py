"""High-resolution period estimate per sound: score = mean onset (max within +-17 ms, one video frame) at drop-anchored
grid points over 8 s, divided by the average. Sweep 0.30-1.30 s in 0.5 ms steps. Print top candidates + ratios."""
import json, numpy as np, librosa
H=json.load(open("hits5.json")); out={}
for k,h in H.items():
    y,sr=librosa.load(h["file"],sr=22050); hop=32
    o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,aggregate=np.median); ol=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,fmax=200,n_mels=32)
    o=o/o.max()+ol/ol.max(); t=librosa.frames_to_time(np.arange(len(o)),sr=sr,hop_length=hop)
    drop=h["drop"]; base=o[(t>drop)&(t<drop+8)].mean(); w=int(0.017*sr/hop)
    def score(p):
        g=drop+p*np.arange(1,int(8/p)+1); idx=np.clip((g*sr/hop).round().astype(int),w,len(o)-w-1)
        return np.mean([o[i-w:i+w+1].max() for i in idx])/base
    ps=np.arange(0.30,1.30,0.0005); sc=np.array([score(p) for p in ps])
    top=[]
    for i in np.argsort(sc)[::-1]:
        if all(abs(ps[i]-q)>0.02 for q,_ in top): top.append((round(float(ps[i]),4),round(float(sc[i]),2)))
        if len(top)==6: break
    out[k]=top; print(f"{k:16s} {[(p,s,round(60/p)) for p,s in top]}")
json.dump(out,open("beat8.json","w"),indent=1)
