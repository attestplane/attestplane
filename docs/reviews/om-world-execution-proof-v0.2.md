<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# Review Checklist — om-world `execution-proof` spec v0.2

Internal review preparation. This document is consulted by the attestplane
maintainer when the `omworldprotocol/om-world` v0.2 candidate diff lands. It
is not a self-attestation about om-world's spec quality, nor a public
position on om-world.

## 1. Status snapshot

- **Reviewer role accepted:** attestplane issue
  [#7 comment](https://github.com/attestplane/attestplane/issues/7#issuecomment-4501108977),
  2026-05-20.
- **om-world freeze target:** 2026-08-01 (om-world-side fact).
- **om-world candidate diff window:** ~2026-07-25 (om-world-side fact).
- **Baseline against which v0.2 diff is read:** `omworldprotocol/om-world`
  commit
  [`61979b1`](https://github.com/omworldprotocol/om-world/commit/61979b1),
  the commit that adopted the three converged primitives described in §3
  below.
- **Attestplane-side anchor date:** v1.0 GA target 2026-08-15. No other
  attestplane-side date is anchored on by this review.
- **Document class:** internal review preparation. Not a self-attestation
  about om-world's spec. Not a public release.

## 2. Scope of attestplane's Reviewer role

Bounded by om-world's GENESIS-BUILDERS policy as cited in the
[v0.2 Reviewer offer](https://github.com/attestplane/attestplane/issues/7#issuecomment-4486794312)
and accepted in attestplane's
[issue #7 reply](https://github.com/attestplane/attestplane/issues/7#issuecomment-4501108977):

- Public attribution only — no token, no allocation, now or in any future
  state.
- Obligations capped: read the v0.2 candidate diff in the ~2026-07-25
  pre-publication window, push back on anything attestplane would defend
  differently, opt-out at any time.
- Institutional attribution form: **`attestplane project — maintained by
  @merchloubna70-dot`**. The project is the durable referent; the
  maintainer-of-record handle is there for traceability rather than
  personal branding.

Out-of-scope for the Reviewer role, declined explicitly in the
[issue #7 reply](https://github.com/attestplane/attestplane/issues/7#issuecomment-4501108977):

- Joint marketing.
- Hosted-service endorsement.
- Governance entanglement.
- Any economic axis (token, allocation, fee-share, listing, treasury).

## 3. The three converged primitives

For each adopted primitive, this section records: what attestplane
contributed, where it currently sits in om-world, the framing-preservation
ask carried into v0.2 freeze, and the failure mode to watch for.

### 3.1 Verifier independence rule

- **Attestplane's contribution.** Trust root MUST be the deterministic OSS
  verifier plus versioned schemas plus exported evidence bytes; hosted
  indices/APIs are a convenience layer only.
- **Current location in om-world.**
  [`docs/execution-proof.md#on-chain-verification`](https://github.com/omworldprotocol/om-world/blob/main/docs/execution-proof.md#on-chain-verification),
  introduced at commit
  [`61979b1`](https://github.com/omworldprotocol/om-world/commit/61979b1)
  as a first-class "Rule (verifier independence)" alongside the existing
  relayer-attested-bytes rule.
- **Framing to preserve through freeze.** Verification correctness MUST NOT
  depend on trusting any hosted index, API, or convenience service. A
  third-party auditor receiving a complete export must be able to verify
  offline: chain continuity, signatures, schema version, and the location
  of any verification failure.
- **Failure mode to watch for.** Any v0.2 rewording that softens "MUST" to
  "SHOULD", admits a hosted API as an acceptable trust root, or removes
  the offline-verifiability constraint.

### 3.2 Commit-then-redact deletion evidence

- **Attestplane's contribution.** Four-step pattern: minimize PII before
  ingest → commitments (hash / sealed / ZK claims) in the chain →
  raw / deletable material in a controller-owned sidecar → on verified
  deletion, destroy the sidecar AND append a signed deletion-evidence
  event preserving append-only.
- **Current location in om-world.**
  [`docs/execution-proof.md#deletion-evidence-commit-then-redact`](https://github.com/omworldprotocol/om-world/blob/main/docs/execution-proof.md#deletion-evidence-commit-then-redact),
  added as a top-level section at commit
  [`61979b1`](https://github.com/omworldprotocol/om-world/commit/61979b1).
- **Framing to preserve through freeze.** This is a profile for
  evidence-substrate-supports-deletion, not a legal compliance conclusion
  for any deployed system. Quoting attestplane's
  [closure response on issue #7](https://github.com/attestplane/attestplane/issues/7#issuecomment-4485790505),
  attestplane "should explicitly not claim GDPR compliance,
  right-to-erasure automation, or legal sufficiency without
  controller-specific review." The om-world spec already carries this
  distinction; the freeze must keep it.
- **Failure mode to watch for.** Any v0.2 rewording that presents
  commit-then-redact as GDPR-compliance machinery, right-to-erasure
  automation, or a legal conclusion. The substrate provides primitives;
  it does not decide legality.

### 3.3 Related-work cluster citation

- **Attestplane's contribution.** Position at the
  compliance-and-audit-substrate corner of the four-primitive convergence
  cluster, with the AIA-12 *aligned* profile framing — not a "compliant"
  or "certified" framing — preserved verbatim.
- **Current location in om-world.**
  [`docs/execution-proof.md#related-work`](https://github.com/omworldprotocol/om-world/blob/main/docs/execution-proof.md#related-work),
  alongside Trusteedxyz, Tyche Institute / EATF, and Occasio Labs;
  introduced at commit
  [`61979b1`](https://github.com/omworldprotocol/om-world/commit/61979b1).
- **Framing to preserve through freeze.** Two explicit asks recorded in
  attestplane's
  [issue #7 reply](https://github.com/attestplane/attestplane/issues/7#issuecomment-4501108977):
  - The **alpha qualifier** on attestplane in the cluster sentence.
  - The "evidence-substrate primitives, not a legal compliance conclusion
    for any deployed high-risk system" caveat.
  - The **AIA-12 *aligned* profile** framing — not "compliant" or
    "certified".
- **Failure mode to watch for.** Cluster sentence compression that drops
  the alpha qualifier, drops the substrate-primitives caveat, or
  re-labels attestplane's role as "compliant" or "certified".

## 4. Red lines for the v0.2 review

These are the conditions under which attestplane pushes back. They are
read against the v0.2 candidate diff in the ~2026-07-25 window.

- **R-A.** If the cluster sentence drops the alpha qualifier on
  attestplane → push back (cite §3.3 framing-preservation ask).
- **R-B.** If "compliant", "certified", or "certification" appears as a
  description of attestplane's role anywhere in the spec → push back. The
  AIA-12 *aligned* framing is the only acceptable label for attestplane's
  role; negative-hedge phrasing in om-world's spec ("not certified",
  "not a compliance conclusion") is fine and welcome.
- **R-C.** If the verifier independence rule is weakened to "hosted API is
  an acceptable trust root", or to a "SHOULD"-level recommendation, or
  removes the offline-verifiability constraint → push back (cite §3.1).
- **R-D.** If commit-then-redact is framed as GDPR-compliance machinery,
  right-to-erasure automation, or a legal sufficiency conclusion →
  push back (cite §3.2).
- **R-E.** If a tag or version reference to attestplane points at
  `v0.0.3-alpha` (the tag at the time of issue #7) instead of the
  current release at v0.2 freeze time → polite update request, not
  push-back. The design positions are unchanged; only the implementation
  surface has progressed past `v0.0.3-alpha`.

## 5. Reciprocal cross-reference — the receiving side

om-world has offered, and attestplane has accepted, a small reciprocal
cross-reference PR from om-world back into attestplane. Receiving-side
discipline:

- **Allowed landing points:**
  - `docs/architecture/verifier_independence.md` — short "Related"
    paragraph at the end pointing to
    [`omworldprotocol/om-world` `docs/execution-proof.md#on-chain-verification`](https://github.com/omworldprotocol/om-world/blob/main/docs/execution-proof.md#on-chain-verification).
  - `docs/adr/0015-retention-deletion-proof-profile.md` — "References"
    footer naming the cross-adoption.
- **Fenced off from cross-reference:**
  - `docs/spec/aia-12-aligned-profile.md` — that doc carries the
    AIA-12 *aligned* profile framing deliberately and the wording stays
    owned on the attestplane side. Cross-references *to* it from other
    repos are acceptable; rephrasing the framing inside it via a
    cross-repo edit is not.
- **PR review checklist when om-world's PR arrives:**
  1. PR touches only the two allowed files in §5.
  2. PR does not edit `docs/spec/aia-12-aligned-profile.md`.
  3. PR adds no marketing language, no hosted-service endorsement, no
     joint-program language.
  4. PR does not rephrase "aligned ≠ compliant/certified" anywhere.
  5. PR does not introduce any new economic-axis language.
  6. DCO sign-off present.

## 6. Review process during the v0.2 candidate window

- **Triggering signal.** om-world publishes a v0.2 candidate — expected
  announcement on the
  [`omworldprotocol/om-world` repo](https://github.com/omworldprotocol/om-world/),
  expected ~2026-07-25.
- **What to fetch.**
  - The v0.2 candidate spec text.
  - The diff against the current commit
    [`61979b1`](https://github.com/omworldprotocol/om-world/commit/61979b1)
    baseline.
- **What to review, in order:**
  1. **§Related work cluster** — alpha qualifier preserved, no
     "compliant"/"certified" creep on attestplane's entry, substrate-
     primitives caveat preserved.
  2. **§On-chain verification (verifier independence)** — trust root
     still = OSS verifier + versioned schemas + exported evidence bytes;
     hosted indices/APIs still characterized as convenience layer only.
  3. **§Deletion evidence (commit-then-redact)** — four-step pattern
     intact; framed as evidence-substrate profile, not as GDPR-compliance
     machinery.
  4. Any new content in §Related work that touches attestplane.
  5. Any tag or version reference to attestplane — should update from
     `v0.0.3-alpha` to the release current at v0.2 freeze time.
- **Output of the review.**
  - If any red line in §4 fires: a public comment on om-world's v0.2
    candidate PR (or on attestplane issue
    [#7](https://github.com/attestplane/attestplane/issues/7) if om-world
    prefers), citing each section by name and explicitly naming the
    red-line failure.
  - If no red line fires: a short public review-acknowledgement comment,
    citing the three primitives by section name.

## 7. Out-of-scope for this review

- Anything in om-world's `execution-proof` v0.2 that does not touch
  attestplane's three converged primitives or the Related-work cluster
  entry. The Reviewer role is scoped to the converged surface, not to
  general spec quality.
- Token, allocation, or governance-economy discussion in om-world v0.2 —
  declined per the GENESIS-BUILDERS policy boundary and the attestplane
  [issue #7 reply](https://github.com/attestplane/attestplane/issues/7#issuecomment-4501108977).
- Joint marketing, hosted-service endorsement, governance entanglement,
  any economic axis — declined per the
  [issue #7 reply](https://github.com/attestplane/attestplane/issues/7#issuecomment-4501108977).
- General-purpose attestation spec review beyond the converged primitives.

## 8. Audit trail

- attestplane issue
  [#7](https://github.com/attestplane/attestplane/issues/7) — the design
  thread.
- attestplane Reviewer-acceptance reply
  [comment](https://github.com/attestplane/attestplane/issues/7#issuecomment-4501108977).
- om-world adoption commit
  [`61979b1`](https://github.com/omworldprotocol/om-world/commit/61979b1).
- om-world baseline spec text
  [`docs/execution-proof.md`](https://github.com/omworldprotocol/om-world/blob/main/docs/execution-proof.md).
- om-world GENESIS-BUILDERS policy
  [`GENESIS-BUILDERS.md`](https://github.com/omworldprotocol/om-world/blob/main/GENESIS-BUILDERS.md).
- attestplane local closure record
  `docs/validation/issue_7_closure_report_20260519.md`.

## 9. Roadmap and opt-out

- Reviewer role exit is unilateral per the GENESIS-BUILDERS policy
  ("opt-out at any time"). No notice period is contractually required;
  a short public comment on
  [issue #7](https://github.com/attestplane/attestplane/issues/7)
  is sufficient and is the expected channel.
- If attestplane exits the Reviewer role, the spec adoptions in om-world
  remain — they were unconditional on attestplane's side at the time of
  the design response and remain so. Exiting the Reviewer listing does
  not retract the design contribution.
- If the v0.2 candidate review reveals an irrecoverable red-line drift,
  attestplane's options, in escalation order:
  1. Request changes via public comment on the v0.2 candidate.
  2. Opt out of the Reviewer listing while leaving the spec adoptions in
     place.
  3. Ask om-world to remove attestplane's entry from the §Related work
     cluster entirely.
- No autonomous governance commitment is made by this document. The only
  attestplane-side date anchored on by this review is the v1.0 GA target
  2026-08-15. om-world's freeze date 2026-08-01 and candidate window
  ~2026-07-25 are om-world-side facts, cited but not committed to on
  attestplane's behalf.
