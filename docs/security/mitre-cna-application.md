<!--
SPDX-FileCopyrightText: 2026 The Attestplane Authors
SPDX-License-Identifier: Apache-2.0
-->

# MITRE CNA enrollment — application prep doc (v2)

This document is the pre-prepared prep material for Attestplane's
enrollment as a
[CVE Numbering Authority (CNA)](https://www.cve.org/ProgramOrganization/CNAs)
under the MITRE-coordinated CVE Program. Enrollment is zero-cost,
signals process maturity, and pairs cleanly with the ENISA / EU Cyber
Resilience Act preparation work already noted in
[`SECURITY.md`](../../SECURITY.md).

**Document status (2026-05-21):** v2 revision adds an honest
readiness-threshold self-assessment (§1), a copy-paste-ready
`cveform.mitre.org` field map (§2), and the supplementary-materials
checklist a CNA-LR applicant is expected to provide (§3). The
maintainer recommendation, after threshold review, is to **defer
submission until after the v1.0 GA cut (target 2026-08-15)** rather
than submit pre-GA; the rationale is documented below.

## Scope of this document

This PR adds the **prep doc only**. It does not submit the application
to the CVE Program; that step is a maintainer follow-up after the
project crosses the readiness thresholds identified in §1 below. No
calendar date is promised for the submission itself.

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

Attestplane would apply as a **CNA-LR (Limited Scope CNA)** — its
authority would cover *only* products it itself ships
(`attestplane` substrate, official SDKs, official adapters under the
`attestplane/` GitHub organisation). It would **not** assert authority
over third-party software, downstream forks, or unrelated AI agent
projects.

The reasons enrollment is sequenced for the post-GA window (rather
than pre-GA):

1. **Side B procurement.** Bank / hospital / government procurement
   evaluations frequently include a "Are you a CVE issuer / are you
   listed in the CVE Program?" checkbox. CNA enrollment converts that
   item from `No` to `Yes` without modifying the substrate — but only
   has procurement weight once the listing is *active*, not
   *pending*. Submitting pre-GA risks an extended pending state with
   no procurement benefit.
2. **ENISA-CRA 2027 pipeline alignment.** The EU Cyber Resilience Act
   enters application on 2027-12-11
   ([`SECURITY.md § CRA 2027`](../../SECURITY.md)). CRA Article 14
   incident-reporting and Article 13 vulnerability-handling
   obligations interoperate naturally with a CNA-issued CVE workflow.
   Post-GA enrollment still leaves >15 months of runway before CRA
   application, which is ample.
3. **Coordinated disclosure clarity.** Reporters using the project's
   GitHub Security Advisories channel currently rely on GitHub's
   advisory database for CVE assignment. CNA enrollment lets the
   project assign CVE IDs against its own scope deterministically —
   but only meaningful once the substrate has shipped GA and has
   real-world deployments capable of generating valid vulnerability
   reports.

---

## §1. Honest readiness-threshold self-assessment

The CVE Program's published
[CNA Operational Rules](https://www.cve.org/ResourcesSupport/AllResources/CNARules)
do not specify a hard numerical user-base or maturity floor, but the
root-CNA (MITRE for an independent OSS project) exercises discretion
when admitting applicants. The maintainer's honest read of the
project's current posture against each criterion follows. **The
overall conclusion is partial — three known gaps argue for deferring
submission until after v1.0 GA (target 2026-08-15).**

### 1.1 Criteria the project meets today

| Criterion (per CNA Operational Rules) | Status | Evidence |
|---------------------------------------|--------|----------|
| Public vulnerability-disclosure policy | **Met** | [`SECURITY.md`](../../SECURITY.md) — `security@attestplane.com` + GitHub Security Advisories + 90-day embargo |
| Defined scope of products | **Met** | Attestplane substrate, Python SDK, TypeScript SDK, official adapters; scope per [`SECURITY.md § Scope`](../../SECURITY.md) |
| Public point of contact (institutional) | **Met** | `security@attestplane.com` — non-personal, routed to maintainer queue |
| Coordinated-disclosure handling commitment | **Met** | 90-day default embargo, severity tiers, response SLA published |
| Response SLA published (acknowledge / triage / fix) | **Met** | 7-day acknowledge / 14-day triage / 30-day Critical fix per `SECURITY.md` — exceeds the CNA Operational Rules' minimum of "acknowledge within a reasonable period" |
| Apache-2.0 / open-source / community project | **Met** | Apache-2.0; OpenSSF Best Practices passing badge ([project 12924](https://www.bestpractices.dev/projects/12924/)) |
| English-language coordination | **Met** | All security correspondence and advisories in English |
| Willingness to follow CNA Operational Rules | **Met (commitment)** | Maintainer commits to follow current rules at submission time |

### 1.2 Three known gaps that argue for deferring submission

| Gap | Risk severity for application review | Mitigation timeline |
|-----|--------------------------------------|---------------------|
| **(a) User base — pre-GA, no production deployments** | High | Production users emerge after v1.0 GA cut (target 2026-08-15) and the first month of GA tag soak. CNA-LR applications are reviewed on the basis of *expected vulnerability volume*; a pre-GA project with zero confirmed production users may be deferred by the root CNA as "no current vulnerability-handling load to justify a namespace." |
| **(b) Pre-GA tag line** | Medium | The current 1.0.x line is explicitly pre-GA per `SECURITY.md`. Pre-GA software is not categorically barred from CNA listing — there is precedent — but the bar is higher because the disclosure-handling process is unexercised in production. Post-GA (after the first real CVE-class report is acknowledged and worked through `SECURITY.md`'s SLA), the application becomes considerably stronger. |
| **(c) Single-maintainer governance gap** | Medium | The project openly documents this in its threat model and OpenSSF Best Practices profile. CNA Operational Rules expect the CNA function to survive a maintainer being unavailable. Mitigations: (i) maintainer's China-licensed commercial+compliance lawyer credentials raise reviewer confidence in process discipline; (ii) `security@attestplane.com` is institutional, not personal; (iii) plan for a second triage contact (advisor or co-maintainer) before submission. This gap does not block submission by itself but is best disclosed candidly in the application narrative. |

### 1.3 Maintainer recommendation

**Defer submission to the post-GA window (2026-08-15 + 1 month
minimum, i.e. earliest 2026-09-15).** Submitting earlier carries
the risk of (i) a deferral by the MITRE root CNA citing pre-GA
status, which is unhelpful to procurement narratives, or (ii) a
provisional accept that imposes a stricter watch period than a
post-GA application would.

Submitting post-GA, after at least one full disclosure cycle has been
exercised end-to-end against the published SLA, is materially
stronger from a reviewer's perspective and aligns with the
2027-12-11 CRA Article 14 timeline with comfortable margin.

The post-GA submission window remains zero-cost; nothing is lost by
waiting.

### 1.4 What pre-GA work makes the post-GA submission stronger

The following internal milestones are tracked and, when completed,
will materially strengthen the eventual application:

1. **First end-to-end disclosure cycle exercised** (any severity).
   Even a low-severity report worked through acknowledge → triage →
   fix → publication demonstrates the process is real, not paper.
2. **GPG key published at `https://attestplane.com/.well-known/security.txt`**
   (M5 W6 target per `SECURITY.md`).
3. **Second triage contact added.** A named second person — advisor,
   co-maintainer, or designated escalation — reduces the
   single-maintainer governance risk that reviewers will probe.
4. **Internal CVE-assignment SOP drafted** (assignment authority,
   review path, publication channel, conflict-of-interest handling).
   The SOP need not be public, but its existence is referenced in
   the application narrative.
5. **At least one tagged GA release** with reproducible-build
   evidence and a Sigstore signature (M5 supply-chain track).

---

## §2. `cveform.mitre.org` field map (copy-paste ready)

The enrollment form is at
[`cveform.mitre.org`](https://cveform.mitre.org/) under request type
**"Request a CVE ID block / Request CNA Status"** (top-level
selector). The maintainer should verify field labels against the
live form at submission time — the values below are the canonical
project answers regardless of label wording.

### 2.1 Identity and contact

| cveform field | Value to paste |
|---------------|----------------|
| Request Type | Request CNA Status |
| Organisation legal name | Attestplane Pte. Ltd. (Singapore — registration status as of submission date; the maintainer updates this line at submission) |
| Organisation type | Open-source project with commercial entity maintainer |
| Organisation website | `https://attestplane.com` |
| Public-facing project URL | `https://github.com/attestplane/attestplane/` |
| Primary contact name | (maintainer fills in at submission; do not commit personal name to repo) |
| Primary contact email (institutional) | `security@attestplane.com` |
| Backup contact email | (second triage contact email — to be designated before submission per §1.4) |
| Languages supported for coordination | English |
| Country of operation | Singapore (entity) / People's Republic of China (founder residence) |

### 2.2 CNA scope and role

| cveform field | Value to paste |
|---------------|----------------|
| Requested CNA role | CNA-LR (Limited Scope CNA) — own products only |
| Preferred root CNA | MITRE Corporation |
| Proposed CNA scope (verbatim) | Vulnerabilities in the Attestplane substrate (`attestplane` PyPI package, `@attestplane/attestplane` npm package), the official Python SDK, the official TypeScript SDK, and official adapters published under the `attestplane/` GitHub organisation. Out of scope: third-party forks, third-party adapters, upstream LLM model alignment, customer self-host misconfiguration, and any software not published by the Attestplane project. |
| Estimated CVEs / year | <10 (pre-GA estimate; revisited annually) |
| Justification for joining the CVE Program | Side B (financial / healthcare / public-sector) procurement frequently requires the supplier to be a CVE issuer. Aligning with EU CRA 2027-12 vulnerability-handling obligations. Coordinated-disclosure clarity for reporters using GitHub Security Advisories. |

### 2.3 Disclosure policy and process

| cveform field | Value to paste |
|---------------|----------------|
| Public vulnerability-disclosure policy URL | `../../SECURITY.md` |
| Public security contact email (must match disclosure policy) | `security@attestplane.com` |
| Acknowledgement SLA | 7 days from receipt (per `SECURITY.md § Response Timeline`) |
| Triage / initial severity SLA | 14 days from receipt |
| Fix-or-mitigation SLA — Critical / High / Medium-Low | 30 / 60 / 90 days respectively |
| Default embargo length | 90 days, coordinated, with good-faith negotiation for shorter windows on Critical findings |
| Reporter credit policy | Credit by name or handle in release notes; opt-out available |
| Pre-GA encrypted channel | GitHub Security Advisories (TLS-in-transit private reporting) until GPG key published at M5 W6 |
| GPG key publication channel(s) | `SECURITY.md`, project homepage security page, MIT PGP keyserver |

### 2.4 Governance and continuity

| cveform field | Value to paste |
|---------------|----------------|
| Number of maintainers with security-triage authority | 1 currently (publicly documented single-maintainer governance gap); second triage contact to be designated before submission |
| Maintainer professional background relevant to security operations | China-licensed practising commercial-and-compliance lawyer; entity is a Singapore Pte. Ltd. with founder-led governance |
| Continuity plan if primary maintainer is unavailable | Backup triage email + GitHub Security Advisories private channel + (planned at GA) designated co-triage contact |
| Conflict-of-interest policy for CVE assignment | Maintainer commits not to assign CVEs against the project where they themselves authored the offending code without independent review by the second triage contact (post-GA) |
| Acceptance of CNA Operational Rules (current version at submission) | Confirmed (checkbox at submission time — maintainer re-reads current rules immediately before submitting) |

### 2.5 Supporting artefacts to attach or link

| cveform field | Value to paste |
|---------------|----------------|
| Disclosure policy URL | `../../SECURITY.md` |
| Public repository URL | `https://github.com/attestplane/attestplane/` |
| License | Apache-2.0 |
| OpenSSF Best Practices badge | `https://www.bestpractices.dev/projects/12924/` (passing) |
| Threat model | [`docs/security/threat-model-v1.md`](threat-model-v1.md) |
| GPG key fingerprint (post-GA) | (filled in at submission, after M5 W6 publication; pre-GA submission would mark "to be published at v1.0 GA cut, target 2026-08-15") |

---

## §3. Supplementary-materials checklist

Items the maintainer should have ready *before* opening the cveform
submission. None of these need to be inlined into the form itself,
but reviewers may request them by reply.

- [ ] **Disclosure policy URL stable** at `../../SECURITY.md` — confirmed reachable and not behind a redirect chain.
- [ ] **Acknowledgement SLA published** in the same document (7-day per `SECURITY.md`). Reviewers verify this with their own browser.
- [ ] **Institutional security contact** (`security@attestplane.com`) confirmed receiving mail and routing to maintainer queue. Send a self-test from an external address.
- [ ] **Second triage contact** designated and the contact aware of the responsibility (verbal/email confirmation retained).
- [ ] **Scope statement** matches verbatim between `SECURITY.md § Scope`, this application doc, and the form submission. No divergence.
- [ ] **CNA Operational Rules** read in their current published version (within 24 hours of submission). Note the version number on the application.
- [ ] **Maintainer commitment letter** drafted: a single page stating willingness to follow CNA Operational Rules, attend the CNA mailing list, and respond to root-CNA queries within 7 days. Keep ready to attach if requested.
- [ ] **Conflict-of-interest acknowledgement** drafted (one paragraph). The maintainer's own code is the most likely target of CVE assignments under the project's scope; the acknowledgement states how this is handled (second-contact review).
- [ ] **Internal CVE-assignment SOP** drafted (need not be public). Reviewers may ask to see process; having a written SOP demonstrates seriousness.
- [ ] **First end-to-end disclosure cycle exercised** — even a low-severity report worked through the full SLA. Cite the resulting advisory in the application narrative.
- [ ] **GPG key published** at `https://attestplane.com/.well-known/security.txt` (M5 W6). Pre-GA submission is possible without this, but the application is stronger with the key live.
- [ ] **Maintainer professional credential disclosed** in the application narrative (China-licensed commercial+compliance lawyer). This is not a CNA requirement but it raises reviewer confidence in process discipline and is appropriate to surface candidly.

---

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

The maintainer's submission process (to be performed after the
project crosses the §1.4 readiness milestones, no calendar date
promised here):

1. Re-read the current
   [CNA Operational Rules](https://www.cve.org/ResourcesSupport/AllResources/CNARules)
   immediately before submission and note the version number on the
   application.
2. Confirm every row in §2's field map still matches the live form
   labels.
3. Submit the *Request CNA Status* request at
   [`cveform.mitre.org`](https://cveform.mitre.org/) using the field
   values prepared above.
4. Coordinate with the MITRE root CNA on any clarifications,
   responding within 7 days as committed.
5. Once enrolled, add the CNA roster URL and the project's
   CVE-prefix scope wording (as finalised with the root CNA) into
   [`SECURITY.md`](../../SECURITY.md) and link from this document.
6. Publish the internal CVE-assignment SOP (or its public-summary
   version) before the first CVE is issued under the project's
   namespace.

## When to revisit

- **Pre-GA window (now → 2026-08-15):** Track the §1.4 milestones;
  do not submit.
- **Post-GA window (2026-08-15 → 2026-09-15):** Bake one full
  disclosure cycle. Do not submit yet.
- **Earliest submission window (2026-09-15 onwards):** All §1.4
  milestones met → maintainer makes the submission call.
- **Pre-CRA application date (2027-12-11):** Confirm CNA status is
  active and the CVE-assignment SOP has been exercised at least once
  before CRA Article 14 incident-reporting obligations enter force.

## Out of scope for this PR

- The actual MITRE CNA application submission — a maintainer task
  after the readiness thresholds are crossed, not in this PR.
- The internal CVE-assignment SOP — to be drafted in a separate
  follow-up before first CVE issuance.
- Modifying [`SECURITY.md`](../../SECURITY.md) — the existing
  vulnerability-disclosure policy is referenced as-is; no edits to
  the GPG plan or the response timeline are made here.

## Non-claim (restated)

Enrollment as a CNA is a **process matter, not a compliance
certification**. It does not constitute any regulatory determination.
The pre-GA boundary of the substrate (per
[`SECURITY.md`](../../SECURITY.md)) is unaffected by CNA status.
