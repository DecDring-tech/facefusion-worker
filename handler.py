"""
RunPod Serverless handler — FaceFusion video face-swap.

Input  (job["input"]):
  { "source_image_url": "<url of the avatar face image>",
    "target_video_url": "<url of the template video chunk>" }

Output:
  { "video_base64": "<base64 mp4>" }                         on success
  { "error": "...", "attempts": [ {cmd, returncode, stderr} ] }  on failure

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


def _run(src: str, tgt: str, out: str, processors: list, extra: list):
    """Run one FaceFusion headless pass. Returns (ok, cmd, proc)."""
    # Current FaceFusion CLI uses LONG argument names (the short -s/-t/-o aliases were dropped in the
    # CLI migration; passing them makes it exit without writing anything = "produced no output").
    cmd = [
        "python", "facefusion.py", "headless-run",
        "--source-paths", src,
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
    src_url = inp.get("source_image_url")
    tgt_url = inp.get("target_video_url")
    if not src_url or not tgt_url:
        return {"error": "source_image_url and target_video_url are required"}

    work = tempfile.mkdtemp(prefix="ff-")
    src = os.path.join(work, "source.jpg")
    tgt = os.path.join(work, "target.mp4")
    out = os.path.join(work, "output.mp4")

    def _record(cmd, proc):
        return {"cmd": " ".join(cmd), "returncode": proc.returncode, "stderr": (proc.stderr or "")[-1500:], "stdout": (proc.stdout or "")[-600:]}

    try:
        _download(src_url, src)
        _download(tgt_url, tgt)

        attempts = []
        # Pass 1 — best quality: swapper + enhancer, a lower detector score so a face is found more
        # reliably in a busy template frame.
        ok, cmd, proc = _run(src, tgt, out, ["face_swapper", "face_enhancer"], ["--face-detector-score", "0.3"])
        attempts.append(_record(cmd, proc))

        # Pass 2 — leanest, most-compatible fallback: swapper only, no extra flags. Catches a missing
        # face_enhancer model or an unknown flag from pass 1.
        if not ok:
            try:
                os.remove(out)
            except OSError:
                pass
            ok, cmd, proc = _run(src, tgt, out, ["face_swapper"], [])
            attempts.append(_record(cmd, proc))

        if not ok:
            return {"error": "FaceFusion produced no output", "attempts": attempts}

        with open(out, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"video_base64": b64}

    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(work, ignore_errors=True)


runpod.serverless.start({"handler": handler})