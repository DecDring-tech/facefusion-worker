import glob, os, json, numpy as np, librosa
H=json.load(open("hits5.json"))
REF={k:(H[k]["file"],H[k]["drop"]) for k in ["S1_ballerszn","S2_bannu","S3_salman","S4_404oskar","S5_gsgroup","S6_luxuryxsh","S7_useheadset","S8_calebgordenn","S9_northpole"]}
SR=22050
def find_drop(y):
    hop=256; r=librosa.feature.rms(y=y,frame_length=1024,hop_length=hop)[0]; t=librosa.frames_to_time(np.arange(len(r)),sr=SR,hop_length=hop)
    dur=len(y)/SR; best=None
    for i in range(len(r)):
        tt=t[i]
        if tt<2.0 or tt>dur-5.6: continue
        pre=r[(t>=tt-2.5)&(t<tt-0.1)].mean(); post=r[(t>=tt)&(t<tt+2.0)].mean()
        sh=r[(t>=tt)&(t<tt+0.3)].mean()/(r[(t>=tt-0.3)&(t<tt)].mean()+1e-6)
        sc=(post/(pre+1e-6))*min(sh,4)
        if best is None or sc>best[0]: best=(sc,tt,post/(pre+1e-6),sh)
    return best
def feats(y,drop):
    seg=y[int(drop*SR):int((drop+6)*SR)]
    mf=librosa.feature.mfcc(y=seg,sr=SR,n_mfcc=13); S=np.abs(librosa.stft(seg,n_fft=2048))**2; fr=librosa.fft_frequencies(sr=SR,n_fft=2048)
    low=S[fr<120].sum()/S.sum(); mid=S[(fr>=120)&(fr<2000)].sum()/S.sum()
    cen=librosa.feature.spectral_centroid(y=seg,sr=SR).mean()/1000
    h,p=librosa.effects.hpss(seg); perc=np.sum(p**2)/(np.sum(seg**2)+1e-9)
    o=librosa.onset.onset_strength(y=seg,sr=SR); tempo=float(np.atleast_1d(librosa.beat.beat_track(onset_envelope=o,sr=SR)[0])[0])
    tempo=tempo if tempo<110 else tempo/2
    return np.concatenate([mf.mean(1),mf.std(1)*0.5,[low*10,mid*5,cen,perc*5,tempo/20]])
def beatscore(y,drop):
    o=librosa.onset.onset_strength(y=y,sr=SR,hop_length=128); to=librosa.frames_to_time(np.arange(len(o)),sr=SR,hop_length=128)
    base=o[(to>drop)&(to<drop+6)].mean()+1e-9; w=3; best=(0,0)
    for p in np.arange(0.35,1.3,0.004):
        g=drop+p*np.arange(1,int(6/p)+1); idx=np.clip((g*SR/128).round().astype(int),w,len(o)-w-1)
        s=np.mean([o[i-w:i+w+1].max() for i in idx])/base
        if s>best[0]: best=(s,p)
    return best
refF={}
for k,(f,d) in REF.items():
    y,_=librosa.load(f,sr=SR); refF[k]=feats(y,d)
refids=set(json.load(open(f+".json")).get("music_id") for f in glob.glob("sounds_dl/*.mp3") if os.path.exists(f+".json"))
rows=[]
for f in sorted(glob.glob("snd3/*.mp3")):
    m=json.load(open(f+".json"))
    if m.get("music_id") in refids: continue
    try: y,_=librosa.load(f,sr=SR)
    except Exception: continue
    if len(y)/SR<9: continue
    b=find_drop(y)
    if not b: continue
    sc,drop,ratio,sharp=b
    F=feats(y,drop); bs=beatscore(y,drop)
    rows.append(dict(f=f,name=f'{m["title"]} — {m["author"]}',post=m["post"],dur=round(len(y)/SR,1),drop=round(drop,2),ratio=round(ratio,1),sharp=round(sharp,1),beat=round(bs[0],1),period=round(bs[1],3),F=F.tolist()))
A=np.array([r["F"] for r in rows]+list(refF.values())); mu=A.mean(0); sd=A.std(0)+1e-9
R={k:(v-mu)/sd for k,v in refF.items()}
for r in rows:
    z=(np.array(r["F"])-mu)/sd; d={k:float(np.linalg.norm(z-v)) for k,v in R.items()}
    k=min(d,key=d.get); r["near"]=k; r["dist"]=round(d[k],2); del r["F"]
# reference self-distances for scale
rd=[min(np.linalg.norm(R[a]-R[b]) for b in R if b!=a) for a in R]
print("ref nearest-neighbour distances:",[round(x,1) for x in rd])
json.dump(rows,open("snd3/sim.json","w"),indent=1,default=float)
ok=[r for r in rows if r["ratio"]>=3 and r["sharp"]>=2 and r["beat"]>=3]
ok.sort(key=lambda r:r["dist"])
print(len(rows),"scored,",len(ok),"pass drop+beat filters")
for r in ok[:30]: print(f'{r["dist"]:5.2f} near={r["near"][3:]:13s} drop@{r["drop"]:5.2f} x{r["ratio"]:<4} sharp{r["sharp"]:<4} beat{r["beat"]:<4} {r["dur"]:5.1f}s {r["name"][:55]} post={r["post"]}')
