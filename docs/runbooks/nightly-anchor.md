<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Runbook — nightly-anchor failure

> When the `nightly-anchor` workflow opens a `[gate-failure]` issue,
> this runbook is the maintainer's diagnostic checklist. Target
> acknowledgment time: **48 hours**, per [ATTESTATION_GATES.md A5](../architecture/ATTESTATION_GATES.md).

## What the workflow does

[`.github/workflows/nightly-anchor.yml`](../../.github/workflows/nightly-anchor.yml)
runs daily at 00:30 UTC and:

1. Submits a real RFC-3161 `TimestampRequest` to FreeTSA
   (`https://freetsa.org/tsr`).
2. Downloads FreeTSA's published CA cert at
   `https://freetsa.org/files/cacert.pem`.
3. Calls `verify_chain_with_anchors(chain, [anchor], trust_roots_der=[root])`
   and asserts `cert_status == "VALID"`.

When the live verification path fails closed, the report surfaces
`cert_status == "QUARANTINED"` and `ok == false`. That state is
deliberately non-claim-valid; only `VALID` is treated as a successful
live anchor.

The workflow has two distinct failure exit codes:

| Exit | Meaning | Workflow status | Issue opened? |
|------|---------|-----------------|---------------|
| 0 | Success | green | no |
| 78 | TSA unavailable (timeout / 5xx / network) | neutral | **no** (per ADR-0003 § 4) |
| 1 | Anything else (signature failure, chain failure, malformed response) | red | yes (P0 + `gate-failure` + `claim-safety` labels) |

ADR-0003 § 4 explicitly accepts TSA unavailability as a known outcome:
anchoring is off the substrate's critical path. The neutral exit is the
discipline that keeps "TSA flake" from polluting the alert backlog.

## Triage

### Step 1 — Read the workflow log

The Python script in the workflow prints a `Verification report:` JSON
block immediately before any failure. The block's
`anchor_results[].cert_status` and `anchor_results[].reason` fields
tell you exactly where the chain broke.

Common diagnoses:

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `TSA refused request: PKIStatus=N` (N != 0/1) | FreeTSA rejecting our request shape | Reproduce locally with `attestplane.anchoring.FreeTSAProvider`; check headers, request DER round-trip |
| `signature does not verify against leaf cert` | FreeTSA rotated their leaf cert; our parser missed the new one | Check `parsed.leafCertDer` matches a cert in FreeTSA's published chain |
| `leaf cert issuer DN does not match any configured trust root` | FreeTSA rotated their root; our cached `cacert.pem` is stale | Re-download `https://freetsa.org/files/cacert.pem`, verify out-of-band, update the workflow's pin if we add one |
| `cert_status=QUARANTINED` | The live TSA response was parseable but failed local RFC-3161 / trust-chain verification | Treat as fail-closed. The anchor is not claim-valid; inspect `anchor_results[].reason` for the specific verifier failure. |
| `verification_time exceeds leaf cert not_after` | FreeTSA leaf cert expired between issuance and our verification | Should be impossible (TSA always returns currently-valid certs); investigate as a substrate bug |
| `message_imprint does not match expected digest` | The TSA response didn't echo our digest correctly, or there's a substrate-side hash drift | Diff the chain's `event_hash` against what was sent |

### Step 2 — Decide: TSA-side or substrate-side?

**TSA-side** (acceptable, no PR needed):

- FreeTSA's HTTP endpoint is down or returning 5xx → wait, retry tomorrow.
- FreeTSA rotated their cert and didn't publish the new root in time
  → re-fetch and resume; document in the issue.
- > 7 consecutive days of failure on FreeTSA → evaluate switching the
  nightly to `DigiCertProvider` (the other built-in production
  provider) per ADR-0003 § 2's plurality recommendation.

**Substrate-side** (PR required):

- The parser rejects a token that other clients accept → open a fix PR
  in `sdk/python/src/attestplane/anchoring/rfc3161.py`.
- The verifier rejects a valid chain → fix in
  `sdk/python/src/attestplane/anchoring/verifier.py`.
