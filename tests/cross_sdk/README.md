# Cross-SDK round-trip

`AP-EVD/1.0` requires the Python and TypeScript SDKs to produce
byte-identical canonical output for the same input. This directory holds
the three-step round-trip harness that proves it:

1. **`py_emit.py`** — Python SDK canonicalizes the `corpus.json` inputs
   and writes `py_emit.json` (base64 canonical bytes + SHA-256 hex).
2. **`ts_roundtrip.mjs`** — TypeScript SDK reads the corpus, runs its own
   canonicalizers, asserts byte-equality with Python, and writes
   `ts_reemit.json`.
3. **`py_verify.py`** — Python verifies the two output files agree.

The closing edge is the architecture-level proof: if the Python SDK ships
an undetected canonicalisation change but the TypeScript SDK does not,
step 2 fails on hash mismatch; if both SDKs change in unison but the
on-disk artefact stops matching the verifier's expectations, step 3
catches it.

This corresponds to **Gap G1** in `docs/ci_testing_framework_20260518.md`
and is tier **T2** (pre-merge thorough). The CI driver lives in
`.github/workflows/cross-sdk-roundtrip.yml`. For local execution see
`scripts/test-cross-sdk-roundtrip.sh`.
