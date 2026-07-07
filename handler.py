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
    fal_key = inp.get("fal_key")
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
