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

ARG FF_VERSION=master
RUN git clone https://github.com/facefusion/facefusion.git \
    && cd facefusion && git checkout ${FF_VERSION}

WORKDIR /app/facefusion
RUN python install.py cuda --skip-conda

# ⚠️ Do NOT bake the models in (no `force-download`): the full model set is several GB and pushes the
# image past RunPod's 30-minute BUILD timeout during layer export. FaceFusion downloads only the models it
# needs (swapper + enhancer + detectors) on the FIRST request; the worker then stays warm and reuses them.

RUN python -m pip install runpod
COPY handler.py /app/handler.py

WORKDIR /app
CMD ["python", "handler.py"]