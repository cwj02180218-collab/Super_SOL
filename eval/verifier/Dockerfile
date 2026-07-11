FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df

RUN python -m pip install --no-cache-dir pytest==9.1.1

COPY uv-shim /usr/local/bin/uv

RUN chmod +x /usr/local/bin/uv && mkdir -p /workspace

WORKDIR /workspace
