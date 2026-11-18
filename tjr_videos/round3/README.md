# Round 3 — 11 videos, every clip sourced by me (your uploads were reference only)

Files are in `videos/`. 1080x1920, 30 fps, sound baked in. Nothing from your 11 reference uploads is used.

## Where the footage came from

- **TJR's red Koenigsegg Regera** (Part 2 of every video): six posts on the TJR fan/clip pages `@tjrclipsz2` and `@tjrform.01`
  (Miami skyline pose with the doors up, headlight close-up, street front/rear, night road, driveway, red interior, crowd at night,
  the key-fob shot). Burned-in captions were stripped, letterboxed shots were zoom-cropped to full frame.
- **Bait clips** (Part 1): Jack Doherty's own TikTok (`@jackdoherty`), Logan Paul's (`@loganpaul`), Jake Paul's (`@jakepaul`).
  Captions from the originals stripped. Exact post IDs and timestamps are in `pipeline/sources/provenance.json`.
- **Sounds**: pulled directly off your own posts through the TikTok API, so the baked audio is bit-for-bit the sound you'll add.
  Drop points re-measured on the real files.

## The 11 videos

| # | File | Bait (who / what) | Part 1 caption | Part 2 caption | Sound to add (0% volume) | Drop |
|---|---|---|---|---|---|---|
| 1 | `r3_01_mansion` | Jack Doherty, $5M house tour intro, Cybertruck + Lambo behind him | Where's your mansion TJR? 😂 | Wrong tax bracket lil bro | original sound – Bannu (your "It's red lil bro" 67K post) | 6.11 s |
| 2 | `r3_02_closet` | Jack Doherty, $1M closet tour | Where's your closet TJR? 😂 | Different tax bracket lil bro | الصوت الأصلي – Salman (your "Jack gets brutally Mogged" post) | 3.69 s |
| 3 | `r3_03_lambos` | Jack Doherty drone shot of his Lambos on the driveway | Where's your Lambos TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 (your 3.5M post) | 2.95 s |
| 4 | `r3_04_grillz` | Jack Doherty getting Johnny Dang grillz fitted | Where's your grillz TJR? 😂 | Not even close lil bro | original sound – calebgordenn® (your "Price of Paris" post) | 2.73 s |
| 5 | `r3_05_lilbaby` | Jack Doherty on the couch with Lil Baby holding his chain | Where's your Lil Baby TJR? 😂 | Wrong tax bracket lil bro | original sound – 🃑𝔾𝕊♢.𝔾ℝ♢𝕌ℙ🃑 (your "Maybach" post) | 4.00 s |
| 6 | `r3_06_jetmaybach` | Jack Doherty + McKinley at the jet with the white Maybach | Jet or Maybach TJR? 😂 | Koenigsegg lil bro | origineel geluid – 𝐥𝐮𝐱𝐮𝐫𝐲𝐱𝐬𝐡 (your "SVJ 🥱" post) | 4.89 s |
| 7 | `r3_07_boat` | Jack Doherty on the quad showing the new boat | Where's your boat TJR? 😂 | Different tax bracket lil bro | som original – 𝑼𝑺𝑬 𝑯𝑬𝑨𝑫𝑺𝑬𝑻 (your "My SVJ is red" post) | 6.35 s |
| 8 | `r3_08_mancave` | Logan Paul, $1M man cave reveal with the aquarium | Where's your man cave TJR? 😂 | Wrong tax bracket lil bro | original sound – 404oskar (your "Where's your Ferrari lil bro" post) | 6.41 s |
| 9 | `r3_09_chain` | Logan Paul at WrestleMania, $200K chain | Where's your chain TJR? 😂 | Where's your Ferrari lil bro? | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 2.95 s |
| 10 | `r3_10_panda` | Jake Paul sitting with his panda | Where's your panda TJR? 😂 | Wrong tax bracket lil bro | North Pole (Cynnmixx) – prodbyCyn (your "TJR brutally car mogs jack" 75K post) | 5.02 s |
| 11 | `r3_11_helicopter` | Jake Paul at Lake Powell, helicopter landing behind him | Where's your helicopter TJR? 😂 | Wrong tax bracket lil bro | original sound – calebgordenn® | 2.73 s |

Posting: favourite the sound from your own post, upload the mp4, add the sound, set **Added sound 0 / Original sound 100**, don't trim.

## Rebuilding / making more

```
python3 pipeline/ttdl.py <tiktok post id or url> out.mp4      # downloads any public TikTok post without watermark
python3 pipeline/ttsound.py <post id> sound.mp3               # downloads the sound off a post
python3 pipeline/clean3.py out.mp4 src.mp4 start end          # cuts a segment and strips burned-in captions
python3 pipeline/build3.py out_dir                            # renders every entry in specs_round3.json
```
`build3.py` expects the cleaned clips in `r3clean/` and the sounds in `sounds_dl/`, both next to the scripts; the cleaned clips
were not committed (280 MB) but every one can be regenerated from `pipeline/sources/provenance.json` with the two commands above.
