<!--
Thanks for your contribution to Attestplane.

Before opening this PR, please confirm:
1. Your commits are signed off per the Developer Certificate of Origin (DCO). See CONTRIBUTING.md §1.
2. Your branch is one of: feat/<...>, fix/<...>, docs/<...>, refactor/<...>, chore/<...>, test/<...>.
3. If this PR is load-bearing (new framework mapping, hash chain change, TSA integration, security boundary), an ADR has been drafted in docs/adr/. See CONTRIBUTING.md §5.

Title format: <type>: <imperative present-tense summary>
  examples:  feat: add NIS2 incident reporting helper
             fix: resolve duplicate hash chain entries under concurrent writes
             docs: clarify TSA endpoint configuration in README
-->

## Summary

<!-- One paragraph: what changes, and why. Link to the issue this addresses. -->

Closes #

## Type of change

- [ ] Bug fix (no API change)
- [ ] New feature (additive, no API break)
- [ ] Breaking change (API or behavior change — describe migration path)
- [ ] Documentation only
- [ ] Refactor (no behavior change)
- [ ] Test / tooling only

## Risk and ADR classification

- **Risk level** (check one): `[ ]` low (docs / typos / single-file fix) `[ ]` medium (cross-file refactor / dependency bump / CI change) `[ ]` high (release / signing / security / governance / breaking API)
- **Needs ADR?**: `[ ]` no `[ ]` yes — link to the ADR draft `[ ]` already linked above
- **Impact surface**: `[ ]` python-sdk `[ ]` ts-sdk `[ ]` verifier `[ ]` docs `[ ]` ci `[ ]` release/signing `[ ]` governance

## Compliance / security impact

<!--
Does this change affect any of the following? If yes, describe.
  - Hash chain semantics or algorithm
  - Time-stamp authority (TSA) integration
  - Trust boundary, threat model, or attack surface
  - A framework mapping (EU AI Act / DORA / GDPR / NIS2 / CRA / etc.)
  - Storage of sensitive material (keys, PII, secrets)

If no compliance/security impact, write "None".
-->

## How to validate

<!--
How can a reviewer verify this change works as intended?
  - New / updated unit tests (point to them)
  - Manual reproduction steps
  - Performance benchmarks (if relevant)
-->

## ADR

<!-- Required for substantive/architectural changes. Link the ADR PR or filename. Write "Not required" otherwise. -->

ADR:

## DCO sign-off confirmation

- [ ] All commits in this PR include a `Signed-off-by:` trailer matching the commit author.
- [ ] I have read [CONTRIBUTING.md](../CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).

## AI tool disclosure (transparency, not gatekeeping)

<!--
Was any part of this PR (code, tests, docs) authored with the assistance of an
AI coding tool such as GitHub Copilot, Claude Code, Cursor, Codex, Gemini Code
Assist, or similar?

We are happy to receive AI-assisted contributions. We just ask you to declare
which tool you used and confirm that:
- You have read every line you submit and stand behind it.
- The DCO sign-off applies to you (the human submitter), not the tool.
- You did not paste output verbatim without verifying license compatibility.

This disclosure is for transparency; it does not affect whether the PR is
accepted.
-->

- [ ] No AI tool was used.
- [ ] AI tool was used. Tool / model: `<fill in, e.g. "Claude Sonnet 4.6" or "GitHub Copilot">`
- [ ] I have read every line I am submitting and stand behind it as my own.

## Release Impact
<!-- Check exactly one. Required — CI will block merge if none is selected. -->
- [ ] `release:major` — breaking change to public API or existing behaviour
- [ ] `release:minor` — new backwards-compatible public API, field, exit-code, or schema field
- [ ] `release:patch` — bug fix, internal refactor, test, or docs with no public API change
- [ ] `release:none` — no release needed (CI/tooling/infra only)

- Use `release:major` for changes described by ADR-VERSIONING-001 as breaking or requiring a migration.
- Use `release:minor` for additive, backwards-compatible surface changes under ADR-VERSIONING-001.
- Use `release:patch` for fixes, refactors, tests, and docs that do not change the public API under ADR-VERSIONING-001.
- Use `release:none` for CI, tooling, or infrastructure-only changes with no release impact under ADR-VERSIONING-001.
