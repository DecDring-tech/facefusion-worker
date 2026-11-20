# Marko series — 10 videos in the TJR style

Same setup as the TJR rounds: a 3–4 s opening clip of someone else's flex captioned **"Where's your ___ Marko? 😂"**, a hard cut
on the beat drop, then 5–7 s of Marko cut on every beat, walking through 2–3 cold recordings in order. Same font, caption
spot, beat grid, drop timing, sounds and checks as rounds 9–12. 1080x1920, 30 fps, sound baked in.

**Who Marko is:** Marko Vituk, [@markovituk](https://www.tiktok.com/@markovituk) (1,892 posts, the same guy as the
@markoclipping posts). He's a UK teen influencer boxer, undefeated (12-0 going by Gunman Boxing's posts) and Gunman's
middleweight champion. His next fight is Dec 12 against JackDoesBoxing. Boxing is his flex the way the Regera is TJR's, so
Part 2 is his fight-night footage and the payoff line is the boxing version of "Wrong tax bracket": **"Wrong weight class lil bro"**.

## The 10 videos

| # | File | Opening clip | Part 1 caption | Part 2 caption | Sound to add (0% volume) | Switch | Post caption |
|---|---|---|---|---|---|---|---|
| 1 | `mk01_belt` | Jake Paul at the jet with his belt | Where's your championship belt Marko? 😂 | Middlewieght champ lil bro ⚠️ | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 3.08 s | Logan Paul's belt vs Marko 💀 #marko #markovituk #boxing |
| 2 | `mk02_supercar` | Jake Paul in the blue supercar | Where's your supercar Marko? 😂 | 11-0 lil bro ⚠️ | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 3.08 s | Logan Paul gets brutally Mogged by Marko #marko #markovituk |
| 3 | `mk03_jet` | Jake Paul inside his jet | Where's your private jet Marko? 😂 | Wrong weight class lil bro | original sound – calebgordenn® | 3.05 s | Logan Paul gets Mogged at 40,000 ft 😭 #marko #markovituk |
| 4 | `mk04_richard` | Jake Paul with the Richard Mille | Where's your Richard Mille Marko? 😂 | Undefeted lil bro ⚠️ | original sound – 𝐵𝐴𝐿𝐿𝐸𝑅𝑆𝑍𝑁 | 3.08 s | Logan Paul's watch vs Marko's record 🥱 #marko #markovituk |
| 5 | `mk05_mansion` | Jake Paul at his mansion | Where's your mansion Marko? 😂 | Different weight class lil bro | North Pole (Cynnmixx) – prodbyCyn | 3.23 s | Logan Paul thought a mansion was a flex 💀 #marko #markovituk |
| 6 | `mk06_lambos` | Jake Paul's pool with the yellow Lambos | Where's your Lambo collection Marko? 😂 | Heavyweight champ lil bro ⚠️ | الصوت الأصلي – Salman | 3.66 s | Logan Paul gets brutally Mogged by Marko #marko #markovituk |
| 7 | `mk07_gym` | Logan Paul's home gym | Where's your home gym Marko? 😂 | Wrong weight class lil bro | original sound – 🃑𝔾𝕊♢.𝔾ℝ♢𝕌ℙ🃑 | 4.02 s | Jake Paul's gym vs a real boxer 😭 #marko #markovituk |
| 8 | `mk08_chain` | Logan Paul, $200K chain | Where's your $200K chain Marko? 😂 | 12-0 lil bro | Party Funk – Young Madz & MC Zudo Boladão | 3.08 s | Jake Paul's chain vs Marko's record 🥱 #marko #markovituk |
| 9 | `mk09_billion` | MrBeast selfie | Where's your billion dollars Marko? 😂 | Undefeated lil bro | [original sound – 404oskar](https://www.tiktok.com/@404oskar/video/7678418939537296673) (Lexa) | 3.08 s | MrBeast vs Marko 😭 #marko #markovituk #boxing |
| 10 | `mk10_lambo` | Jack Doherty by his blue Lambo | Where's your Lamborghini Marko? 😂 | Wrong weight class lil bro | som original – 𝑼𝑺𝑬 𝑯𝑬𝑨𝑫𝑺𝑬𝑻•音楽🎶🎧 | 3.58 s | Jack Doherty gets Mogged by Marko 💀 #marko #markovituk |

**⚠️ Rage bait (the 3.5M recipe):** #1, #2, #4 and #6 have a deliberate mistake that fans will correct in the comments.
"Middlewieght" and "Undefeted" are misspelt, he's 12-0 not 11-0, and he's a middleweight champ, not heavyweight. Every
Jake clip is labelled Logan in the post caption and every Logan clip is labelled Jake, like your Logan/Jake post.

## Marko footage used (all native 1080x1920, no captions, no inpainting)

| Source | What it is | Used |
|---|---|---|
| `ring` | @markovituk 7656853193879457046 "11-0-0 baby!": ringside, the Gunman title fight (black shorts vs green) | 1.7–28.2 s, single-take stretches only, referee-blocked part removed |
| `red` | @liaminsidetheballer 7475052144190639382: one long phone recording at ring level, red ballroom (4-0 fight) | 12.3–24.6, 45.5–57.5, 63–71 s |
| `corner` | @markovituk fight-day vlog 7651581756046576898: Marko on the ropes in his corner | 49.4–56.8 s |
| `warmup` | same vlog: backstage pad warm-up in the TEAM VITUK top | 26.6–32.0 s |
| `ko` | @hekinationtimz 7685129377872350486: the knockdown on the GUNMAN canvas | 0.1–5.0 s |
| `belt` | @markovituk 7474385745709534487 "4-0 baby": Marko with the belt | 4.5–17.9 s |

Openers come from the clean bait pool built for the TJR rounds (`@jakepaul`, `@loganpaul`, `@mrbeast`, `@jackdoherty`
single takes).

## Checks on the rendered files

`sync.txt`: every placed cut is within 50 ms of its hit, and `stray_visual_cuts=[]` on all 10. Every shot is at least 1.0 s,
except #8, where the Party Funk beat is 0.92 s.

## Rebuilding

```
SPECS=pipeline/specs_marko.json SRCS=pipeline/sources_marko.json PLAN=pipeline/plan_marko.json python3 pipeline/build9.py out_dir
python3 pipeline/verify8.py out_dir
```
