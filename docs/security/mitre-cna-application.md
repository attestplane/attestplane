<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# MITRE CNA enrollment — application prep doc

This document is the pre-prepared prep material for Attestplane's
enrollment as a
[CVE Numbering Authority (CNA)](https://www.cve.org/ProgramOrganization/CNAs)
under the MITRE-coordinated CVE Program. Enrollment is zero-cost,
signals process maturity, and pairs cleanly with the ENISA / EU Cyber
Resilience Act preparation work already noted in
[`SECURITY.md`](../../SECURITY.md).

## Scope of this document

This PR adds the **prep doc only**. It does not submit the application
to the CVE Program; that step is a maintainer follow-up after this
file is merged. No date is promised for the submission itself — it
will be submitted by the maintainer when ready.

## What is a CNA, and why apply

A **CVE Numbering Authority (CNA)** is an organisation authorised by
the CVE Program to assign CVE Identifiers from its own namespace for
vulnerabilities in products under its scope. For Attestplane, this
would mean:

- The project owns its own CVE namespace for vulnerabilities reported
  against the Attestplane substrate, SDKs, and adapters.
- Coordinated disclosure under the project's
  [`SECURITY.md`](../../SECURITY.md) policy can issue a CVE directly
  rather than waiting for an upstream root-CNA assignment.
- The project name appears in the public CNA roster at
  [`cve.org/PartnerInformation/ListofPartners`](https://www.cve.org/PartnerInformation/ListofPartners).

The reasons enrollment is sequenced now (zero-cost, ahead of v1.0 GA):

1. **Side B procurement.** Bank / hospital / government procurement
   evaluations frequently include a "Are you a CVE issuer / are you
   listed in the CVE Program?" checkbox. CNA enrollment converts that
   item from `No` to `Yes` without modifying the substrate.
2. **ENISA-CRA 2027 pipeline alignment.** The EU Cyber Resilience Act
   enters application on 2027-12-11
   ([`SECURITY.md § CRA 2027`](../../SECURITY.md)). CRA Article 14
   incident-reporting and Article 13 vulnerability-handling
   obligations interoperate naturally with a CNA-issued CVE workflow.
   Enrolling well ahead of the application date avoids a same-quarter
   compliance scramble.
3. **Coordinated disclosure clarity.** Reporters using the project's
   GitHub Security Advisories channel currently rely on GitHub's
   advisory database for CVE assignment. CNA enrollment lets the
   project assign CVE IDs against its own scope deterministically.

## Eligibility checklist (self-assessment)

The CVE Program publishes the
[CNA eligibility criteria](https://www.cve.org/ProgramOrganization/CNAs#BecomeACNA).
Mapping each against the project's current observable state:

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Active vulnerability-disclosure process | **Met** | [`SECURITY.md`](../../SECURITY.md) — `security@attestplane.com` + GitHub Security Advisories channel + 90-day embargo policy |
| Defined scope of products | **Met** | Attestplane substrate, Python SDK, TypeScript SDK, official adapters; scope documented in [`SECURITY.md § Scope`](../../SECURITY.md) |
| Public point of contact | **Met** | `security@attestplane.com` (institutional) per `SECURITY.md` |
| Public disclosure policy | **Met** | `SECURITY.md` — coordinated 90-day disclosure with embargo terms |
| Open-source / community project | **Met** | Apache-2.0, public repository, OpenSSF Best Practices passing badge ([project 12924](https://www.bestpractices.dev/projects/12924)) |
| English-language coordination | **Met** | All security correspondence and advisories in English |
| Acceptance of CNA Rules and Operational Rules | **To be confirmed at submission** | Maintainer reviews the current [CNA Operational Rules](https://www.cve.org/ResourcesSupport/AllResources/CNARules) at submission time and acknowledges in the application form |
| Root CNA selection | **To be selected at submission** | MITRE root-CNA is the natural choice for an independent OSS project not under another root-CNA's umbrella |

## Application form fields prep

The enrollment form is at
[`cveform.mitre.org`](https://cveform.mitre.org/) (Request Type:
*Become a CNA*). Field values to use:

| Form field | Prepared value |
|------------|----------------|
| Organisation name | Attestplane Pte. Ltd. (Singapore, in formation as of 2026-05-17) |
| Organisation type | Open-source project with commercial entity maintainer |
| Public contact email | `security@attestplane.com` |
| Public disclosure policy URL | `https://github.com/attestplane/attestplane/blob/main/SECURITY.md` |
| Proposed CNA scope | Attestplane substrate (`attestplane` PyPI / `@attestplane/attestplane` npm), official SDKs, official adapters under the `attestplane/` GitHub organisation |
| Languages supported | English |
| Preferred root CNA | MITRE |
| Public repository | `https://github.com/attestplane/attestplane` |
| License | Apache-2.0 |

The form may evolve; the maintainer verifies field labels against the
live form at submission time. The values above are the canonical
project answers regardless of label wording.

## Honest non-claim

MITRE CNA enrollment is a **process matter, not a compliance
certification**. Being listed as a CNA:

- Does not constitute EU AI Act Article 12 logging conformance.
- Does not constitute CRA 2027 conformity assessment.
- Does not constitute SLSA Build L3 certification.
- Does not endorse, certify, or attest to the security of any
  Attestplane release.
- Does not modify the AIA-12 *aligned* profile recorded in
  [`docs/spec/aia-12-aligned-profile.md`](../spec/aia-12-aligned-profile.md).

It records, publicly, that the project operates a coordinated
disclosure process at a level the CVE Program considers consistent
with its operational rules — nothing more, and nothing less.

## Maintainer follow-up action items

The maintainer's submission process (to be performed after this prep
doc merges, when ready — no date promised here):

1. Re-read the current
   [CNA Operational Rules](https://www.cve.org/ResourcesSupport/AllResources/CNARules)
   and the
   [CNA Rules](https://www.cve.org/ResourcesSupport/AllResources/CNARules)
   to confirm no eligibility criterion has shifted.
2. Submit the *Become a CNA* request at
   [`cveform.mitre.org`](https://cveform.mitre.org/) using the field
   values prepared above.
3. Coordinate with MITRE root-CNA on any clarifications.
4. Once enrolled, add the CNA roster URL and the project's
   CVE-prefix (`CVE-…/attestplane` scope wording, as finalised with
   the root CNA) into [`SECURITY.md`](../../SECURITY.md) and link
   from this document.
5. Document the internal CVE-assignment SOP (who can assign, the
   review path, the publication channel) before the first CVE is
   issued under the project's namespace.

## When to revisit

- **Pre-GA submission window.** Submission in the pre-GA window is
  fine and signals maturity ahead of the v1.0 GA cut (target
  2026-08-15 per `SECURITY.md`).
- **At v1.0 GA cut.** Re-confirm the application status; if enrolled,
  surface the CNA listing in release notes. If still pending, note in
  the GA postmortem.
- **Pre-CRA application date (2027-12-11).** Confirm CNA status is
  active and the CVE-assignment SOP is exercised at least once
  before CRA Article 14 incident-reporting obligations enter force.

## Out of scope for this PR

- The actual MITRE CNA application submission — a maintainer task
  afterwards, not in this PR.
- The internal CVE-assignment SOP — to be drafted in a separate
  follow-up after enrollment.
- Modifying [`SECURITY.md`](../../SECURITY.md) — the existing
  vulnerability-disclosure policy is referenced as-is; no edits to
  the GPG plan or the response timeline are made here.

## Non-claim (restated)

Enrollment as a CNA is a **process matter, not a compliance
certification**. It does not constitute any regulatory determination.
The pre-GA boundary of the substrate (per
[`SECURITY.md`](../../SECURITY.md)) is unaffected by CNA status.
