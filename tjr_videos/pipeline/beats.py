import json, numpy as np, librosa
S = {"S1_ballerszn":("37572da9",2.95),"S2_bannu":("bcd9585a",3.40),"S3_salman":("87eb16cc",3.71),"S4_404oskar":("05aa0696",6.45),
     "S5_gsgroup":("62169fa7",3.43),"S6_luxuryxsh":("4d94e081",4.91),"S7_useheadset":("28d452a3",3.55),"S8_calebgordenn":("9e8beab4",2.73)}
out={}
for k,(n,drop) in S.items():
    y,sr=librosa.load(f"audio/{n}.wav",sr=16000); dur=len(y)/sr
    tempo,bf=librosa.beat.beat_track(y=y,sr=sr,units='time')
    tp=float(np.atleast_1d(tempo)[0])
    # onsets after drop (strong transients) for cut candidates
    on=librosa.onset.onset_detect(y=y,sr=sr,units='time',backtrack=False)
    out[k]={"file":n,"dur":round(dur,3),"drop":drop,"tempo":round(tp,1),"beats":[round(float(b),3) for b in bf],"onsets":[round(float(o),3) for o in on]}
    print(k,n,f"dur={dur:.2f} drop={drop} tempo={tp:.0f}","beats after drop:",[round(float(b),2) for b in bf if b>=drop][:12])
json.dump(out,open("sounds.json","w"),indent=1)
