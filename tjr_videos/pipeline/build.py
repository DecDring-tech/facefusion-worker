"""Assemble TJR-style videos: [bait clip + 'Where's your X TJR? 😂'] -> drop -> [Regera B-roll cut on beats + 'lil bro' line]."""
import json, os, subprocess, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from caption import render
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")              # cleaned Regera/bait footage + the 8 sounds
SND = json.load(open(os.path.join(HERE, "sounds.json")))
OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True)

# clean/ clips, (file, start, end)
BAIT = {
 "watch":   [("87eb16cc", 0.00, 3.77)],
 "cat":     [("05aa0696", 0.00, 6.53)],
 "rolls":   [("bcd9585a", 0.00, 3.40)],
 "bentley": [("9e8beab4", 0.00, 2.77)],
 "gls":     [("62169fa7", 0.00, 3.43)],
 "svj":     [("28d452a3", 0.00, 3.77)],
 "r8":      [("41c7e566", 0.00, 3.00)],
 "pj":      [("fa30f079", 0.00, 3.03)],
 "pool":    [("e1a6da07", 0.00, 3.40)],
 "svjpov":  [("4d94e081", 0.00, 4.90)],
}
R = {  # Regera B-roll shots
 "pose_arms_a": ("41c7e566", 3.00, 3.97), "pose_arms_b": ("fa30f079", 3.03, 3.90), "pose_arms_c": ("37572da9", 3.13, 4.37),
 "pose_chain_a": ("87eb16cc", 3.77, 4.53), "pose_chain_b": ("05aa0696", 6.53, 7.97), "pose_chain_c": ("bcd9585a", 3.40, 4.50), "pose_chain_d": ("e1a6da07", 3.40, 5.97),
 "crowd_front_a": ("87eb16cc", 4.53, 6.43), "crowd_front_b": ("41c7e566", 3.97, 5.03), "crowd_front_c": ("28d452a3", 4.53, 5.27), "crowd_front_d": ("4d94e081", 5.63, 6.53),
 "crowd_window_a": ("05aa0696", 7.97, 11.93), "crowd_window_b": ("bcd9585a", 5.27, 6.03), "crowd_window_c": ("87eb16cc", 6.43, 7.07),
 "crowd_side": ("9e8beab4", 2.77, 5.37),
 "tail_night_a": ("28d452a3", 5.27, 6.70), "tail_night_b": ("4d94e081", 4.90, 5.63), "tail_night_c": ("9e8beab4", 7.07, 8.03),
 "gas_rear_a": ("87eb16cc", 7.07, 7.87), "gas_rear_b": ("62169fa7", 6.37, 7.00), "gas_rear_c": ("4d94e081", 6.53, 7.07), "gas_rear_d": ("fa30f079", 5.93, 6.30),
 "gas_front_a": ("05aa0696", 12.93, 14.10), "gas_front_b": ("62169fa7", 5.83, 6.37), "gas_front_c": ("4d94e081", 7.07, 7.57), "gas_front_d": ("bcd9585a", 6.03, 6.43),
 "gas_side": ("62169fa7", 7.00, 7.63), "interior_a": ("62169fa7", 7.63, 8.67), "interior_b": ("41c7e566", 6.17, 7.37),
 "garage": ("28d452a3", 3.77, 4.53),
 "carpet_a": ("28d452a3", 7.40, 8.10), "carpet_b": ("4d94e081", 8.47, 9.13), "carpet_c": ("4d94e081", 7.93, 8.47), "carpet_d": ("9e8beab4", 5.97, 6.57),
 "miami_wide_a": ("87eb16cc", 8.20, 8.93), "miami_wide_b": ("87eb16cc", 8.93, 10.70), "miami_wide_c": ("37572da9", 4.37, 6.33), "miami_wide_d": ("28d452a3", 6.70, 7.40), "miami_wide_e": ("9e8beab4", 5.37, 5.97),
 "street_rear": ("37572da9", 6.33, 7.07), "street_front": ("e1a6da07", 5.97, 7.20), "street_plate": ("37572da9", 7.07, 7.60), "street_side": ("37572da9", 7.60, 8.27),
 "headlight": ("e1a6da07", 7.20, 8.20), "wheel_a": ("e1a6da07", 8.20, 8.83), "wheel_b": ("87eb16cc", 7.87, 8.20), "coast": ("fa30f079", 6.30, 7.23),
}

def clip_path(src):
    return src if src.endswith(".mp4") else os.path.join(ASSETS, "clean", f"{src}.mp4")