- The HTTP transport drops headers or mishandles a redirect → fix in
  `sdk/python/src/attestplane/anchoring/http.py`.

### Step 3 — Verify the fix locally

Before merging, reproduce the failure locally:

```bash
cd sdk/python
.venv/bin/python -m pip install -e ".[anchor]"

# Re-run the nightly script with verbose output:
.venv/bin/python <<'PY'
from datetime import UTC, datetime
from hashlib import sha256
import urllib.request

from attestplane.anchoring import (
    FreeTSAProvider, TimestampRequest, UrllibHttpTransport,
    verify_chain_with_anchors,
)
from attestplane.hashchain import chain_extend, genesis_head
from attestplane.types import EventDraft

# Download FreeTSA root.
root_pem = urllib.request.urlopen(
    "https://freetsa.org/files/cacert.pem", timeout=30
).read()
import subprocess
root_der = subprocess.check_output(
    ["openssl", "x509", "-outform", "der"],
    input=root_pem,
)

# Submit live request.
now = datetime.now(UTC).replace(microsecond=0)
ev = chain_extend(
    genesis_head(),
    EventDraft(event_type="eval_event", actor="local://test"),
    now=now,
    event_id="00000000-0000-7000-8000-000000000001",
)
provider = FreeTSAProvider(
    transport=UrllibHttpTransport(),
    trust_roots_der=[root_der],
    ocsp_responses_der=[b"placeholder"],
)
anchor = provider.request_timestamp(
    TimestampRequest(digest=ev.event_hash),
    anchored_seq=0, now=now,
)
result = verify_chain_with_anchors(
    [ev], [anchor],
    trust_roots_der=[root_der],
    verification_time=now,
    verify_ocsp=False,
)
print(result)
PY
```

If it fails the same way, you've reproduced the bug. Fix, write a
regression test (the testing-side fixture often goes in
`tests/anchoring/test_rfc3161.py` or `test_http.py`), and verify
green before merging.

### Step 4 — Close the issue

When the fix lands and the next nightly run is green, close the
`[gate-failure]` issue with a comment summarising:

- Root cause (one paragraph)
- Fix commit SHA
- Next 3 nightly run links (must all be green)

The 3-consecutive-green requirement is from ATTESTATION_GATES.md A5.
Don't tag a new release until all 3 are confirmed.

## Operational notes

- **The workflow never blocks PRs.** Pre-merge A5 enforcement uses the
  frozen `anchor_vectors.json` (RecordedHttpTransport replay path).
  The nightly is the live-endpoint smoke test, not a hard gate.
- **OCSP is not exercised by this workflow.** FreeTSA doesn't publish
  a fully-RFC-6960 OCSP responder we can rely on. The Python verifier
  is invoked with `verify_ocsp=False`. When DigiCert (which does
  publish OCSP) is added, a separate `nightly-anchor-digicert` job
  will exercise the OCSP path.
- **The workflow fetches FreeTSA's CA cert from FreeTSA's own server**
  every run. This is fine for nightly smoke testing — if FreeTSA's
  domain is compromised, the next pre-merge run still uses the frozen
  `anchor_vectors.json` test_tsa_root_cert which is from the in-tree
  `TestTSAAuthority`, not FreeTSA. The substrate's integrity does not
  depend on this workflow.
- **Concurrency**: the job is `cancel-in-progress: false`. Two
  overlapping runs (e.g., from `workflow_dispatch` interrupting the
  schedule) are allowed because they exercise the same code path
  independently.

## Cross-references

- [ATTESTATION_GATES.md § A5](../architecture/ATTESTATION_GATES.md)
- [ADR-0003 § 4 — Anchoring is never on the `append()` critical path](../adr/0003-tsa-rfc-3161-anchoring.md)
- [ADR-0003 § 6 — CAdES-A long-term validation](../adr/0003-tsa-rfc-3161-anchoring.md)
- [`sdk/python/src/attestplane/anchoring/http.py`](../../sdk/python/src/attestplane/anchoring/http.py) — `FreeTSAProvider` source
- [`docs/policy/claims_policy.md`](../policy/claims_policy.md) — claim-safety triad
