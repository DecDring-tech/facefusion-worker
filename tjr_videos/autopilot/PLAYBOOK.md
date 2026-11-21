# Autopilot playbook (for Claude)

The user runs the TJR and Marko accounts by saying short commands. This is what each one means. Work from
`tjr_videos/autopilot/` on branch `claude/tjr-video-series-6y4umc`. Commit and push after every batch, post and stats run.

## Commands

| User says | Do |
|---|---|
| "make a TJR batch" | Build 10 new TJR videos (below), make `batches/tjr_NNN/manifest.json`, send the videos with their captions, commit. |
| "make a Marko batch" | Same for Marko in the **rich** TJR style (marko_002 and later): bait, then drop, then Marko with his supercars (red Ferrari, yellow Urus, convertible), "Wrong tax bracket lil bro" family. Sources: `sources_marko2.json`. The boxing version (`sources_marko.json`, "Wrong weight class") only when asked. |
| "make a Marko batch in the latest style" | Marko style 2. **Not defined yet**: it's from a chat Claude can't see. Ask the user for an example post, then add it here. |
| "post on TJR accounts" / "post on Marko accounts" | `python3 post.py batches/<latest unposted batch> <tjr\|marko>` (dry run), check the mapping, then `--live --stagger 7`. Then `python3 post.py status` after ~10 min. Report what posted where. |
| "stats" / "how are we doing" | `python3 stats.py`, commit `data/`, summarise `data/report.md`: best and worst posts, what's working, and the 24 h change. |
| "how do we improve" | Run stats first, then answer from the data (see "Improving" below), and propose the next batch's changes. |

## Making a batch (both series)

The rules the user has set over 12 rounds. Every one still applies:

- **Opener (bait):** someone else's flex, one continuous native-res take, no burned-in captions, no blur or inpainting,
  3–4 s long. Never reuse an opener already used for that series (check old `batches/*/manifest.json` and `specs/`).
  Caption: `Where's your <thing>\n<TJR|Marko>? 😂`. Titles must make sense.
- **The drop lands exactly on the switch.** The video never starts on the drop: loud intros get an offset or fade
  (already set in `plan8.json`).
- **Payoff, 5–8 s:** cold, long phone recordings walked in order, one cut on every beat, about 3 windows per recording, then
  the next recording. No tiny clips, no flash frames, nothing faster than about 0.9 s. TJR: `sources9.json`, never the head-on
  tree reveal. Marko: `sources_marko.json`.
- **Marko face rule:** Marko must look richer than everyone. Faceless supercar clips (POV at the wheel, Lambo interiors) can
  be slid in as if they're his, but **never as payoff shot 1, 2 or 3**: the drop shot and the next two must show Marko's
  face. Every source in `sources_marko2.json` has a `face` flag; check `[s for s in seq[:3]]` are all face sources before
  rendering, then check a frame sheet (start and end of shots 1–3). Don't use faceless clips where the driver's arms or skin
  give it away.
- **Payoff captions:** TJR "Wrong tax bracket lil bro" family. Marko "Wrong weight class lil bro" family. Rage-bait variant
  (the 3.5M recipe): Jake Paul opener labelled "Logan Paul" in the post caption, plus a subtly wrong but plausible detail
  on screen (wrong car, misspelling, wrong record or weight class). Set `rage_bait: true` on those.
- **Sound:** the audio is baked into the video and posts as the video's own sound. Pick from the 29 registered sounds in
  `plan8.json`, spread across the batch, and favour what `data/report.md` says is winning.
- **Every spec** carries `post_caption`, `hashtags`, `bait_person` and `rage_bait`, so posting and analytics work.

Steps (from `engine/`):
```
python3 scripts/ttdl.py <post_id> bait_dl/<id>.mp4          # get opener footage (tikwm, no watermark); cut a clean single take into r8clean/<name>.mp4
SPECS=specs/<new>.json SRCS=sources9.json PLAN=plan8.json python3 scripts/build9.py out_<batch>      # Marko: SRCS=sources_marko.json PLAN=plan_marko.json
python3 scripts/verify8.py out_<batch>                     # every line must show stray_visual_cuts=[]; check a frame sheet by eye too
python3 scripts/manifest.py <tjr|marko> specs/<new>.json out_<batch> <tjr|marko>_NNN
```
Tools: tikwm per-post API works, and its `challenge/search` and `challenge/posts` work for hashtag feeds. yt-dlp
`--flat-playlist -J https://www.tiktok.com/@user` works for profiles. YouTube and cobalt are blocked. Audio from mp4:
extract with ffmpeg first (librosa can't read mp4). New sounds: `scripts/register2.py`.

## Posting

- Upload-Post API (audited TikTok app, so posts are public). The key lives in the environment's network secrets for
  `api.upload-post.com`. If `post.py check` returns 401, ask for it with `request_credential` (header Authorization,
  prefix ApiKey).
- `accounts.json` maps slot → TikTok handle and Upload-Post profile. Video N goes to slot N, one per account.
- Limit: 15 posts per account per day (Upload-Post). Don't post the same video to two accounts.

## Improving (what to look at)

- **Still watching at the switch** (retention at the drop second): low means the opener or its caption isn't hooking.
  Change the opener person or caption.
- **Finished %** and **avg watch** vs length: low means the payoff drags. Shorten it or use a sound with a harder drop.
- **Comments per 1K views:** the rage-bait signal. Compare rage-bait and straight posts.
- **Shares and saves per view:** relatability. Compare which openers and payoff lines get shared.
- Groups in "What's working" need 2+ posts each. Say when a sample is too small to trust.
- Then change one or two things per batch (sound, opener person, payoff line, length) so the next stats run shows what moved.
