# Day 0 Verifier Image

This image is the minimal verifier for `eval/tasks.example.json`. It contains
Python 3.12, pytest, and a small `uv` shim for the example command:

```bash
uv run --with pytest pytest -q
```

The live harness requires a complete digest-pinned image reference. A plain local
tag such as `fablized-sol-verifier:day0` is intentionally rejected.

## Build And Pin Locally

```bash
docker run -d --name fablized-registry -p 5050:5000 registry:2
docker build -t localhost:5050/fablized-sol-verifier:day0 eval/verifier
docker push localhost:5050/fablized-sol-verifier:day0
export VERIFICATION_IMAGE="$(
  docker image inspect localhost:5050/fablized-sol-verifier:day0 \
    --format '{{ index .RepoDigests 0 }}'
)"
docker pull "$VERIFICATION_IMAGE"
```

Then run the pilot:

```bash
uv run fablized-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/live \
  --run-id day0-live-pilot \
  --verification-image "$VERIFICATION_IMAGE"
```

Stop the local registry when you are done:

```bash
docker rm -f fablized-registry
```
