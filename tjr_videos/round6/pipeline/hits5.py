"""Drop table from the user's own posts (sound time), sound start offsets mirroring their posts, hits after the drop.
Each drop is snapped to the strongest onset within ±70 ms of the target."""
import json, numpy as np, librosa, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
S=json.load(open("sounds2.json"))
#            target drop (sound s), sound start offset (s), part-2 length (s)
T={"S1_ballerszn":(3.00,0.0,5.3),"S2_bannu":(9.063,5.663,5.5),"S3_salman":(3.77,0.0,6.5),"S4_404oskar":(6.533,0.0,6.5),
   "S5_gsgroup":(3.99,0.0,5.4),"S6_luxuryxsh":(4.917,0.0,4.4),"S7_useheadset":(6.37,2.804,5.0),"S8_calebgordenn":(2.76,0.0,5.3),"S9_northpole":(5.033,2.0,5.0)}
out={}; fig,axes=plt.subplots(len(T),1,figsize=(16,2.2*len(T)))
for ax,(k,(tgt,off,tail)) in zip(axes,T.items()):
    y,sr=librosa.load(S[k]["file"],sr=22050); hop=128
    o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,aggregate=np.median); ol=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,fmax=200,n_mels=32)
    o=o/(o.max()+1e-9)+ol/(ol.max()+1e-9); t=librosa.frames_to_time(np.arange(len(o)),sr=sr,hop_length=hop)
    m=(t>tgt-0.07)&(t<tgt+0.07); drop=float(t[m][np.argmax(o[m])]); end=drop+tail
    pk=librosa.util.peak_pick(o,pre_max=20,post_max=20,pre_avg=60,post_avg=60,delta=0.12,wait=int(0.28*sr/hop))
    hits=[(float(t[i]),float(o[i])) for i in pk if drop+0.3<t[i]<end-0.25]
    thr=np.percentile([h[1] for h in hits],35) if hits else 0; strong=[h for h in hits if h[1]>=thr]
    out[k]={"file":S[k]["file"],"offset":off,"drop":round(drop,3),"end":round(end,3),"hits":[round(h[0],3) for h in strong]}
    ax.plot(t,o,lw=0.7); ax.axvline(drop,color="r"); [ax.axvline(h[0],color="g",alpha=0.6) for h in strong]
    ax.set_xlim(max(0,drop-2),end+0.5); ax.set_title(f"{k} drop={drop:.3f} (clip {drop-off:.2f}s) hits={len(strong)}",fontsize=9)
    print(f"{k:16s} drop={drop:.3f} clip@{drop-off:.2f}s hits={[round(h[0],2) for h in strong]}")
plt.tight_layout(); plt.savefig("hits5.png",dpi=70); json.dump(out,open("hits5.json","w"),indent=1)
