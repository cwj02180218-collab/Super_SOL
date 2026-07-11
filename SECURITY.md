# Security Policy

## Supported version

Security fixes target the latest tagged release and `main`.

## Reporting a vulnerability

Use GitHub private vulnerability reporting at
`https://github.com/cuj0218/Super-SOL/security/advisories/new`.

Do not open a public issue containing API keys, environment files, raw live
workspaces, model output that may contain private data, or instructions for
bypassing the verifier/grader boundary. Revoke any credential that may have
been exposed before sharing a redacted reproduction.

## Trust boundary

The model-callable verifier and the out-of-band grader must remain different,
digest-pinned images. Both run without network access or the parent process
environment. The grader's tests and output must never be returned to the model.

Super SOL does not claim that arbitrary hosted tools are observable evidence.
Only registered local tools with typed results participate in the deterministic
evidence gate.
