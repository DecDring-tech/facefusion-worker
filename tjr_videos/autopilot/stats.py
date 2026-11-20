"""Analytics: snapshot the public stats of every connected account, tie each post back to the batch it came from, and
write data/report.md.
usage (from autopilot/): python3 stats.py            # snapshot + report
                         python3 stats.py --report   # report from stored snapshots only
Public numbers only (views, likes, comments, shares, saves). Watch time / retention / follower gains are only in TikTok
Studio; screenshots of those can be dropped into data/studio/ and read by hand."""
import csv, glob, json, os, subprocess, sys, time
from collections import defaultdict
ROOT = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(ROOT, "data"); os.makedirs(D, exist_ok=True)
SNAP = os.path.join(D, "snapshots.csv"); LEDGER = os.path.join(D, "posted.jsonl")
FIELDS = ["snap_ts", "series", "handle", "video_id", "created_ts", "duration", "views", "likes", "comments", "shares", "saves", "caption"]

def accounts():
    A = json.load(open(os.path.join(ROOT, "accounts.json"))); out = []
    for series in ("tjr", "marko"):
        out += [(series, a["handle"].lstrip("@")) for a in A.get(series, []) if a.get("handle")]
    out += [("watch", h.lstrip("@")) for h in A.get("watch_also", [])]
    return out

def listing(handle, tries=3):
    for k in range(tries):
        r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", "--playlist-end", "60", f"https://www.tiktok.com/@{handle}"],
                           capture_output=True, text=True, timeout=600)
        try: return json.loads(r.stdout).get("entries", [])
        except Exception: time.sleep(5 * (k + 1))
    print(f"  ! could not read @{handle}: {r.stderr.strip()[-200:]}"); return None

def snapshot():
    now = int(time.time()); new = not os.path.exists(SNAP); n = 0
    with open(SNAP, "a", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        if new: w.writeheader()
        for series, h in accounts():
            E = listing(h)
            if E is None: continue
            for e in E:
                w.writerow({"snap_ts": now, "series": series, "handle": h, "video_id": e["id"], "created_ts": e.get("timestamp") or "",
                            "duration": e.get("duration") or "", "views": e.get("view_count") or 0, "likes": e.get("like_count") or 0,
                            "comments": e.get("comment_count") or 0, "shares": e.get("repost_count") or 0, "saves": e.get("save_count") or 0,
                            "caption": (e.get("title") or e.get("description") or "").replace("\n", " ")[:150]})
                n += 1
            print(f"  @{h}: {len(E)} posts")
    print(f"snapshot: {n} rows")

METR = os.path.join(D, "post_metrics.json")

def deep():
    """Watch time / retention per post from Upload-Post (needs posts made through post.py and the API key on the proxy)."""
    sys.path.insert(0, ROOT); from post import curl, API
    M = json.load(open(METR)) if os.path.exists(METR) else {}
    if not os.path.exists(LEDGER): return
    for line in open(LEDGER):
        r = json.loads(line)
        if r.get("status") != "posted" or not r.get("post_id"): continue
        d = curl([f"{API}/api/uploadposts/post-analytics?platform_post_id={r['post_id']}&platform=tiktok&user={r['uploadpost_user']}"])
        pm = d.get("post_metrics") or (d.get("tiktok") or {}).get("post_metrics") or d.get("metrics")
        if pm: M[str(r["post_id"])] = {"ts": int(time.time()), **pm}
        time.sleep(3.5)                                          # 100 requests / 5 min
    json.dump(M, open(METR, "w"), indent=1)

def ledger():
    """posted.jsonl rows -> {(handle, normalised caption): features}; caption match ties a TikTok post to our batch entry"""
    L = {}
    if os.path.exists(LEDGER):
        for line in open(LEDGER):
            r = json.loads(line)
            if r.get("status") in ("posted", "submitted"): L[(r["handle"], norm(r["caption"]))] = r
    return L

def norm(s): return " ".join(s.lower().split())[:80]

def fmt(n): return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.1f}K" if n >= 1e3 else str(int(n))

