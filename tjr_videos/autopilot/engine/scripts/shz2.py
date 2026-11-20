import asyncio, json, subprocess
from shazamio import Shazam
rows=json.load(open("snd3/sim.json"))
ok=[r for r in rows if r["ratio"]>=3 and r["sharp"]>=2 and r["beat"]>=3 and r["dist"]<8]
ok.sort(key=lambda r:r["dist"])
async def main():
    sh=Shazam(); out=[]
    for r in ok:
        seg="tmp/shz.mp3"; subprocess.run(["ffmpeg","-v","error","-y","-ss",str(max(0,r["drop"]-1)),"-t","9","-i",r["f"],seg])
        try:
            res=await sh.recognize(seg); t=res.get("track"); song=(t["title"]+" — "+t["subtitle"]) if t else "no match"
        except Exception as e: song="ERR"
        r["shazam"]=song; out.append(r); print(f'{r["dist"]:5.2f} {r["post"]} {r["name"][:40]:40s} -> {song}')
    json.dump(out,open("snd3/shortlist.json","w"),indent=1,default=float)
asyncio.run(main())
