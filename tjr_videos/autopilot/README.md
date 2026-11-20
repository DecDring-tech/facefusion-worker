# Autopilot: make, post and track batches for the TJR and Marko accounts

You say the word, Claude does the rest:

| You say | What happens |
|---|---|
| **make a TJR batch** | 10 new TJR videos in the locked-in style, each with a post caption and hashtags |
| **make a Marko batch** | 10 new Marko videos in the TJR style |
| **post on TJR accounts** / **post on Marko accounts** | the newest batch goes out, video 1 to account 1, video 2 to account 2 … ~7 minutes apart, caption and hashtags filled in, the video's own audio as the sound |
| **stats** | fresh numbers for every account and every post we made |
| **how do we improve** | ideas based on what the numbers say |

## One-time setup (you)

1. Sign up at [upload-post.com](https://www.upload-post.com/pricing/). **Professional** covers 25 accounts (20 needed).
   It's the plan that includes TikTok with enough profiles.
2. Create 20 profiles named exactly `tjr01` … `tjr10` and `marko01` … `marko10`. In each one, connect the matching TikTok
   account. You log in to each TikTok once; Claude never sees your passwords.
3. Copy your Upload-Post API key. Next time you're in this chat, say "connect upload-post": a secure form pops up and the
   key goes into the environment's secrets, never into the chat or the repo.
4. Send Claude the 20 handles in order (TJR 1–10, Marko 1–10). They go into `accounts.json`.

Claude then runs `post.py check` to confirm every account is connected, and sets up a daily stats check.

## What's in here

- `engine/`: the video builder (beat grid, sounds, TJR and Marko footage, caption renderer, checks).
- `batches/`: one folder per batch with the 10 videos and `manifest.json` (which video goes to which account, plus captions).
  Ready now: `tjr_001` (round 12, the Jake-as-Logan rage-bait set) and `marko_001` (the 10 Marko videos).
- `post.py`: posts a batch through Upload-Post. Dry run by default.
- `stats.py`: snapshots every account's public numbers, plus watch time, finish rate and retention per post from
  Upload-Post, and writes `data/report.md`.
- `PLAYBOOK.md`: the full rulebook Claude follows for each command.

## Things to know

- TikTok and Upload-Post allow 15 posts per account per day. A batch is one post per account, so that's plenty.
- Every account gets a different video. Identical uploads across accounts get suppressed.
- Watch time and retention only exist for posts made through `post.py`. Posts made by hand only get the public numbers.
