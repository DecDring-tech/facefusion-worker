"""Perceptual-hash every frame of the user's 11 reference clips; flag any candidate shot that matches."""
import cv2, glob, os, sys, subprocess, numpy as np
def frames(path, fps=6, size=(32, 32)):
    p = subprocess.Popen(["ffmpeg","-v","error","-i",path,"-vf",f"fps={fps},scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,scale=32:32","-f","rawvideo","-pix_fmt","gray","-"],stdout=subprocess.PIPE)
    out=[]
    while True:
        b=p.stdout.read(32*32)
        if len(b)<1024: break
        out.append(np.frombuffer(b,np.uint8).reshape(32,32))
    return out
def dhash(g):
    g=cv2.resize(g,(17,16),interpolation=cv2.INTER_AREA).astype(int)
    return np.packbits((g[:,1:]>g[:,:-1]).ravel())
def ham(a,b): return int(np.unpackbits(a^b).sum())
ref=[]
for f in sorted(glob.glob("/root/.claude/uploads/508c9b53-ff4c-5ea1-99ff-9ea13eb52fbb/*.mp4")):
    for g in frames(f, fps=10):
        # also hash a centre crop so letterbox/zoom variants still match
        ref.append((os.path.basename(f)[:8], dhash(g), dhash(g[6:26,4:28])))
print(len(ref),"reference hashes")
for cand in sorted(glob.glob(sys.argv[1]+"/*.mp4")):
    best=(999,None); n=0
    for g in frames(cand, fps=6):
        h=dhash(g); hc=dhash(g[6:26,4:28])
        for name,r,rc in ref:
            d=min(ham(h,r),ham(hc,rc),ham(h,rc),ham(hc,r))
            if d<best[0]: best=(d,name)
        n+=1
    flag="MATCH" if best[0]<=14 else ("close" if best[0]<=22 else "ok")
    print(f"{os.path.basename(cand):26s} min_dist={best[0]:3d} vs {best[1]}  -> {flag}")
