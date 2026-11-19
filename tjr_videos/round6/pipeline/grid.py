"""Beat grid per sound: tempo from onset autocorrelation after the drop, period refined, phase locked to the drop.
Also prints how the user's reference cuts sit on that grid."""
import json, re, subprocess, numpy as np, librosa
H=json.load(open("hits5.json")); S=json.load(open("sounds2.json"))
REF={"S1_ballerszn":["41c7e566","37572da9","fa30f079"],"S2_bannu":["bcd9585a"],"S3_salman":["87eb16cc"],"S4_404oskar":["05aa0696"],"S5_gsgroup":["62169fa7"],"S6_luxuryxsh":["4d94e081"],"S7_useheadset":["28d452a3"],"S8_calebgordenn":["9e8beab4"]}
OFF={"S1_ballerszn":0.0,"S2_bannu":5.663,"S3_salman":0.0,"S4_404oskar":0.0,"S5_gsgroup":0.0,"S6_luxuryxsh":0.0,"S7_useheadset":2.804,"S8_calebgordenn":0.0}
OVR={"S1_ballerszn":(0.503,4.03)}   # (period, anchor) where the autocorrelation picks a half/double tempo
out={}
for k,h in H.items():
    y,sr=librosa.load(h["file"],sr=22050); hop=128
    o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,aggregate=np.median); t=librosa.frames_to_time(np.arange(len(o)),sr=sr,hop_length=hop)
    drop=h["drop"]; seg=o[(t>=drop)&(t<drop+9)]
    # autocorrelation -> candidate periods 0.30..1.0 s
    ac=np.correlate(seg,seg,"full")[len(seg)-1:]; lags=np.arange(len(ac))*hop/sr
    m=(lags>=0.30)&(lags<=1.0); P=lags[m][np.argmax(ac[m])]
    # refine: period that maximises onset energy at grid points from the drop
    best=(0,P)
    for p in np.linspace(P*0.97,P*1.03,121):
        g=drop+p*np.arange(0,int(9/p)); idx=np.clip(((g)*sr/hop).round().astype(int),0,len(o)-1); sc=o[idx].mean()
        if sc>best[0]: best=(sc,p)
    p=best[1]
    if k in OVR:
        p,anchor=OVR[k]; k0=int(np.ceil((drop+0.3-anchor)/p)); grid=[round(anchor+p*i,3) for i in range(k0,k0+int(9/p)+1)]; grid=[x for x in grid if x < t[-1]-0.05]
    else:
        grid=[round(drop+p*i,3) for i in range(1,int(9/p)+1)]
    grid=[x for x in grid if x < t[-1]-0.05]
    idx=np.clip((np.array(grid)*sr/hop).round().astype(int),0,len(o)-1); rand=o[(t>=drop)&(t<drop+9)].mean(); score=o[idx].mean()/rand
    # onset strength at each grid point (max within +-25 ms), normalised
    ons=[]
    for gp in grid:
        m=(t>=gp-0.025)&(t<=gp+0.025); ons.append(round(float(o[m].max()/rand),2))
    out[k]={"file":h["file"],"drop":drop,"period":round(float(p),4),"bpm":round(60/p,1),"grid_score":round(float(score),2),"grid":grid,"onset":ons}
    print(f"{k:16s} drop={drop:.3f} period={p:.3f}s ({60/p:.0f} bpm) onset-at-grid/avg={score:.1f}")
    for ref in REF.get(k,[]):
        err=subprocess.run(["ffmpeg","-i",f"src/{ref}.mp4","-vf","select='gt(scene,0.3)',showinfo","-an","-f","null","-"],capture_output=True,text=True).stderr
        cuts=[float(x)+OFF[k] for x in re.findall(r"pts_time:([0-9.]+)",err)]; cuts=[c for c in cuts if c>drop-0.1]
        beats=[(c-drop)/p for c in cuts]
        print(f"    ref {ref}: cuts in beats after drop = {[round(b,2) for b in beats]}")
json.dump(out,open("grid.json","w"),indent=1)
