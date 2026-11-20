"""Post a batch: video in slot N goes to account slot N of that series, one video per account, caption + hashtags filled,
the video's own (baked-in) audio used as the sound. Goes through Upload-Post's API (their TikTok app is audited, so posts
are public).
usage (from autopilot/):
  python3 post.py check                         # list Upload-Post profiles and which TikTok accounts are connected
  python3 post.py <batch_dir> <tjr|marko>       # DRY RUN: shows exactly what would go where, posts nothing
  python3 post.py <batch_dir> <tjr|marko> --live [--stagger MIN] [--private]
  python3 post.py status                        # refresh pending uploads in the ledger (post ids / urls)
The API key is never stored here: the session's network proxy adds the Authorization header for api.upload-post.com
(set UPLOAD_POST_API_KEY only when running somewhere without that proxy)."""
import datetime, json, os, subprocess, sys, time, uuid
ROOT = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(ROOT, "data"); os.makedirs(D, exist_ok=True)
LEDGER = os.path.join(D, "posted.jsonl"); API = "https://api.upload-post.com"
KEY = os.environ.get("UPLOAD_POST_API_KEY", "placeholder-replaced-by-proxy")

def curl(args):
    r = subprocess.run(["curl", "-sS", "--max-time", "600", "-H", f"Authorization: Apikey {KEY}"] + args, capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"success": False, "raw": (r.stdout or r.stderr)[-500:]}

def check():
    d = curl([f"{API}/api/uploadposts/users"])
    if not d.get("profiles"): print(json.dumps(d, indent=1)[:1500]); return
    print(f"plan {d.get('plan')}  profiles {len(d['profiles'])}/{d.get('limit')}")
    for p in d["profiles"]:
        tt = (p.get("social_accounts") or {}).get("tiktok") or {}
        flag = "" if tt else "  (no TikTok connected)"
        if tt.get("reauth_required"): flag = "  (RECONNECT NEEDED)"
        print(f"  {p['username']:12s} -> @{tt.get('handle','') if tt else ''}{flag}")

def log(row):
    with open(LEDGER, "a") as fh: fh.write(json.dumps(row, ensure_ascii=False) + "\n")

def post(bdir, series, live, stagger, private):
    M = json.load(open(os.path.join(bdir, "manifest.json"))); A = json.load(open(os.path.join(ROOT, "accounts.json")))[series]
    done = set()
    if os.path.exists(LEDGER):
        done = {(r["batch"], r["video"]) for r in map(json.loads, open(LEDGER)) if r.get("status") in ("posted", "submitted")}
    acc = {a["slot"]: a for a in A}; t0 = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2)
    for it in M["items"]:
        a = acc.get(it["slot"])
        if not a or not a.get("uploadpost_user"): print(f"  slot {it['slot']}: no account, skipped"); continue
        if (M["batch"], it["video"]) in done: print(f"  slot {it['slot']}: {it['video']} already posted, skipped"); continue
        when = t0 + datetime.timedelta(minutes=stagger * (it["slot"] - 1)) if stagger else None
        print(f"  slot {it['slot']:2d} {it['video']:22s} -> {a['uploadpost_user']} (@{a.get('handle') or '?'})"
              f"{' at ' + when.strftime('%H:%M UTC') if when else ' now'}\n           \"{it['caption']}\"")
        if not live: continue
        rid = f"{M['batch']}-{it['slot']}-{uuid.uuid4().hex[:6]}"
        args = [f"{API}/api/upload", "-H", f"Idempotency-Key: {rid}", "-F", f"video=@{os.path.join(bdir, it['video'])}",
                "-F", f"user={a['uploadpost_user']}", "-F", "platform[]=tiktok", "--form-string", f"tiktok_title={it['caption']}",
                "-F", f"privacy_level={'SELF_ONLY' if private else 'PUBLIC_TO_EVERYONE'}", "-F", "post_mode=DIRECT_POST",
                "-F", "async_upload=true", "-F", f"request_id={rid}", "--form-string", f"external_id={M['batch']}/{it['video']}"]
        if when: args += ["-F", f"scheduled_date={when.strftime('%Y-%m-%dT%H:%M:%S')}", "-F", "timezone=UTC"]
        r = curl(args); ok = bool(r.get("success"))
        log({"ts": int(time.time()), "series": series, "batch": M["batch"], "video": it["video"], "slot": it["slot"],
             "uploadpost_user": a["uploadpost_user"], "handle": a.get("handle", ""), "caption": it["caption"],
             "request_id": r.get("request_id", rid), "job_id": r.get("job_id"), "status": "submitted" if ok else "failed",
             "response": r, "features": {**it["features"], "video": it["video"]}})
        print(f"           {'submitted' if ok else 'FAILED'} {'' if ok else json.dumps(r)[:300]}")
        time.sleep(2)
    if not live: print("\nDry run only. Add --live to post.")

def status():
    rows = [json.loads(l) for l in open(LEDGER)] if os.path.exists(LEDGER) else []
    for r in rows:
        if r["status"] != "submitted": continue
        q = f"job_id={r['job_id']}" if r.get("job_id") else f"request_id={r['request_id']}"
        s = curl([f"{API}/api/uploadposts/status?{q}"]); r["last_status"] = s
        res = [x for x in s.get("results", []) if x.get("platform") == "tiktok"]
        if s.get("status") == "completed" and res and res[0].get("success"):
            r["status"] = "posted"; r["post_url"] = res[0].get("post_url"); r["post_id"] = res[0].get("platform_post_id") or res[0].get("post_id")
        elif s.get("status") == "failed": r["status"] = "failed"
        print(f"  {r['batch']}/{r['video']} @{r['handle']}: {r['status']} {r.get('post_url') or ''}")
    with open(LEDGER, "w") as fh:
        for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "check": check()
    elif a[0] == "status": status()
    else:
        st = float(a[a.index("--stagger") + 1]) if "--stagger" in a else 0
        post(a[0], a[1], "--live" in a, st, "--private" in a)
