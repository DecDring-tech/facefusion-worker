# clipper — Markov motivational edits

Turns a long talking-head recording plus a folder of luxury b-roll into 9:16
clips in the style of the reference TikToks: speaker on camera for the strong
lines, dark moody b-roll over the rest, word-by-word captions, no music, only
the talking audio.

## What the references do (and what this copies)

| Reference account      | Face? | Cut rhythm         | Grade                  | Captions                                   |
|------------------------|-------|--------------------|------------------------|--------------------------------------------|
| stoicstoriesx          | yes   | punch-ins, no cuts | dark, desaturated      | bold serif, 1–3 words, dead centre         |
| lifelesson401          | yes   | one reframe        | dark, cool             | small ALL-CAPS sans phrases, centre        |
| calverne_brand         | no    | ~2 s b-roll cuts   | slightly desaturated   | sans sentence fragments, upper third       |
| goldenlife.mindset     | no    | 2–4 s b-roll cuts  | black & white          | serif single words, uppercase              |
| 1make.more.money1      | no    | 3–5 s b-roll holds | very dark blue         | tiny single lowercase word, centre         |

The script mixes the two families: face for the hook and the payoff lines,
b-roll in between, all through one grade so the cuts feel like one piece.

## Install

```bash
pip install faster-whisper "opencv-python-headless==4.11.0.86"
# ffmpeg with libass + libx264 must be on PATH; fonts Inter + Caladea (fonts-crosextra-caladea)
```

## Use

```bash
python clipper/make_clip.py \
  --speaker raw/markov_podcast.mp4 --start 412 --end 441 \
  --broll broll/ \
  --style serif --look moody \
  --out out/markov_01.mp4
```

* `--start/--end` — the good bit, in seconds of the source. Pick 20–45 s.
* `--style` — `serif` (stoic), `caps` (lifelesson), `phrase` (calverne), `word` (1make).
* `--look` — `moody` (default), `bw`, `clean`.
* `--hook` — seconds on the face before the first b-roll (default 3.2).
* `--face-ratio` — share of screen time on the speaker (default 0.5).
* `--closer` — final seconds always on the face (default 2.5).
* `--no-tighten` — keep the pauses (default cuts dead air > 0.45 s).
* `--seed` — different number, different shot pattern and b-roll order.
* `--face-only` — no b-roll, pure punch-in talking head.
* `--handle @name` — small faded handle at the bottom (off by default).

Landscape podcast footage is reframed to 9:16 around the detected face.
A `<out>.plan.json` is written next to the video with the transcript and every
shot, so you can re-run with a different seed or style without re-transcribing.

## B-roll rules

Put clips in a folder; any aspect ratio, 2 s or longer. The best-performing
style is dark, slow, no people's faces, no text, no watermarks: cars in rain,
night cities, jets, watches, yachts, empty gyms, hotel corridors. Every clip is
cover-cropped to 9:16 with a slow push, so shoot/pick clips with the subject
roughly centred.
