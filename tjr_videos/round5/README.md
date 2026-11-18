# Round 5 — final set: switch on the drop, no inpainted captions, no footage from your posts

Files are in `videos/`. 1080x1920, 30 fps, sound baked in. Replaces round 4.

## What changed

- **The switch to TJR is on the drop, measured from your own posts.** I aligned each of your reference clips to its sound
  by cross-correlation and read off the frame where your video switches to TJR. That showed my earlier drop detector was
  wrong on three tracks: the Bannu sound switches at 8.98 s into the sound (not 6.15), the Salman sound at 3.66 s (not 3.54)
  and the 404oskar sound at 6.43 s (not 6.42, your cut is at 6.53). Each drop is now placed on the frame where the transient
  starts. Your own cuts on those posts were 3–4 frames after the hit; these are on it.
- **Sound starts are offset the way you do it.** Bannu starts 5.66 s in, USE HEADSET 2.80 s in, North Pole 2.0 s in, so the
  switch comes at 3.0–3.6 s like your posts instead of after a 6–9 s intro.
- **No blurred captions.** Every clip that needed caption inpainting was thrown out: the top-down side views, the inside-car
  clip, and the four Jack Doherty clips with word captions. All bait is now caption-free source footage and all Regera shots
  come from the clean sections of the fan-page edits.
- **No footage from your posts.** Same rule as round 4.

## Sync check on the rendered files

Offset of the drop and each cut to the nearest audio hit (ms). One frame is 33 ms. A positive number means the cut lands
just before the hit, which is how it should feel.

| Video | Offsets | Worst |
|---|---|---|
| r5_01_lambos | 35, -5, -5, 5, 4, -14 | 35 |
| r5_02_jet | 3, 6, 22, 4, 9, -9, -16, -2, 1 | 22 |
| r5_03_1m | 47, 33, -12, 8, -23, -16 | 47 |
| r5_04_mancave | 15, 12, -3, 12, 2, -12, -14 | 15 |
| r5_05_lilbaby | 17, 15, 0, 15, 8, -12, 4 | 17 |
| r5_06_richard | 17, 0, 16, 11, -9, 15 | 17 |
| r5_07_yacht | 21, -14, -8, 12, -10 | 21 |
| r5_08_grillz | 12, 13, -9, -15, -4, 3, -14 | 15 |
| r5_09_chain | 35, -5, -5, 5, 4, -14 | 35 |
| r5_10_panda | 30, 6, 11, 15, 32, 7 | 32 |
| r5_11_helicopter | 12, 13, -9, -15, -4, 3, -14 | 15 |

## The 11 videos

| # | File | Bait (who / what) | Part 1 caption | Part 2 caption | Sound to add (0% volume) | Switch |
|---|---|---|---|---|---|---|
| 1 | `r5_01_lambos` | Jack Doherty, drone over his Lambos | Where's your Lambos TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 2.97 s |
| 2 | `r5_02_jet` | Jake Paul at the jet, then inside with the dog | Where's your jet TJR? 😂 | Wrong tax bracket lil bro | original sound – Bannu | 3.30 s |
| 3 | `r5_03_1m` | Logan Paul with $1M in Pokémon boxes | Where's your $1M TJR? 😂 | Different tax bracket lil bro | الصوت الأصلي – Salman | 3.63 s |
| 4 | `r5_04_mancave` | Logan Paul, $1M man cave | Where's your man cave TJR? 😂 | Wrong tax bracket lil bro | original sound – 404oskar | 6.40 s |
| 5 | `r5_05_lilbaby` | Jack Doherty with Lil Baby and the chain | Where's your Lil Baby TJR? 😂 | Wrong tax bracket lil bro | original sound – 🃑𝔾𝕊♢.𝔾ℝ♢𝕌ℙ🃑 | 4.00 s |
| 6 | `r5_06_richard` | Jake Paul in the car with the Richard Mille | Where's your Richard Mille TJR? 😂 | Wrong tax bracket lil bro | origineel geluid – 𝐥𝐮𝐱𝐮𝐫𝐲𝐱𝐬𝐡 | 4.90 s |
| 7 | `r5_07_yacht` | Jake Paul, helicopter over the yacht at Lake Powell | Where's your yacht TJR? 😂 | Different tax bracket lil bro | som original – 𝑼𝑺𝑬 𝑯𝑬𝑨𝑫𝑺𝑬𝑻 | 3.57 s |
| 8 | `r5_08_grillz` | Jack Doherty getting grillz fitted | Where's your grillz TJR? 😂 | Not even close lil bro | original sound – calebgordenn® | 2.73 s |
| 9 | `r5_09_chain` | Logan Paul, $200K chain at WrestleMania | Where's your chain TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 2.97 s |
| 10 | `r5_10_panda` | Jake Paul with his panda | Where's your panda TJR? 😂 | Wrong tax bracket lil bro | North Pole (Cynnmixx) – prodbyCyn | 3.00 s |
| 11 | `r5_11_helicopter` | Jake Paul in the helicopter | Where's your helicopter TJR? 😂 | Bugatti AND a Koenigsegg lil bro | original sound – calebgordenn® | 2.73 s |

Posting: favourite the sound from your own post, upload the mp4, add the sound, set **Added sound 0 / Original sound 100**,
don't trim. The sound name maps to your post in `pipeline/sounds/*.json`.

## Sources

`pipeline/provenance.json` lists the account, post ID and time range of every clip. Regera footage is from the fan pages
`@tjrform.01` and `@tjrclipsz2` (edit sections only); bait is from `@jackdoherty`, `@loganpaul`, `@jakepaul`.

## Rebuilding

```
python3 pipeline/ttdl.py <post id> out.mp4          # download a public TikTok post, no watermark
python3 pipeline/refdrop.py                         # align your reference clips to the sounds, read off your switch frames
python3 pipeline/hits5.py                           # drop table + hit grid per sound -> hits5.json, hits5.png
python3 pipeline/build5.py out_dir                  # renders every entry in specs_round5.json
python3 pipeline/verify4.py out_dir                 # offset of every placed cut to the nearest hit
```
