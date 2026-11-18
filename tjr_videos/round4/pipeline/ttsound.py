import sys, json, subprocess, urllib.parse, time
pid, out = sys.argv[1], sys.argv[2]
url = f"https://www.tiktok.com/@x/video/{pid}"
for a in range(3):
    r = subprocess.run(["curl","-s","--max-time","60",f"https://www.tikwm.com/api/?url={urllib.parse.quote(url,safe='')}"],capture_output=True,text=True).stdout
    try:
        d=json.loads(r)
        if d.get("code")==0: break
    except Exception: d={"msg":r[:60]}
    time.sleep(3)
else: print("API FAIL",d.get("msg")); sys.exit(1)
m=d["data"]["music_info"]
subprocess.run(["curl","-s","-L","--max-time","120","-o",out,m["play"]])
json.dump({"post":pid,"post_title":d["data"]["title"],"music_id":m.get("id"),"title":m.get("title"),"author":m.get("author"),"original":m.get("original"),"duration":m.get("duration")},open(out+".json","w"),indent=1,ensure_ascii=False)
print(pid, "->", m.get("title"), "—", m.get("author"), f"({m.get('duration')}s)")
