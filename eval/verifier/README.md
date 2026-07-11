# Super SOL verifier and grader images

The live harness uses two different images:

- the model-callable verifier contains Python, pytest, and a small `uv` shim for visible checks;
- the out-of-band grader additionally contains hidden checks that run only after the model turn.

Both Dockerfiles pin the reviewed `python:3.12-alpine` multi-platform digest and install the complete
pytest dependency graph with `--require-hashes`. The live harness rejects plain tags and requires
complete `name@sha256:...` references.

## Release supply-chain audit

Run the repository audit after any Dockerfile, base digest, or grader dependency change:

```bash
uv run super-sol-container-audit \
  --repo-root . \
  --sbom-dir security/sbom
```

The command validates the exact base policy, builds both images, writes SPDX 2.3 SBOMs, runs both
Docker Scout release gates, and returns failure if either gate fails. A missing Docker engine or
Scout plugin is also a failure. The checked-in SBOMs are release evidence for the reviewed image,
not a permanent claim about future images.

## Build immutable local-registry references

```bash
docker run -d --name super-sol-registry -p 5050:5000 registry:2
docker tag super-sol-verifier:audit localhost:5050/super-sol-verifier:day3-visible
docker push localhost:5050/super-sol-verifier:day3-visible
export VERIFICATION_IMAGE="$(
  docker image inspect localhost:5050/super-sol-verifier:day3-visible \
    --format '{{ index .RepoDigests 0 }}'
)"

docker tag super-sol-grader:audit localhost:5050/super-sol-grader:day3
docker push localhost:5050/super-sol-grader:day3
export GRADER_IMAGE="$(
  docker image inspect localhost:5050/super-sol-grader:day3 \
    --format '{{ index .RepoDigests 0 }}'
)"

docker pull "$VERIFICATION_IMAGE"
docker pull "$GRADER_IMAGE"
```

This tags and pushes the exact images already audited instead of rebuilding them. Confirm that the
two variables differ and both contain `@sha256:`. Keep the API key only in the local shell; do not
place it in a file, chat, image, command log, or repository.

## Explicit live pilot

The live command requires all of the following: local API key, two different locally available
digest-pinned images, and the explicit `--confirm-billable` flag. It never runs from routine CI or
the Codex plugin.

```bash
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/live \
  --run-id day3-live \
  --arm-design crossover \
  --product-effort medium \
  --reference-effort medium \
  --verification-image "$VERIFICATION_IMAGE" \
  --grader-image "$GRADER_IMAGE" \
  --confirm-billable
```

The public hidden checks validate harness plumbing, not benchmark secrecy. Use an unpublished,
versioned grader build context before making model or Fable-parity claims.

Stop the local registry when finished:

```bash
docker rm -f super-sol-registry
```
