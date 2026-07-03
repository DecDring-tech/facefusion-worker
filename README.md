# FaceFusion RunPod Serverless worker (AdSpark face-swap)

This is the GPU worker that face-swaps the chosen avatar onto your GRWM / Story Time base template
videos. AdSpark's pipeline splits each template into **half 1 / half 2** and calls this worker once per
half, so each chunk is swapped independently. Self-hosted on RunPod = best quality, pay-per-GPU-second,
**$0 when idle** (no monthly floor).

## Files
- `Dockerfile` — builds FaceFusion + the RunPod handler (GPU/CUDA).
- `handler.py` — takes `{ source_image_url, target_video_url }`, runs FaceFusion, returns the swapped mp4 as base64.

## Deploy (no local Docker needed — RunPod builds it)
1. **Create a GitHub repo** and push these three files to it (`Dockerfile`, `handler.py`, `README.md`).
2. Go to **runpod.io → Serverless → New Endpoint → Import Git Repository**, connect GitHub, and pick your repo.
3. Configure the endpoint:
   - **GPU:** 24 GB class (e.g. RTX 4090 / A5000) — FaceFusion + enhancer wants a real GPU.
   - **Container disk:** ~20 GB (models are baked in at build).
   - **Max workers:** 1–3 is plenty to start. **Idle timeout:** low (e.g. 5s) so it scales to zero.
   - Leave the CMD as-is (the Dockerfile already runs `handler.py`).
4. Click deploy and let RunPod **build the image** (first build is slow — it installs FaceFusion + downloads models).
5. When it's live, copy the **Endpoint ID** (shown on the endpoint page).
6. **runpod.io → Settings → API Keys →** create a key (starts with `rpa_`).

## Wire it into AdSpark
In your deployed app: **Admin → Settings → "Face Swap (GRWM / Story Time)"**:
- **RunPod API Key** → your `rpa_...` key
- **RunPod Endpoint ID** → the endpoint id

That's it — the pipeline auto-detects RunPod and routes GRWM/Story face-swaps through it.

## Testing the endpoint directly (optional)
```bash
curl -X POST https://api.runpod.ai/v2/<ENDPOINT_ID>/run \
  -H "Authorization: Bearer <RUNPOD_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"input":{"source_image_url":"https://.../face.jpg","target_video_url":"https://.../clip.mp4"}}'
# → { "id": "..." }, then poll:
curl https://api.runpod.ai/v2/<ENDPOINT_ID>/status/<id> -H "Authorization: Bearer <RUNPOD_API_KEY>"
```

## If the first build/run fails
- **Build fails at `install.py`** → note `onnxruntime` is a POSITIONAL arg (`python install.py cuda --skip-conda`),
  choices `default|cuda|rocm|openvino|migraphx`. If CUDA still fails, try a different base image tag.
- **Run fails with a CLI error** → your FaceFusion version changed the flags. Adjust the single `cmd`
  block in `handler.py` (it's clearly marked). Send the `stderr` from the AdSpark Debug panel and it's a quick fix.
- **`force-download` errors** → harmless (`|| true`); models just download on the first real request instead.
