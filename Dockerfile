# FaceFusion video face-swap — RunPod Serverless worker (GPU).
# Builds a container with FaceFusion + a RunPod handler. RunPod can build this straight from your
# GitHub repo (Serverless → New Endpoint → Import Git Repository), so you don't need Docker locally.

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    FACEFUSION_DIR=/app/facefusion

# System deps: python, ffmpeg (FaceFusion needs it), git, curl.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git ffmpeg curl ca-certificates \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone FaceFusion. Pin a tag for reproducible builds (change FF_VERSION to move versions).
ARG FF_VERSION=master
RUN git clone https://github.com/facefusion/facefusion.git \
    && cd facefusion && git checkout ${FF_VERSION}

# Install FaceFusion for CUDA. If this fails on your GPU, try --onnxruntime cuda-12.4 or a matching base image.
WORKDIR /app/facefusion
RUN python install.py --onnxruntime cuda --skip-conda

# Pre-download the models so the first request isn't a huge cold download (best-effort).
RUN python facefusion.py force-download || true

# RunPod serverless SDK + our handler.
RUN pip install runpod
COPY handler.py /app/handler.py

WORKDIR /app
CMD ["python", "handler.py"]
