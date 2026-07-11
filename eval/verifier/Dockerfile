FROM python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df

COPY requirements.lock /tmp/requirements.lock

RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

COPY uv-shim /usr/local/bin/uv

RUN chmod +x /usr/local/bin/uv && mkdir -p /workspace

WORKDIR /workspace
