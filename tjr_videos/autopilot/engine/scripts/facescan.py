"""For one clip: find the best >=3.1 s stretch (inside one take) where a frontal face fills the frame."""
import subprocess,re,sys,json,os,numpy as np,cv2
f=sys.argv[1]; key=os.path.basename(f)[:-4]; out=f"facescan/{key}.json"
if os.path.exists(out): sys.exit()
def run(a): return subprocess.run(a,capture_output=True)
pr=run(["ffprobe","-v","error","-select_streams","v","-show_entries","stream=width,height","-of","csv=p=0",f]).stdout.decode().strip()
if not pr: json.dump({},open(out,"w")); sys.exit()
w,h=[int(x) for x in pr.split(",")[:2]]
if w>h: json.dump({},open(out,"w")); sys.exit()
D=float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]).stdout.decode() or 0); T=min(D,45)
r=run(["ffmpeg","-i",f,"-t",str(T),"-vf","scale=180:-2,select='gt(scene,0.25)',showinfo","-an","-f","null","-"]).stderr.decode()
cuts=[0.0]+[float(x) for x in re.findall(r"pts_time:([0-9.]+)",r)]+[T]
W,H=270,480; FPS=4
raw=run(["ffmpeg","-v","error","-i",f,"-t",str(T),"-vf",f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}","-f","rawvideo","-pix_fmt","bgr24","-"]).stdout
n=len(raw)//(W*H*3); fr=np.frombuffer(raw[:n*W*H*3],np.uint8).reshape(n,H,W,3)
det=cv2.FaceDetectorYN.create("models/yunet.onnx","",(W,H),0.6); frac=np.zeros(n)
for i in range(n):
    _,d=det.detect(fr[i])
    if d is None: continue
    x=max(d,key=lambda q:q[2]); ed=abs(x[6]-x[4])+1e-6; off=abs(x[8]-(x[4]+x[6])/2)/ed
    frac[i]=float(x[2])/W*(1.0 if off<0.3 else 0.5)
best=None; need=int(3.15*FPS)
for a,b in zip(cuts[:-1],cuts[1:]):
    if b-a<3.2: continue
    i0=int(np.ceil((a+0.12)*FPS)); i1=int(np.floor((b-0.1)*FPS))
    for s in range(i0,i1-need+1):
        win=frac[s:s+need]; sc=float(np.sort(win)[len(win)//4])        # 25th percentile: face must be there most of the time
        first=float(frac[s:s+3].max())
        tot=sc+0.3*first
        if best is None or tot>best[0]: best=(tot,sc,first,s/FPS,b-s/FPS)
if best is None: json.dump({},open(out,"w")); sys.exit()
tot,sc,first,st,avail=best
json.dump({"file":f,"score":round(tot,3),"face":round(sc,3),"first":round(first,3),"start":round(st,2),"avail":round(avail,2),"wh":f"{w}x{h}"},open(out,"w"))
if sc>=0.25:
    for k,t in enumerate((st,st+1.5,st+3.0)):
        run(["ffmpeg","-v","error","-y","-ss",f"{t:.2f}","-i",f,"-frames:v","1","-vf","scale=110:196:force_original_aspect_ratio=increase,crop=110:196",f"facescan/{key}_{k}.png"])
