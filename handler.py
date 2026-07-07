"""
RunPod Serverless handler — FaceFusion video face-swap.

Input  (job["input"]):
  { "source_image_url": "<url of the avatar face image>",
    "target_video_url": "<url of the template video chunk>",
    "fal_key": "<optional fal.ai API key — lets the worker upload the result to fal.storage>" }

Output:
  { "video_url": "<fal.storage url>" }                       on success (when fal_key is provided)
  { "video_base64": "<base64 mp4>" }                         fallback (small outputs / no fal_key)
  { "error": "...", "attempts": [ {cmd, returncode, stderr} ] }  on failure

⚠️ WHY the fal.storage upload matters: a full-length swapped video encoded as base64 EXCEEDS
RunPod's response payload cap — RunPod then drops the output and the job reads COMPLETED with an
EMPTY result. Returning a small {video_url} avoids that entirely.
"""

import os
import json
import base64
import shutil
import tempfile
import subprocess
import urllib.request

import runpod

FACEFUSION_DIR = os.environ.get("FACEFUSION_DIR", "/app/facefusion")


def _download(url: str, path: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "adspark-facefusion-worker"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(path, "wb") as f:
        shutil.copyfileobj(resp, f)


def _upload_to_fal(path: str, fal_key: str) -> str:
    """Upload the mp4 to fal.storage (same flow the official fal client uses) → public file URL."""
    body = json.dumps({"content_type": "video/mp4", "file_name": "swapped.mp4"}).encode()
    req = urllib.request.Request(
        "https://rest.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3",
        data=body, method="POST",
        headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json",
                 "User-Agent": "adspark-facefusion-worker"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        info = json.loads(resp.read().decode())
    upload_url, file_url = info["upload_url"], info["file_url"]
    with open(path, "rb") as f:
        data = f.read()
    put = urllib.request.Request(upload_url, data=data, method="PUT", headers={"Content-Type": "video/mp4"})
    with urllib.request.urlopen(put, timeout=900):
        pass
    return file_url


def _run(srcs: list, tgt: str, out: str, processors: list, extra: list):
    """Run one FaceFusion headless pass. Returns (ok, cmd, proc)."""
    # Current FaceFusion CLI uses LONG argument names (the short -s/-t/-o aliases were dropped in the
    # CLI migration; passing them makes it exit without writing anything = "produced no output").
    # --source-paths accepts MULTIPLE images of the same person — the identity embedding averages
    # across them, which measurably improves likeness accuracy vs a single photo.
    cmd = [
        "python", "facefusion.py", "headless-run",
        "--source-paths", *srcs,
        "--target-path", tgt,
        "--output-path", out,
        "--processors", *processors,
        "--execution-providers", "cuda",
        *extra,
    ]
    proc = subprocess.run(cmd, cwd=FACEFUSION_DIR, capture_output=True, text=True, timeout=1800)
    ok = os.path.exists(out) and os.path.getsize(out) > 0
    return ok, cmd, proc


def handler(job):
    inp = job.get("input") or {}
    # Multiple same-person source images (identity averaging) — falls back to the single legacy field.
    src_urls = inp.get("source_image_urls") or ([inp.get("source_image_url")] if inp.get("source_image_url") else [])
    src_urls = [u for u in src_urls if isinstance(u, str) and u.strip()][:4]
    tgt_url = inp.get("target_video_url")
    fal_key = inp.get("fal_key")
    if not src_urls or not tgt_url:
        return {"error": "source_image_url(s) and target_video_url are required"}

    work = tempfile.mkdtemp(prefix="ff-")
    tgt = os.path.join(work, "target.mp4")
    out = os.path.join(work, "output.mp4")

    def _record(cmd, proc):
        return {"cmd": " ".join(cmd), "returncode": proc.returncode, "stderr": (proc.stderr or "")[-1500:], "stdout": (proc.stdout or "")[-600:]}

    try:
        srcs = []
        for i, u in enumerate(src_urls):
            p = os.path.join(work, f"source{i}.jpg")
            _download(u, p)
            srcs.append(p)
        _download(tgt_url, tgt)

        attempts = []
        # Pass 1 — MAXIMUM quality (all flags verified against the FaceFusion CLI docs):
        #  • --face-mask-types box occlusion + xseg_2 occluder → hands/brushes IN FRONT of the face
        #    correctly COVER the swapped face (without this the swap paints OVER the hand — the
        #    "floating sticker face" that ruins GRWM content, where hands touch the face constantly).
        #  • --face-selector-mode one → exactly ONE face swapped per frame (no double/phantom faces).
        #  • --face-swapper-model hyperswap_1a_256 → 256px swapper vs the default inswapper_128 (the
        #    128px default IS the cheap-filter look on 1080p video).
        #  • --face-swapper-pixel-boost 512x512 → the swap region is processed at 512px and scaled,
        #    a major sharpness/fidelity boost.
        #  • --face-enhancer-blend 40 → the enhancer re-paints "perfect clean skin" every frame, which is
        #    what ERASES cream/makeup residue she just dabbed on and adds the smoothed-mask look. 40 keeps
        #    the identity sharpening but preserves the template's real on-face state (residue, texture).
        #  • --output-video-quality 85 → high quality but COMPRESSED (95 was near-lossless and produced
        #    a 158MB video that exceeded fal's upload cap → HTTP 413; 85 is visually identical for
        #    phone-style UGC at roughly a third of the size).
        #  • detector score stays at the DEFAULT (a lowered 0.3 made FaceFusion swap junk detections).
        #  • --face-occluder-model many → ENSEMBLE of all xseg occluder models: strongest possible
        #    segmentation of hands AND held OBJECTS in front of the face (single xseg models are
        #    trained mostly on hands — products held up to the camera segment noticeably better
        #    with the ensemble). Slower, worth it.
        #  • --face-landmarker-model many → ensemble landmarks: steadier face alignment while the
        #    face is PARTIALLY covered (the patting/applying moments).
        #  • --face-mask-types + REGION → the parser-based region mask restricts the swap to the ACTUAL
        #    parsed face parts (skin/brows/eyes/nose/mouth) instead of the whole bounding box — this is
        #    what CLAMPS the swap to her face: no spill onto hair/background/held objects, no "loose
        #    mask / tiktok filter" edge floating past the jawline.
        #  • --face-mask-blur 0.45 (default 0.3) → softer blend right at the mask edge so the jawline
        #    boundary reads as skin, not a cutout.
        ok, cmd, proc = _run(srcs, tgt, out, ["face_swapper", "face_enhancer"], [
            "--face-mask-types", "box", "occlusion", "region",
            # FULL-face region list pinned explicitly (it's the default, but the worker builds FF from
            # master where defaults can drift): the parser re-computes these PER FRAME, so a part covered
            # by a hand/product simply doesn't parse in those frames → the swap skips it until it's
            # visible again. Fully adaptive, whole face, nothing static.
            "--face-mask-regions", "skin", "left-eyebrow", "right-eyebrow", "left-eye", "right-eye", "glasses", "nose", "mouth", "upper-lip", "lower-lip",
            "--face-mask-blur", "0.45",
            "--face-occluder-model", "many",
            "--face-landmarker-model", "many",
            "--face-selector-mode", "one",
            "--face-swapper-model", "hyperswap_1a_256",
            "--face-swapper-pixel-boost", "512x512",
            "--face-enhancer-blend", "40",
            "--output-video-quality", "85",
        ])
        attempts.append(_record(cmd, proc))

        # Pass 2 — leanest, most-compatible fallback: swapper only, no extra flags. Catches a missing
        # model download or an unknown flag from pass 1 (FaceFusion master can drift).
        if not ok:
            try:
                os.remove(out)
            except OSError:
                pass
            ok, cmd, proc = _run(srcs, tgt, out, ["face_swapper"], [])
            attempts.append(_record(cmd, proc))

        if not ok:
            return {"error": "FaceFusion produced no output", "attempts": attempts}

        # Preferred: upload to fal.storage, return a tiny {video_url} (immune to RunPod's payload cap).
        upload_error = None
        if fal_key:
            try:
                return {"video_url": _upload_to_fal(out, fal_key)}
            except Exception as e:  # noqa: BLE001
                upload_error = f"{type(e).__name__}: {e}"

        # Fallback: base64. ⚠️ Only safe for SMALL outputs — a big video will blow RunPod's response
        # cap and come back as an EMPTY completed job; error out with the real reason instead.
        size = os.path.getsize(out)
        if size > 15 * 1024 * 1024:
            return {"error": f"Output video is {size // (1024 * 1024)}MB — too large to return as base64 (RunPod payload cap). Provide fal_key in the job input so the worker can upload it. Upload error: {upload_error or 'fal_key not provided'}"}
        with open(out, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        resp = {"video_base64": b64}
        if upload_error:
            resp["upload_error"] = upload_error
        return resp

    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(work, ignore_errors=True)


runpod.serverless.start({"handler": handler})
