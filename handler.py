"""
RunPod Serverless handler — FaceFusion video face-swap.

Input  (job["input"]):
  { "source_image_url": "<url of the avatar face image>",
    "target_video_url": "<url of the template video chunk>" }

Output:
  { "video_base64": "<base64 mp4>" }        on success
  { "error": "...", "stderr": "..." }        on failure

The AdSpark pipeline splits the template into HALF 1 / HALF 2 and calls this once per half,
so each request face-swaps one chunk.
"""

import os
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


def handler(job):
    inp = job.get("input") or {}
    src_url = inp.get("source_image_url")
    tgt_url = inp.get("target_video_url")
    if not src_url or not tgt_url:
        return {"error": "source_image_url and target_video_url are required"}

    work = tempfile.mkdtemp(prefix="ff-")
    src = os.path.join(work, "source.jpg")
    tgt = os.path.join(work, "target.mp4")
    out = os.path.join(work, "output.mp4")

    try:
        _download(src_url, src)
        _download(tgt_url, tgt)

        # ── FaceFusion 3.x headless CLI ──────────────────────────────────────────────
        # If your pinned FaceFusion version uses different flags, THIS is the only block to adjust.
        # face_enhancer is included for best quality / occlusion handling (drop it to go faster).
        cmd = [
            "python", "facefusion.py", "headless-run",
            "-s", src,
            "-t", tgt,
            "-o", out,
            "--processors", "face_swapper", "face_enhancer",
            "--execution-providers", "cuda",
        ]
        proc = subprocess.run(cmd, cwd=FACEFUSION_DIR, capture_output=True, text=True, timeout=1800)

        if not os.path.exists(out) or os.path.getsize(out) == 0:
            return {
                "error": "FaceFusion produced no output",
                "returncode": proc.returncode,
                "stderr": (proc.stderr or "")[-2000:],
                "stdout": (proc.stdout or "")[-1000:],
            }

        with open(out, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"video_base64": b64}

    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(work, ignore_errors=True)


runpod.serverless.start({"handler": handler})
