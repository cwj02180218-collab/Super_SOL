# Day 3 Verifier Image

The pilot uses two images. The verifier image contains Python, pytest, and a
small `uv` shim for model-callable visible tests. The grader image additionally
contains out-of-band checks that run only after the model turn.

```bash
uv run --with pytest pytest -q -p no:cacheprovider /workspace
```

The live harness requires a complete digest-pinned image reference. A plain local
tag such as `fablized-sol-verifier:day0` is intentionally rejected.

## Build And Pin Locally

```bash
docker run -d --name fablized-registry -p 5050:5000 registry:2
docker build -f eval/verifier/Dockerfile \
  -t localhost:5050/fablized-sol-verifier:day3-visible eval/verifier
docker push localhost:5050/fablized-sol-verifier:day3-visible
export VERIFICATION_IMAGE="$(
  docker image inspect localhost:5050/fablized-sol-verifier:day3-visible \
    --format '{{ index .RepoDigests 0 }}'
)"
docker build -f eval/verifier/Dockerfile.grader \
  -t localhost:5050/fablized-sol-grader:day3 eval/verifier
docker push localhost:5050/fablized-sol-grader:day3
export GRADER_IMAGE="$(
  docker image inspect localhost:5050/fablized-sol-grader:day3 \
    --format '{{ index .RepoDigests 0 }}'
)"
docker pull "$VERIFICATION_IMAGE"
docker pull "$GRADER_IMAGE"
```

Then run the pilot:

```bash
uv run fablized-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/live \
  --run-id day3-live \
  --arm-design crossover \
  --verification-image "$VERIFICATION_IMAGE" \
  --grader-image "$GRADER_IMAGE"
```

The published grader checks validate the harness plumbing, not benchmark
secrecy. Replace them with an unpublished grader build context before using
results for model or Fable-parity claims.

Stop the local registry when you are done:

```bash
docker rm -f fablized-registry
```
