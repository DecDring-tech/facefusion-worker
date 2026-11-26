# Autopilot playbook (for Claude)

**Read `HITS.md` first. Every batch is based on the hits listed there.**

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
  be slid in as if they're his, but **never as payoff shot 1 or 2**: the drop shot and the next one must show Marko's
  face (shot 3 onward may be faceless; user changed this from 3 to 2 for marko_003). Every source in `sources_marko2.json` has a `face` flag; check the first 2 entries of the expanded source sequence are face sources before
  rendering, then check a frame sheet (start and end of shots 1–2). Don't use faceless clips where the driver's arms or skin
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

## Sounds and captions (user feedback, batch tjr_004 / marko_005)

- **Sounds:** use the sounds from the user's own @tjrv001 posts: S1–S9 plus `A_flexx`. Those are the sounds the user likes. The
  extra library sounds (M_/N_) were disliked in tjr_003/marko_004; only use them if the user asks. Before each batch,
  re-list @tjrv001's posts for any new sound they've started using (tikwm per post gives `music_info`).
- **Captions:** keep them simple and close to the user's best posts. Caption 1 is "Where's your <thing you can see in the
  clip> TJR/Marko? 😂", or the 3.6M line "What colours your Ferari …? 😂". Caption 2 is one of "Wrong tax bracket lil bro",
  "Different tax bracket lil bro", "Not even close lil bro", "It's red lil bro" or "Where's your Ferrari lil bro?". No
  invented punchlines ("Mine's Swedish", "1.6 tonnes", "Who does your nails" were disliked). Post captions follow
  "Logan Paul gets brutally car Mogged by …", "Next time Logan 🥱", "We're not the same Logan", with hashtags
  `#tjr #mogged #loganpaul #jakepaul`.

## Proven winner (Nov 2026): marko_005 #10 "chains", 31K views in 10 h, 9.3 s average watch, 44.5% full watches

The formula: a Jake close-up selfie showing something he's wearing or holding; "Where's your <that thing> Marko? 😂";
"Wrong tax bracket lil bro"; USE HEADSET sound (S7, 4 × 1.45 s shots, 9.37 s total); Marko by the Ferrari and Urus, then the
white Urus. marko_006 is 10 copies of it. When a video takes off, copy its sound, shot pattern and caption style exactly and
only change the opener.

## Opener rules from the chains hit (apply to every Marko and TJR batch)

Compared with the two flops on @markovclipping (jet ski, 2.7K; championship belt, 2.8K):
1. Frame 1 is a face close-up looking into the lens and filling the frame, selfie style. No wide shots, action shots or
   small faces. It's also the cover image.
2. The flex item is on or right next to that face in frame 1 (chain, watch, glasses, girl, medal), and caption 1 names it,
   so the joke reads in under a second.
3. Caption 1 is five words or fewer plus "Marko? 😂". Caption 2 is "Wrong tax bracket lil bro".
4. Payoff: Marko's face on shots 1 and 2, at night by the Ferrari and Urus, so the day/night contrast hits on the drop.
5. Long, slow shots (USE HEADSET, 4 × 1.45 s, 9.4 s) so the whole video is easy to finish and it loops.
6. Post caption labels Jake as Logan, for the comments.

## Second Marko hit (27 Nov 2026): marko_007 #2 "gold chain", 12.3K and climbing ~8K/hour

Scoreboard on @markovclipping at that point: chains 61.2K, gold chain 12.3K (rising), belt 3.8K, jet ski 3.3K,
"Where's your Ferrari" (tattoos opener) 740 (too new to judge).
Both hits share: Jake's face filling the frame and looking into the lens, a chain on his neck named in caption 1,
USE HEADSET sound, "Wrong tax bracket lil bro". Their Marko shots differ (fer1f lead vs fer2f lead), so the payoff order
is not what matters. Not yet separated: is it the chain, or any face-to-lens close-up? Jewellery close-ups (chains,
watch, rings, grillz, earrings) are the safest next openers; non-jewellery face-to-lens openers are the test.
