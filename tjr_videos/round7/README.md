# Round 7 — clean rebuild: 3 s+ bait, drop, 7 s of TJR on a strict beat grid

Files are in `videos/`. 1080x1920, 30 fps, sound baked in. Replaces round 6.

## What was wrong before and what changed

| Problem | Cause | Fix |
|---|---|---|
| Blurry / cheap-looking TJR shots | Footage came from letterboxed fan edits and was upscaled 2.5x, plus caption inpainting | Part 2 now comes almost entirely from one native-vertical clip of the Regera (rear, side, doors up, POV behind the wheel, red dash). No inpainting anywhere. The three soft upscaled shots were removed. |
| Cuts not on the beat | Cuts were placed on any transient (hi-hats, vocal syllables) at uneven spacing | Each sound's beat period is measured at 0.5 ms resolution. Shots are a fixed number of beats (1.0–1.45 s each, never faster). Every cut is then moved to the strongest hit within a quarter-beat so it lands on a kick/snare and the pattern never drifts. |
| Drop not on the switch | Drop detector picked small pickups | Drop = frame where the main transient starts, verified on the rendered file. |
| Half captions / text cut off | Caption bounding not checked at full size | Every caption is rendered within 900 px width and checked at 1080p. |
| Bait too short / cut too fast | 2.7 s baits, 0.5 s shots | Bait is 3.05–3.66 s. Shortest shot in any video is 0.79 s, most are 1.0–1.45 s. |

## Sync measured on the rendered files

For the drop and every cut: how much stronger the audio onset at that frame is than the track average (a hit is ≥2.5x),
and the offset from the cut to the local peak (one frame = 33 ms).

See `sync.txt`. Every cut is within one frame of its local peak. A handful land on quieter bars of the track (1.4–2.0x);
those are still on the beat, the track is just quieter there.

## The 12 videos

| # | File | Bait | Part 1 caption | Part 2 caption | Sound to add (0% volume) |
|---|---|---|---|---|---|
| 1 | `r7_01_watches` | Jack Doherty, LV watch case | Where's your watch collection TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 |
| 2 | `r7_02_jet` | Jake Paul at the jet, then inside with the dog | Where's your jet TJR? 😂 | Wrong tax bracket lil bro | original sound – Bannu |
| 3 | `r7_03_1m` | Logan Paul, $1M in Pokémon boxes | Where's your $1M TJR? 😂 | Different tax bracket lil bro | الصوت الأصلي – Salman |
| 4 | `r7_04_mancave` | Logan Paul, $1M man cave | Where's your man cave TJR? 😂 | Wrong tax bracket lil bro | original sound – 404oskar |
| 5 | `r7_05_lilbaby` | Jack Doherty with Lil Baby | Where's your Lil Baby TJR? 😂 | Wrong tax bracket lil bro | original sound – 🃑𝔾𝕊♢.𝔾ℝ♢𝕌ℙ🃑 |
| 6 | `r7_06_richard` | Jake Paul, Richard Mille in the car | Where's your Richard Mille TJR? 😂 | Wrong tax bracket lil bro | origineel geluid – 𝐥𝐮𝐱𝐮𝐫𝐲𝐱𝐬𝐡 |
| 7 | `r7_07_yacht` | Jake Paul, helicopter over the yacht | Where's your yacht TJR? 😂 | Different tax bracket lil bro | som original – 𝑼𝑺𝑬 𝑯𝑬𝑨𝑫𝑺𝑬𝑻 |
| 8 | `r7_08_grillz` | Jack Doherty getting grillz | Where's your grillz TJR? 😂 | Not even close lil bro | original sound – calebgordenn® |
| 9 | `r7_09_chain` | Logan Paul, $200K chain | Where's your chain TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 |
| 10 | `r7_10_panda` | Jake Paul with his panda | Where's your panda TJR? 😂 | Wrong tax bracket lil bro | North Pole (Cynnmixx) – prodbyCyn |
| 11 | `r7_11_helicopter` | Jake Paul in the helicopter | Where's your helicopter TJR? 😂 | Wrong tax bracket lil bro | original sound – calebgordenn® |
| 12 | `r7_12_mansion` | Jack Doherty's garage: Lambos + Cybertruck | Where's your mansion TJR? 😂 | Wrong tax bracket lil bro | original sound – Bannu |

## Sounds: how to make the TikTok sound line up

The baked audio starts partway into some sounds so the drop lands at 3–3.7 s. When you add the sound on TikTok at 0%
volume this doesn't matter. If you want the added sound audible, trim its start to the value below:

| Sound | Trim start to | Drop in the video |
|---|---|---|
| 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 0.00 s (video has 0.1 s of silence first) | 3.08 s |
| Bannu | 2.82 s | 3.30 s |
| Salman | 0.00 s | 3.66 s |
| 404oskar | 3.00 s | 3.43 s |
| GS Group | 0.60 s | 3.42 s |
| luxuryxsh | 1.50 s | 3.42 s |
| USE HEADSET | 2.80 s | 3.58 s |
| calebgordenn | 0.00 s (video has 0.3 s of silence first) | 3.05 s |
| North Pole | 1.80 s | 3.23 s |

## Sources

Regera footage: `@brezscales` post 7539575477426523406 (native vertical) and two shots from `@tjrmindset` 7650883107087813918.
Bait: `@jackdoherty`, `@loganpaul`, `@jakepaul`, all caption-free segments. Nothing from your own posts.

## Rebuilding

```
python3 pipeline/beat8.py                      # beat period candidates per sound
python3 pipeline/build7.py out_dir             # renders every entry in specs_round7.json using plan7.json
python3 pipeline/verify7.py out_dir            # hit strength + offset at every placed cut
```
