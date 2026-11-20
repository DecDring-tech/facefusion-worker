"""Register new sounds: exact drop (transient start), beat period, offset so the bait is ~3.1 s, slot pattern, fade-in if the intro is loud."""
import json, numpy as np, librosa, sys
sys.path.insert(0,"scripts"); from onsets import peaks
PICK0={"sybau":3.27,"temporary":6.95,"ptdg":3.17,"vaivai":16.82,"lilbabyman":38.01,"drknites":9.77,"itizwotitiz":14.14,
      "partyfunk":5.88,"motorsport":9.62,"zetsu":4.26,"g80kam":3.74,"nm25":5.85}
PICK=json.load(open("snd3/pick.json"))
H=json.load(open("hits5.json")); B=json.load(open("beat7.json")); P=json.load(open("plan8.json"))
for k,(f,coarse) in PICK.items():
    key="M_"+k
    y,sr=librosa.load(f,sr=44100); hop=64
    r=librosa.feature.rms(y=y,frame_length=256,hop_length=hop)[0]; t=librosa.frames_to_time(np.arange(len(r)),sr=sr,hop_length=hop)
    m=(t>coarse-0.35)&(t<coarse+0.35); rr=r[m]; tt=t[m]; drop=float(tt[np.argmax(rr>=0.6*rr.max())])
    pk,st,o,to=peaks(f); base=o[(to>drop)&(to<drop+7)].mean()+1e-9; w=int(0.017*22050/64)
    best=(0,0)
    for p in np.arange(0.33,1.3,0.0005):
        g=drop+p*np.arange(1,int(7/p)+1); idx=np.clip((g*22050/64).round().astype(int),w,len(o)-w-1)
        s=np.mean([o[i-w:i+w+1].max() for i in idx])/base
        if s>best[0]: best=(s,p)
    per=float(best[1]); mult=next(m for m in (1,2,4,8) if per*m>=0.9)
    slot=per*mult; dur=len(y)/sr
    n=max(4,min(7,int(round(5.3/slot)))); n=min(n,int((dur-drop-0.05)//slot))
    off=max(0.0,drop-3.08); pad=round(max(0.0,3.08-drop),2)
    pre=r[(t>off)&(t<drop-0.15)].mean() if drop-off>0.3 else 0; post=r[(t>drop)&(t<drop+2)].mean()
    fade=0.8 if pre>0.35*post else 0
    if pre>0.5*post: print(f"SKIP loud intro {k} {pre/post:.2f}"); continue
    if n<3: print("SKIP short",k); continue
    H[key]={"file":f,"offset":round(off,3),"drop":round(drop,3),"end":round(drop+n*slot,3),"hits":[]}
    B[key]={"drop":round(drop,3)}
    P[key]={"offset":round(off,3),"period":round(per,4),"pattern":[mult]*n,"pad":pad,**({"fade":fade} if fade else {})}
    print(f"{key:14s} drop={drop:.3f} offset={off:.2f} pad={pad} beat={per:.3f}s x{mult} -> {n} shots of {slot:.2f}s  part2={n*slot:.2f}s  fade={fade}  intro/drop rms={pre/post:.2f}")
json.dump(H,open("hits5.json","w"),indent=1); json.dump(B,open("beat7.json","w"),indent=1); json.dump(P,open("plan8.json","w"),indent=1)
