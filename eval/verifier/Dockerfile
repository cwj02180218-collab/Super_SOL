FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

RUN python -m pip install --no-cache-dir pytest==9.1.1

COPY uv-shim /usr/local/bin/uv

RUN chmod +x /usr/local/bin/uv && mkdir -p /workspace

WORKDIR /workspace
