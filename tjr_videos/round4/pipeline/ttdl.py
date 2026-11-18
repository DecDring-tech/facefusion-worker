"""Download a TikTok post (no watermark) via the tikwm API. usage: ttdl.py <video_url_or_id> <out.mp4>"""
import sys, json, subprocess, urllib.parse, time
src, out = sys.argv[1], sys.argv[2]
url = src if src.startswith("http") else f"https://www.tiktok.com/@x/video/{src}"
for attempt in range(3):
    r = subprocess.run(["curl", "-s", "--max-time", "60", f"https://www.tikwm.com/api/?url={urllib.parse.quote(url, safe='')}&hd=1"], capture_output=True, text=True).stdout
    try:
        d = json.loads(r)
        if d.get("code") == 0: break
    except Exception: d = {"msg": r[:80]}
    time.sleep(3)
else:
    print("API FAIL", d.get("msg")); sys.exit(1)
v = d["data"]; play = v.get("hdplay") or v.get("play")
rc = subprocess.run(["curl", "-s", "-L", "--max-time", "180", "-o", out, play]).returncode
m = v.get("music_info", {})
meta = {"id": v["id"], "title": v.get("title"), "duration": v.get("duration"), "plays": v.get("play_count"),
        "music": f'{m.get("title")} — {m.get("author")}', "music_id": m.get("id"), "music_url": m.get("play")}
json.dump(meta, open(out + ".json", "w"), indent=1)
print(json.dumps({k: meta[k] for k in ["id", "title", "duration", "plays", "music"]}))
