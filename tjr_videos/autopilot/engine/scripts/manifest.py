"""Turn a rendered batch into a posting manifest.
usage (from engine/): python3 scripts/manifest.py <series tjr|marko> <specs.json> <render_dir> <batch_dir>
Copies the videos into ../batches/<batch_dir>/ and writes manifest.json: one entry per video, in slot order, with the
full post caption (caption + hashtags) and the features analytics groups by."""
import json, os, shutil, sys
series, specs_f, rdir, bname = sys.argv[1:5]
specs = json.load(open(specs_f)); meta = json.load(open("sounds_meta.json"))
bdir = os.path.join("..", "batches", bname); os.makedirs(bdir, exist_ok=True)
items = []
for i, sp in enumerate(specs, 1):
    src = os.path.join(rdir, sp["name"] + ".mp4"); assert os.path.exists(src), f"missing render {src}"
    shutil.copy2(src, os.path.join(bdir, sp["name"] + ".mp4"))
    cuts = json.load(open(os.path.join(rdir, sp["name"] + ".cuts.json")))
    tags = " ".join(sp.get("hashtags", []))
    items.append({
        "slot": i, "video": sp["name"] + ".mp4",
        "caption": (sp.get("post_caption", "").strip() + " " + tags).strip(),
        "features": {
            "series": series, "batch": bname, "sound": sp["sound"], "sound_name": meta.get(sp["sound"], sp["sound"]),
            "bait": sp["bait"], "bait_person": sp.get("bait_person", ""), "cap1": sp["cap1"].replace("\n", " "),
            "cap2": sp["cap2"].replace("\n", " "), "rage_bait": bool(sp.get("rage_bait")),
            "switch_s": round(cuts["drop_frame"] / 30, 2), "length_s": round(cuts["end_frame"] / 30, 2),
            "shots": len(cuts["cut_frames"]) + 1, "sources": [s[0] for s in sp["sources"]]}})
json.dump({"series": series, "batch": bname, "items": items}, open(os.path.join(bdir, "manifest.json"), "w"), indent=1, ensure_ascii=False)
print(f"{bdir}/manifest.json: {len(items)} videos")
for it in items: print(f"  {it['slot']:2d} {it['video']:22s} {it['caption']}")
