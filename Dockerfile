# FaceFusion video face-swap — RunPod Serverless worker (GPU).

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    FACEFUSION_DIR=/app/facefusion

# FaceFusion's current code imports typing.NotRequired, which ONLY exists in Python 3.11+. Ubuntu 22.04
# ships Python 3.10 → "cannot import name 'NotRequired'". Install Python 3.11 from deadsnakes and point
# `python` at it (leave system python3=3.10 so apt keeps working). ffmpeg is a FaceFusion dep.
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common ca-certificates curl git ffmpeg \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PINNED release (master drifts and can silently change CLI/behavior; the stabilizer patch below is
# written against exactly this version and refuses to build against anything it doesn't recognise).
ARG FF_VERSION=3.7.1
RUN git clone https://github.com/facefusion/facefusion.git \
    && cd facefusion && git checkout ${FF_VERSION}

# TEMPORAL LANDMARK STABILIZER — FaceFusion has NO temporal smoothing, so partial face occlusion
# (hands/products in GRWM footage) makes the per-frame warp landmarks oscillate → "jelly" face.
# This patches an EMA stabilizer into the swap warp (see patch_stabilizer.py; build FAILS if the
# source doesn't match, never builds unpatched). Requires --execution-thread-count 1 (handler sets it).
COPY patch_stabilizer.py /app/patch_stabilizer.py
RUN python /app/patch_stabilizer.py /app/facefusion/facefusion/processors/modules/face_swapper/core.py

WORKDIR /app/facefusion
RUN python install.py cuda --skip-conda

# ⚠️ Do NOT bake the models in (no `force-download`): the full model set is several GB and pushes the
# image past RunPod's 30-minute BUILD timeout during layer export. FaceFusion downloads only the models it
# needs (swapper + enhancer + detectors) on the FIRST request; the worker then stays warm and reuses them.

RUN python -m pip install runpod
COPY handler.py /app/handler.py

WORKDIR /app
CMD ["python", "handler.py"]