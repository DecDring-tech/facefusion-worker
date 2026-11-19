# Round 9 — cold long-take B-roll, walked through on the beat

Everything from round 8 is the same (bait, drop timing, beat grid, titles, sounds, fade-ins). The only change is how
Part 2 is built.

## How Part 2 is built now

Instead of a pool of short angles, each video walks through 2–3 long phone recordings of the Regera **in order**:
on every beat it cuts to the next window of the same recording (jumping forward 0.3–2 s), takes 2–3 windows from it, then
moves to the next recording. No window is reused within a video and no window crosses a cut in its source.

| Source | What it is | Usable |
|---|---|---|
| `night` | `@brezscales` "car week trio" 7538662108729183502: night walk-around at a gas station — doors up, red interior, red body, TJR standing arms crossed | 13.1–24.7 s, five clean stretches |
| `day` | `@brezscales` 7539575477426523406: door opening, car on the street, TJR at the wheel, rear | 6.9–27.3 s, five clean stretches |
| `gas` | `@brezscales` "I met TJR" 7538871880439090446: pump pan, TJR at the car | 6.25–9.85 s |
| `spot` | `@stardrivendaily` 7538798422510390550: the Regera in traffic at Car Week (banner cropped) | 0–3.15 s |

All native 1080x1920 phone footage, no captions, no inpainting. Fingerprinted against your 11 uploads: no overlap
(your gas-station shots are a daytime Shell station; this is a different station at night).

## The 10 videos

| # | File | Sound (0% volume) | Part 2 walk |
|---|---|---|---|
| 1 | `r9_01_watches` | الصوت الأصلي – Salman | night ×3 → day ×3 |
| 2 | `r9_02_jet` | original sound – calebgordenn® | day ×3 → night ×3 → gas ×1 |
| 3 | `r9_03_mancave` | original sound – 404oskar | night ×2 → day ×2 |
| 4 | `r9_04_lilbaby` | original sound – Bannu | night ×2 → gas ×1 → day ×1 |
| 5 | `r9_05_richard` | North Pole (Cynnmixx) – prodbyCyn | night ×3 → spot ×2 → day ×2 |
| 6 | `r9_06_mansion` | som original – 𝑼𝑺𝑬 𝑯𝑬𝑨𝑫𝑺𝑬𝑻 | day ×3 → night ×2 |
| 7 | `r9_07_grillz` | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | night ×3 → day ×3 → gas ×1 |
| 8 | `r9_08_chain` | origineel geluid – 𝐥𝐮𝐱𝐮𝐫𝐲𝐱𝐬𝐡 | day ×2 → night ×2 |
| 9 | `r9_09_panda` | original sound – 🃑𝔾𝕊♢.𝔾ℝ♢𝕌ℙ🃑 | gas ×2 → night ×3 → day ×1 |
| 10 | `r9_10_garage` | original sound – calebgordenn® | night ×3 → spot ×2 → day ×2 |

Titles, switch times and sound trim points are the same as round 8.

## Checks on the rendered files

`sync.txt`: every placed cut is within one frame of its hit, `stray_visual_cuts=[]` on all 10, every shot at least 1.0 s
(the man cave bait has its own shot change 0.86 s before the drop, as in round 8).

## Rebuilding

```
python3 pipeline/build9.py out_dir        # uses specs_round9.json, sources9.json, plan8.json, hits5.json
python3 pipeline/verify8.py out_dir
```
To add a source, add it to `sources9.json` with its clean stretches (no cuts inside them), then reference it in a spec's
`sources` list as `[name, windows, optional_start_time]`.
