# Round 8 — 10 new videos: no flash frames, single-take shots only, cuts on the grid

Files are in `videos/`. 1080x1920, 30 fps, sound baked in. Round 7 stays as the previous set.

## What changed from round 7

- **No tiny clips can appear.** Each Regera shot is now a single continuous take (no internal cut inside any window),
  each shot is used at most once per video, and the builder refuses to render if any slot is under 0.9 s. A scene-change
  scan on the rendered file then confirms the only visual cuts are the placed ones (`sync.txt`, `stray_visual_cuts=[]`).
- **Bait is one continuous shot** so nothing flashes before the drop. The jet, Lil Baby and watch baits were re-cut
  to their single-take windows; the yacht and helicopter baits (fast-cut sources) were replaced by the mansion driveway and
  the garage walk.
- **Cuts stay on the grid.** A cut may move at most 50 ms (1.5 frames) to sit on the hit, so shots can't shrink.
- **Better footage.** Two new native-res shots from a different day: the Regera at the pump (gas-station pan, and TJR
  at the car). Everything soft or upscaled from letterboxed edits is gone.

## The 10 videos

| # | File | Bait | Part 1 caption | Part 2 caption | Sound to add (0% volume) | Switch |
|---|---|---|---|---|---|---|
| 1 | `r8_01_watches` | Jack Doherty, LV watch case | Where's your watch collection TJR? 😂 | Where's your Ferrari lil bro? | الصوت الأصلي – Salman | 3.66 s |
| 2 | `r8_02_jet` | Jake Paul outside the jet | Where's your private jet TJR? 😂 | Wrong tax bracket lil bro | original sound – calebgordenn® | 3.05 s |
| 3 | `r8_03_mancave` | Logan Paul, $1M man cave | Where's your $1M man cave TJR? 😂 | Wrong tax bracket lil bro | original sound – 404oskar | 3.43 s |
| 4 | `r8_04_lilbaby` | Jack Doherty with Lil Baby | Where's your celebrity friends TJR? 😂 | Wrong tax bracket lil bro | original sound – Bannu | 3.32 s |
| 5 | `r8_05_richard` | Jake Paul, Richard Mille in the car | Where's your Richard Mille TJR? 😂 | Wrong tax bracket lil bro | North Pole (Cynnmixx) – prodbyCyn | 3.23 s |
| 6 | `r8_06_mansion` | Jack Doherty's driveway, Lambos + Cybertruck | Where's your car collection TJR? 😂 | Different tax bracket lil bro | som original – 𝑼𝑺𝑬 𝑯𝑬𝑨𝑫𝑺𝑬𝑻 | 3.58 s |
| 7 | `r8_07_grillz` | Jack Doherty getting grillz | Where's your diamond grillz TJR? 😂 | Not even close lil bro | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 3.08 s |
| 8 | `r8_08_chain` | Logan Paul, $200K chain | Where's your $200K chain TJR? 😂 | Where's your Ferrari lil bro? | origineel geluid – 𝐥𝐮𝐱𝐮𝐫𝐲𝐱𝐬𝐡 | 3.42 s |
| 9 | `r8_09_panda` | Jake Paul with his panda | Where's your pet panda TJR? 😂 | Wrong tax bracket lil bro | original sound – 🃑𝔾𝕊♢.𝔾ℝ♢𝕌ℙ🃑 | 4.02 s |
| 10 | `r8_10_garage` | Jack Doherty's carport walk | Where's your $5M house TJR? 😂 | Wrong tax bracket lil bro | original sound – calebgordenn® | 3.05 s |

Trim points for each sound (only needed if you turn the added sound up): BALLERSZN 0.00 (video has 0.1 s lead-in),
Bannu 5.66 (same as your own Bannu posts), Salman 0.00, 404oskar 3.00, GS Group 0.00, luxuryxsh 1.50, USE HEADSET 2.80,
calebgordenn 0.00 (0.3 s lead-in), North Pole 1.80.

**Loud-intro sounds.** Bannu, Salman, luxuryxsh and North Pole have no quiet intro, so the baked audio fades in over
0.6–2 s on those four and the Bannu start matches the point your own posts used. The Bannu sound is only 14.4 s long, so
that video is 8.7 s with 5.35 s after the drop.

## Sync and cut checks on the rendered files

`sync.txt`: for every placed cut, onset strength vs the track average and offset to the local peak, plus the scene-change
scan. All 10 show `stray_visual_cuts=[]`; shortest shot is 1.0 s or more in every video except the man cave, where the bait
itself changes shot 0.86 s before the drop.

## Sources

Regera: `@brezscales` posts 7539575477426523406 and 7538871880439090446 (native vertical). Bait: `@jackdoherty`,
`@loganpaul`, `@jakepaul`, caption-free single takes. Nothing from your own posts.
