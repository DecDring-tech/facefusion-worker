"""Transient grid per sound: strongest drum hits after the drop, frame-accurate. Writes hits.json + a plot per sound."""
import json, numpy as np, librosa, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
S = json.load(open("sounds2.json"))
DROP_GUESS = {"S1_ballerszn":2.95,"S2_bannu":6.11,"S3_salman":3.69,"S4_404oskar":6.41,"S5_gsgroup":4.0,"S6_luxuryxsh":4.89,"S7_useheadset":6.35,"S8_calebgordenn":2.73,"S9_northpole":5.02}
TAIL = {"S1_ballerszn":5.3,"S2_bannu":5.0,"S3_salman":6.0,"S4_404oskar":6.0,"S5_gsgroup":5.0,"S6_luxuryxsh":4.4,"S7_useheadset":5.0,"S8_calebgordenn":5.3,"S9_northpole":5.0}
out = {}
fig, axes = plt.subplots(len(S), 1, figsize=(16, 2.2*len(S)))
for ax, (k, s) in zip(axes, S.items()):
    y, sr = librosa.load(s["file"], sr=22050); hop = 128
    # low band emphasises kicks; full band catches snares/claps
    o_full = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, aggregate=np.median)
    o_low = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, fmax=200, n_mels=32)
    o = o_full/ (o_full.max()+1e-9) + o_low/(o_low.max()+1e-9)
    t = librosa.frames_to_time(np.arange(len(o)), sr=sr, hop_length=hop)
    # exact drop = strongest onset within ±0.25 s of the coarse estimate
    g = DROP_GUESS[k]; m = (t > g-0.25) & (t < g+0.25); drop = float(t[m][np.argmax(o[m])])
    end = drop + TAIL[k]
    # candidate hits after the drop: local maxima, min spacing 0.28 s, keep the strong ones
    pk = librosa.util.peak_pick(o, pre_max=20, post_max=20, pre_avg=60, post_avg=60, delta=0.12, wait=int(0.28*sr/hop))
    hits = [(float(t[i]), float(o[i])) for i in pk if drop+0.3 < t[i] < end-0.25]
    thr = np.percentile([h[1] for h in hits], 35) if hits else 0
    strong = [h for h in hits if h[1] >= thr]
    out[k] = {"file": s["file"], "drop": round(drop,3), "end": round(end,3), "hits": [round(h[0],3) for h in strong], "strength": [round(h[1],2) for h in strong]}
    ax.plot(t, o, lw=0.7); ax.axvline(drop, color="r"); [ax.axvline(h[0], color="g", alpha=0.6) for h in strong]
    ax.set_xlim(max(0, drop-1.5), end+0.5); ax.set_title(f"{k}  drop={drop:.3f}  hits={len(strong)}", fontsize=9)
    print(f"{k:16s} drop={drop:.3f} end={end:.2f} hits={[round(h[0],2) for h in strong]}")
plt.tight_layout(); plt.savefig("hits.png", dpi=70)
json.dump(out, open("hits.json","w"), indent=1)
