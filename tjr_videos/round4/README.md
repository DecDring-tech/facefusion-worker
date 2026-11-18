# Round 4 — 11 videos, fresh Regera footage only, every cut on a drum hit

Files are in `videos/`. 1080x1920, 30 fps, sound baked in. Replaces round 3.

## What changed from round 3

- **No footage from your posts.** Every shot was fingerprinted against your 11 uploads, and every shot from the same
  scenes (the Miami waterfront pose, that street, the headlight close-up, the night car meet) was thrown out even where the
  take differed. Part 2 now uses: TJR driving the Regera top-down filmed from another car, the inside-the-car clip, the road
  and driveway edit footage, the red-interior shots, the key-fob shot, the garage lot, and his Bugatti for one video.
- **Cuts land on the hits.** The drop and every B-roll cut sit on a detected drum transient, and every segment is an exact
  frame count so nothing drifts. Measured on the rendered files, every placed cut is within one frame of the hit:

| Video | Offset of drop + each cut to the nearest hit (ms) | Worst |
|---|---|---|
| r4_01_mansion | 14, 1, -12, 15, -10, -16, -4, 12, 5 | 16 ms |
| r4_02_closet | 8, 33, -12, 8, -23, -16 | 33 ms |
| r4_03_lambos | 1, -5, -5, 5, 4, -14 | 14 ms |
| r4_04_grillz | 12, 13, -9, -15, -4, 3, -14 | 15 ms |
| r4_05_lilbaby | 17, 15, 0, 15, 8, -12, 4 | 17 ms |
| r4_06_jetmaybach | 17, 0, 16, 11, -9, 15 | 17 ms |
| r4_07_boat | 25, -11, -4, 16, -6 | 25 ms |
| r4_08_mancave | 15, 12, -3, 12, 2, -12, -14 | 15 ms |
| r4_09_chain | 1, -5, -5, 5, 4, -14 | 14 ms |
| r4_10_panda | 33, 9, 14, 18, 29, 4 | 33 ms |
| r4_11_bugatti | 12, 13, -9, -15, -4, 3, -14 | 15 ms |

One frame at 30 fps is 33 ms. `pipeline/hits.png` shows the onset curve of each sound with the chosen hits marked.

## The 11 videos

| # | File | Bait (who / what) | Part 1 caption | Part 2 caption | Sound to add (0% volume) |
|---|---|---|---|---|---|
| 1 | `r4_01_mansion` | Jack Doherty, $5M house tour intro | Where's your mansion TJR? 😂 | Wrong tax bracket lil bro | original sound – Bannu |
| 2 | `r4_02_closet` | Jack Doherty, $1M closet tour | Where's your closet TJR? 😂 | Different tax bracket lil bro | الصوت الأصلي – Salman |
| 3 | `r4_03_lambos` | Jack Doherty, drone over his Lambos | Where's your Lambos TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 |
| 4 | `r4_04_grillz` | Jack Doherty getting grillz fitted | Where's your grillz TJR? 😂 | Not even close lil bro | original sound – calebgordenn® |
| 5 | `r4_05_lilbaby` | Jack Doherty with Lil Baby and the chain | Where's your Lil Baby TJR? 😂 | Wrong tax bracket lil bro | original sound – 🃑𝔾𝕊♢.𝔾ℝ♢𝕌ℙ🃑 |
| 6 | `r4_06_jetmaybach` | Jack Doherty at the jet with the Maybach | Jet or Maybach TJR? 😂 | Koenigsegg lil bro | origineel geluid – 𝐥𝐮𝐱𝐮𝐫𝐲𝐱𝐬𝐡 |
| 7 | `r4_07_boat` | Jack Doherty on the quad with the boat | Where's your boat TJR? 😂 | Different tax bracket lil bro | som original – 𝑼𝑺𝑬 𝑯𝑬𝑨𝑫𝑺𝑬𝑻 |
| 8 | `r4_08_mancave` | Logan Paul, $1M man cave | Where's your man cave TJR? 😂 | Wrong tax bracket lil bro | original sound – 404oskar |
| 9 | `r4_09_chain` | Logan Paul, $200K chain at WrestleMania | Where's your chain TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 |
| 10 | `r4_10_panda` | Jake Paul with his panda | Where's your panda TJR? 😂 | Wrong tax bracket lil bro | North Pole (Cynnmixx) – prodbyCyn |
| 11 | `r4_11_bugatti` | Jake Paul, helicopter at Lake Powell | Where's your helicopter TJR? 😂 | Bugatti AND a Koenigsegg lil bro | original sound – calebgordenn® |

Each sound name is the one on your own post, listed in `pipeline/sounds/*.json` with the post it was taken from. Posting:
favourite the sound from your post, upload the mp4, add the sound, set **Added sound 0 / Original sound 100**, don't trim.

## Sources

`pipeline/provenance.json` lists the account, post ID and time range of every clip. Regera footage is from the fan pages
`@tjrform.01` and `@tjrclipsz2`; bait is from `@jackdoherty`, `@loganpaul`, `@jakepaul`.

## Rebuilding

```
python3 pipeline/ttdl.py <post id> out.mp4                      # download a public TikTok post, no watermark
python3 pipeline/clean3.py out.mp4 src.mp4 start end [band_top band_bottom min_stroke kernel window dilate]
python3 pipeline/hits.py                                        # drop + hit grid per sound -> hits.json, hits.png
python3 pipeline/build4.py out_dir                              # renders every entry in specs_round4.json
python3 pipeline/verify4.py out_dir                             # offset of every placed cut to the nearest hit
python3 pipeline/overlap.py clip_dir                            # fingerprint clips against the reference uploads
```
`build4.py` expects cleaned clips in `r4clean/` and `hits.json` next to the scripts.
