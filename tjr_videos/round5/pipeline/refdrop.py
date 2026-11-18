"""Derive the drop from the user's own posts: align each reference clip's audio to the sound (xcorr), take the clip's
visual switch frame, map it into sound time."""
import json, numpy as np, librosa, subprocess, re
U="/root/.claude/uploads/508c9b53-ff4c-5ea1-99ff-9ea13eb52fbb"
REF={"S1_ballerszn":["41c7e566","37572da9","fa30f079"],"S2_bannu":["bcd9585a","e1a6da07"],"S3_salman":["87eb16cc"],"S4_404oskar":["05aa0696"],
     "S5_gsgroup":["62169fa7"],"S6_luxuryxsh":["4d94e081"],"S7_useheadset":["28d452a3"],"S8_calebgordenn":["9e8beab4"]}
H=json.load(open("hits.json")); out={}
def switch_time(ref):
    # first hard cut after 2.5s (part1->part2); scene threshold 0.3, 30fps
    err=subprocess.run(["ffmpeg","-i",f"src/{ref}.mp4","-vf","select='gt(scene,0.3)',showinfo","-an","-f","null","-"],capture_output=True,text=True).stderr
    cuts=[float(x) for x in re.findall(r"pts_time:([0-9.]+)",err)]
    return [c for c in cuts if c>2.5][0]
for snd,refs in REF.items():
    s,sr=librosa.load(H[snd]["file"],sr=16000)
    rows=[]
    for ref in refs:
        y,_=librosa.load(f"audio/{ref}.wav",sr=16000)
        # xcorr of 8 s of the ref against the sound -> offset of ref t=0 in sound time
        seg=y[:min(len(y),8*sr)]; seg=(seg-seg.mean())/(seg.std()+1e-9); ss=(s-s.mean())/(s.std()+1e-9)
        c=np.correlate(ss,seg,mode="valid"); k=int(np.argmax(c)); off=k/sr; conf=c[k]/len(seg)
        sw=switch_time(ref); drop_sound=sw+off
        rows.append((ref,round(off,3),round(conf,2),round(sw,3),round(drop_sound,3)))
    print(snd, "my drop:",H[snd]["drop"]); [print("   ref",r) for r in rows]
    out[snd]={"refs":rows}
json.dump(out,open("refdrop.json","w"),indent=1)
