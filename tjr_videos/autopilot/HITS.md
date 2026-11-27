# Hit list

Every batch is built from these. The user sends each new hit as it happens; add it here with what it did and what it
shares with the others, then base the next batch on it. Openers stay with the person in the hits (Jake Paul) unless the
user says otherwise. Never swap in a different creator on your own.

## Marko (@markovclipping)

| Hit | Batch file | Views when logged | Opener | Caption 1 → 2 | Sound |
|---|---|---|---|---|---|
| Chains | marko_005/mk5_10_chains | 70.5K at 32 h (10.0 s avg watch, 47.0% full, 22 followers) | Jake, face filling the frame, looking into the lens, chains on | Where's your chains Marko? 😂 → Wrong tax bracket lil bro | USE HEADSET (S7), 4 × 1.45 s, 9.37 s |
| Gold chain | marko_007/mk7_02_goldchain | 30.1K at 8 h (8.0 s avg watch, 34.4% full, 10 followers) | Jake, face filling the frame, looking into the lens, gold chain on | Where's your gold chain Marko? 😂 → Wrong tax bracket lil bro | USE HEADSET (S7), 4 × 1.45 s, 9.37 s |

Shared: Jake; face close-up to lens in frame 1; a thing money buys on him, named in caption 1; S7; "Wrong tax bracket
lil bro"; Marko's face on shots 1–2 at night with the Ferrari/Urus, Lambo to finish.
Misses for contrast: championship belt 3.8K (wide shot, belt is won not bought), jet ski 3.3K (action shot, looking away),
"Where's your Ferrari" on the tattoos opener 740 (side-on, item not visible).

## TJR (@tjrv001)

| Hit | Views | Opener | Caption 1 → 2 | Sound |
|---|---|---|---|---|
| Logan Paul gets brutally car Mogged by TJR | 3.6M | Jake in his pool, yellow Lambos behind | What colours your ferari TJR? 😂 → It's Red. | BALLERSZN (S1), drop 3.08 s, 8.2 s, shot 2 double length |

What made it: Jake labelled "Logan" in the post caption, "ferari" misspelt and the wrong car, a two-word cold answer,
8 s loop.

## Caption rule

Caption 1 must ask about something money buys that is visible in the opener, so "Wrong tax bracket lil bro" answers it.
Not things you win or grow (belt, beard, tattoos, friends).

## Footage status (27 Nov 2026)

Every post on @jakepaul (about 620) has been screened. The Jake openers that match the hits (face to lens, jewellery or
another bought flex in shot, no burned-in text) are all used now; `batches/marko_next10/` holds the ten closest unposted
videos in posting order. More hit-grade Marko videos need new Jake footage from the user (selfie close-ups with a
chain/watch, 4 s+, no text on screen). Do not substitute another creator.

## Priority rule (user, 27 Nov 2026)

What makes a video go viral comes first and overrules any earlier production rule. For start clips this means it is fine to
zoom into a wider Jake shot so his face and jewellery fill the frame, slow a short clip to reach the opener length, or crop
burned-in text off. Each new video needs a new start clip; TJR/Marko payoff clips can repeat with small variations.
Never resend a start clip the user has already been sent. Keep replies short.

## Answer rule (user, 28 Nov 2026)

Marko's answer must actually answer Jake's question, short and cold. "How much you make a year?" → "More than you."
"How much tax you pay?" → "More than you make." Use "Wrong tax bracket lil bro" only when the question is "Where's your
<thing money buys>".

## Face-on rule and how to find the clips (user, 28 Nov 2026)

Scoreboard on @markovclipping: chains 76.9K, gold chain 50.8K, belt 5.1K, jet ski 3.9K, Ferrari (side-on) 1.7K,
art collection 464, bank (dim, face small) 97. The start clip must be face-on to the lens with the face filling the
screen, at normal speed, not zoomed. Measured with `engine/scripts/facescan.py` (YuNet): the hits score 0.44 and 0.63 face
width / frame width in the first frames; the flops 0.18–0.30. Only build from stretches scoring 0.40+ at the start and
0.30+ throughout. If the face-on stretch is under 3.6 s, use `S7_short` (same sound, opener 3.08 s) instead of slowing it.