def grid(snd):
    """cut candidates after the drop: tracked beats, else synthesized from tempo."""
    s = SND[snd]; drop, dur = s["drop"], s["dur"]
    b = [x for x in s["beats"] if x > drop + 0.2]
    if len(b) < 4:
        per = 60.0 / s["tempo"]; b = [drop + per * i for i in range(1, 40)]
    return [x for x in b if x < dur - 0.3], drop, dur

def seg(src, start, length, speed, idx):
    """cut a segment from a clean clip, scaled to 1080x1920, optionally slowed (speed<1)."""
    out = f"tmp/seg_{idx:02d}.mp4"
    vf = f"setpts=PTS/{speed},scale=1080:1920:flags=lanczos,fps=30"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", clip_path(src), "-t", f"{length/speed + 0.05:.3f}",
                    "-vf", vf, "-t", f"{length:.3f}", "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", out], check=True)
    return out

def prep_external(path, name, note):
    """Any-resolution clip -> 1080x1920 cover-cropped 30fps clean/ext_<name>.mp4. Missing file -> slate."""
    out = f"tmp/ext_{name}.mp4"
    if os.path.exists(path):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-an",
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                        "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", out], check=True)
    else:
        from caption import slate
        slate(note, "tmp/slate.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", "tmp/slate.png", "-t", "8", "-r", "30",
                        "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", out], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
    return [(out, 0.0, d)]

def build(spec):
    name, snd = spec["name"], spec["sound"]
    beats, drop, dur = grid(snd)
    parts = []; idx = 0
    # ---- part 1: bait, must last exactly `drop` seconds
    bait = prep_external(spec["bait_file"], name, spec.get("clip_note", "")) if "bait_file" in spec else BAIT[spec["bait"]]
    avail = sum(e - s for _, s, e in bait)
    speed = max(0.6, min(1.0, avail / drop))  # slow down (max 0.6x) if the bait is shorter than the intro
    t = 0.0
    for (f, s, e) in bait:
        L = min((e - s) / speed, drop - t)
        if L <= 0: break
        parts.append(seg(f, s, L, speed, idx)); idx += 1; t += L
    if drop - t > 0.05 and parts:             # still short: hold the last frame up to the drop
        hold = f"tmp/seg_{idx:02d}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.1", "-i", parts[-1], "-vf", f"tpad=stop_mode=clone:stop_duration={drop - t + 0.2:.3f}",
                        "-t", f"{drop - t:.3f}", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", hold], check=True)
        parts.append(hold); idx += 1
    # ---- part 2: B-roll cut on the beat grid
    steps = spec.get("steps", [2, 2, 1, 1, 1, 1, 2, 2])
    cuts = []; i = -1
    for st in steps * 4:
        i += st
        if i >= len(beats): break
        cuts.append(beats[i])
    times = [drop] + [c for c in cuts if c - drop > 0.4] + [dur]
    shots = spec["broll"]; si = 0
    for k in range(len(times) - 1):
        L = times[k + 1] - times[k]
        while L > 0.08:
            f, s, e = R[shots[si % len(shots)]]; si += 1
            avail = e - s
            if avail >= L:                       # shot covers the interval at normal speed
                parts.append(seg(f, s, L, 1.0, idx)); idx += 1; L = 0
            elif avail / 0.75 >= L:              # gentle slow-mo to reach the next beat
                parts.append(seg(f, s, L, avail / L, idx)); idx += 1; L = 0
            else:                                # use the whole shot and keep filling
                parts.append(seg(f, s, avail, 1.0, idx)); idx += 1; L -= avail
    # ---- captions
    y = spec.get("y", 0.62)
    render(spec["cap1"], "tmp/cap1.png", y_center=y); render(spec["cap2"], "tmp/cap2.png", y_center=y)
    with open("tmp/list.txt", "w") as fh:
        for p in parts: fh.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "tmp/list.txt", "-c", "copy", "tmp/joined.mp4"], check=True)
    src_audio = os.path.join(ASSETS, "sounds", SND[snd]["file"] + ".m4a")
    out = f"{OUT}/{name}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "tmp/joined.mp4", "-i", "tmp/cap1.png", "-i", "tmp/cap2.png", "-i", src_audio,
                    "-filter_complex", f"[0:v][1:v]overlay=0:0:enable='lt(t,{drop})'[a];[a][2:v]overlay=0:0:enable='gte(t,{drop})'[v]",
                    "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
    print(f"{name}: {d:.2f}s  sound={snd} drop@{drop}s  cuts={[round(x,2) for x in times]}")

SPECS = json.load(open(os.environ.get("SPECS", os.path.join(HERE, "..", "specs.json"))))
only = sys.argv[2:] 
for sp in SPECS:
    if only and sp["name"] not in only: continue
    build(sp)