def report():
    if not os.path.exists(SNAP): print("no snapshots yet"); return
    rows = list(csv.DictReader(open(SNAP)))
    hist = defaultdict(list)                                     # (handle, id) -> [(snap_ts, row)]
    for r in rows: hist[(r["handle"], r["video_id"])].append((int(r["snap_ts"]), r))
    PM = json.load(open(METR)) if os.path.exists(METR) else {}
    L = ledger(); now = max(int(r["snap_ts"]) for r in rows)
    vids = []
    for (h, vid), H in hist.items():
        H.sort(key=lambda x: x[0]); last = H[-1][1]
        created = int(last["created_ts"] or 0); age_h = max(0.1, (H[-1][0] - created) / 3600) if created else None
        v = int(last["views"]); prev = [x for x in H if x[0] <= H[-1][0] - 20 * 3600]
        d24 = v - int(prev[-1][1]["views"]) if prev else None
        lr = L.get((h, norm(last["caption"])))
        pm = PM.get(vid, {})
        vids.append({"series": last["series"], "handle": h, "id": vid, "caption": last["caption"], "views": v, "likes": int(last["likes"]),
                     "comments": int(last["comments"]), "shares": int(last["shares"]), "saves": int(last["saves"]),
                     "age_h": age_h, "views_last_24h": d24, "ours": bool(lr), "features": (lr or {}).get("features", {}),
                     "avg_watch": pm.get("average_time_watched"), "finish": pm.get("full_video_watched_rate"),
                     "kept_at_drop": next((x.get("percentage") for x in pm.get("retention", []) if lr and
                                           int(x.get("second", -1)) == int(round(lr["features"].get("switch_s", 3)))), None)})
    out = [f"# Analytics report\n\nLast snapshot: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(now))}. Views, likes, comments, shares and saves are "
           "public numbers; watch time, finish rate and retention come from Upload-Post for posts made through post.py.\n"]
    for series in ("tjr", "marko", "watch"):
        V = [x for x in vids if x["series"] == series]
        if not V: continue
        out.append(f"\n## {series.upper()} accounts\n\n| Account | Posts tracked | Total views | Best post | Views (24h change) |\n|---|---|---|---|---|")
        by = defaultdict(list)
        for x in V: by[x["handle"]].append(x)
        for h, X in sorted(by.items()):
            b = max(X, key=lambda x: x["views"]); d = sum(x["views_last_24h"] or 0 for x in X)
            out.append(f"| @{h} | {len(X)} | {fmt(sum(x['views'] for x in X))} | {fmt(b['views'])} — {b['caption'][:40]} | +{fmt(d)} |")
        ours = sorted([x for x in V if x["ours"]], key=lambda x: -x["views"])
        if ours:
            out.append(f"\n### Our posts ({len(ours)})\n\n| Views | Avg watch | Finished | Still watching at the switch | Likes | Comments | Shares | Saves | Comments per 1K views | Age | Account | Video | Sound | Opener | Payoff |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for x in ours:
                f = x["features"]; cpk = 1000 * x["comments"] / max(1, x["views"])
                pc = lambda v: f"{100*v:.0f}%" if isinstance(v, (int, float)) else "–"
                aw = f"{x['avg_watch']:.1f}s" if isinstance(x["avg_watch"], (int, float)) else "–"
                out.append(f"| {fmt(x['views'])} | {aw} | {pc(x['finish'])} | {pc(x['kept_at_drop'])} | {fmt(x['likes'])} | {x['comments']} | {x['shares']} | {x['saves']} | {cpk:.1f} | "
                           f"{x['age_h']:.0f}h | @{x['handle']} | {f.get('video','')} | {f.get('sound','')} | {f.get('bait_person','')} | "
                           f"{f.get('cap2','')}{' ⚠️' if f.get('rage_bait') else ''} |")
            # what works: median views per feature value, only once each value has 2+ posts
            out.append("\n### What's working (median views per post, groups with 2+ posts)\n")
            for key in ("sound", "bait_person", "rage_bait", "cap2", "batch"):
                g = defaultdict(list)
                for x in ours: g[str(x["features"].get(key, ""))].append(x)
                g = {k: X for k, X in g.items() if len(X) >= 2}
                if len(g) < 2: continue
                out.append(f"- **{key}**: " + ", ".join(f"{k} {fmt(sorted(y['views'] for y in X)[len(X)//2])} (n={len(X)}, "
                           f"{1000*sum(y['comments'] for y in X)/max(1,sum(y['views'] for y in X)):.1f} comments/1K)"
                           for k, X in sorted(g.items(), key=lambda kv: -sorted(y['views'] for y in kv[1])[len(kv[1])//2])))
    open(os.path.join(D, "report.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out))

if __name__ == "__main__":
    if "--report" not in sys.argv:
        snapshot()
        if "--no-api" not in sys.argv: deep()
    report()
